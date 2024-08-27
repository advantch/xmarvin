from litellm import ModelResponse
from litellm.utils import StreamingChoices
from openai.types import FileObject, CreateEmbeddingResponse
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from polyfactory.factories.pydantic_factory import ModelFactory
from openai.types.beta.threads import Message, MessageDelta
from openai.types.beta.threads.runs import (
    RunStep,
    RunStepDelta,
    ToolCallDeltaObject,
    ToolCallsStepDetails,
)
from openai.types.beta.threads.run import Run
from openai.types.beta.assistant_stream_event import (
    ThreadRunCompleted,
    ThreadRunFailed,
    ThreadRunCancelled,
)


class ChatCompletionChunkFactory(ModelFactory):
    __model__ = ChatCompletionChunk
    __allow_none_optionals__ = False


class ChoiceFactory(ModelFactory):
    __model__ = ChunkChoice


class ChoicesFactory(ModelFactory):
    __model__ = StreamingChoices
    __allow_none_optionals__ = False


class CustomStreamWrapperFactory(ModelFactory):
    choices = ChoicesFactory
    __model__ = ModelResponse
    __allow_none_optionals__ = False


class ModelResponseFactory(ModelFactory):
    choices = ChoicesFactory
    __model__ = ModelResponse
    __allow_none_optionals__ = False


class FileObjectFactory(ModelFactory):
    __model__ = FileObject
    __allow_none_optionals__ = False


class EmbeddingFactory(ModelFactory):
    __model__ = CreateEmbeddingResponse
    __allow_none_optionals__ = False


class MessageFactory(ModelFactory[Message]):
    __model__ = Message
    __allow_none_optionals__ = False


class MessageDeltaFactory(ModelFactory[MessageDelta]):
    __model__ = MessageDelta
    __allow_none_optionals__ = False


class RunStepFactory(ModelFactory[RunStep]):
    __model__ = RunStep
    __allow_none_optionals__ = False


class ToolCallsStepDetailsFactory(ModelFactory[ToolCallsStepDetails]):
    __model__ = ToolCallsStepDetails
    __allow_none_optionals__ = False


class RunStepDeltaFactory(ModelFactory[RunStepDelta]):
    __model__ = RunStepDelta
    __allow_none_optionals__ = False


class RunFactory(ModelFactory[Run]):
    __model__ = Run
    __allow_none_optionals__ = False


class ThreadRunCompletedFactory(ModelFactory[ThreadRunCompleted]):
    __model__ = ThreadRunCompleted
    __allow_none_optionals__ = False


class ThreadRunFailedFactory(ModelFactory[ThreadRunFailed]):
    __model__ = ThreadRunFailed
    __allow_none_optionals__ = False


class ThreadRunCancelledFactory(ModelFactory[ThreadRunCancelled]):
    __model__ = ThreadRunCancelled
    __allow_none_optionals__ = False


class ToolCallDeltaObjectFactory(ModelFactory[ToolCallDeltaObject]):
    __model__ = ToolCallDeltaObject
    __allow_none_optionals__ = False
