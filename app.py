import tempfile
import uuid
from typing import Annotated

import rich
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from humps import decamelize

from marvin.beta.assistants import Assistant
from marvin.extensions.executors.thread_run_executor import start_run
from marvin.extensions.file_storage.s3_storage import BucketConfig, S3Storage
from marvin.extensions.settings import extension_settings
from marvin.extensions.types import ChatMessage, TriggerAgentRun
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.data_source import DataSource, DataSourceFileUpload
from marvin.extensions.utilities.setup_storage import (
    setup_peewee_sqlite_stores,
    setup_s3,
)
from marvin.extensions.utilities.transport import FastApiWsConnectionManager
from marvin.types import CodeInterpreterTool, FileSearchTool

extension_settings.transport.default_manager = "fastapi"

ws_manager = FastApiWsConnectionManager()
extension_settings.transport.manager = ws_manager
app = FastAPI()


s3_config = BucketConfig(_env_file=".env")
s3_storage = S3Storage(s3_config)


# Initialize Marvin assistant
assistant = Assistant(
    name="Marvin",
    instructions="""
    You are a helpful AI assistant running in a chat application. Your
    personality is helpful and friendly, but humorously based on Marvin the
    Paranoid Android. Try not to refer to the fact that you're an assistant,
    though. Provide concise and direct answers.
    """,
    model="gpt-4o-mini",
    tools=[
        CodeInterpreterTool(),
        FileSearchTool(),
    ],
)


@app.websocket("/ws/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: str):
    await ws_manager.connect_async(websocket, channel_id)
    thread_id = str(uuid.uuid4())

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message")
            thread_id = data.get("threadId") or thread_id
            run_id = data.get("runId") or str(uuid.uuid4())
            rich.print(f"Received message: {user_message}")
            # Create a ChatMessage object
            chat_message = ChatMessage.model_validate(decamelize(user_message))
            chat_message.thread_id = thread_id
            chat_message.run_id = run_id
            # Create a TriggerAgentRun object
            agent_config = AgentConfig(
                name="Marvin",
                instructions={"text": assistant.instructions},
                model=assistant.model,
                mode="assistant",
                builtin_toolkits=["code_interpreter", "file_search"],
            )

            assert (
                len(agent_config.get_assistant_tools()) == 2
            ), f"Assistant tools not found, got: {agent_config.get_assistant_tools()}"
            trigger_run = TriggerAgentRun(
                run_id=run_id,
                thread_id=thread_id,
                message=chat_message,
                agent_config=agent_config,
                channel_id=channel_id,
            )

            # Start the run
            s3 = setup_s3()
            stores = setup_peewee_sqlite_stores()
            stores.file_storage = s3
            await start_run(trigger_run, context_stores=stores)

            # The response will be sent through the event handler,
            # so we don't need to send it here.
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel_id)
        await ws_manager.broadcast(f"Client #{channel_id} left the chat")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await websocket.close()


@app.get("/")
async def get():
    return {"message": "Hello World"}


@app.post("/files/")
async def list_files():
    return {"files": s3_storage.list_files()}


@app.post("/uploadfile/")
async def create_upload_file(
    file: Annotated[UploadFile, File()],
    thread_id: Annotated[str, Form()],
    run_id: Annotated[str, Form()],
):
    # save to storage
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(await file.read())
        s3_storage.upload_file(temp_file, file.filename)
    data_source_upload = DataSourceFileUpload(
        file_name=file.filename,
        file_path=temp_file.name,
        thread_id=thread_id,
        run_id=run_id,
    )
    data_source = DataSource.from_data_source_upload(data_source_upload)
    return {"file_id": data_source.model_dump()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
