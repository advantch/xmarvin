from marvin.extensions.context.run_context import RunContextStores
from marvin.extensions.file_storage.local_file_storage import LocalFileStorage
from marvin.extensions.file_storage.s3_storage import BucketConfig, S3Storage
from marvin.extensions.storage import (
    InMemoryAgentStore,
    InMemoryDataSourceStore,
    InMemoryMessageStore,
    InMemoryRunStore,
    InMemoryThreadStore,
    InMemoryToolStore,
)
from marvin.extensions.storage.custom.peewee_db import (
    PeeweeAgentStore,
    PeeweeDataSourceStore,
    PeeweeMessageStore,
    PeeweeRunStore,
    PeeweeThreadStore,
    PeeweeToolStore,
    init_sqlite_db,
)
from marvin.extensions.storage.vector_store import BaseVectorStore, InMemoryVectorStore


def setup_memory_stores() -> RunContextStores:
    """
    Sets up in-memory stores for testing and development.
    """
    return RunContextStores(
        thread_store=InMemoryThreadStore(),
        message_store=InMemoryMessageStore(),
        run_store=InMemoryRunStore(),
        agent_store=InMemoryAgentStore(),
        data_source_store=InMemoryDataSourceStore(),
        tool_store=InMemoryToolStore(),
        file_storage=LocalFileStorage(),
    )


def setup_peewee_sqlite_stores(db_path: str | None = None) -> RunContextStores:
    """
    Sets up Peewee SQLite stores for testing and development.
    Files are stored in the file system
    """
    init_sqlite_db(db_path=db_path)
    return RunContextStores(
        thread_store=PeeweeThreadStore(),
        message_store=PeeweeMessageStore(),
        run_store=PeeweeRunStore(),
        agent_store=PeeweeAgentStore(),
        data_source_store=PeeweeDataSourceStore(),
        tool_store=PeeweeToolStore(),
        file_storage=LocalFileStorage(),
    )


# def setup_dj_stores() -> RunContextStores:
#     """
#     Sets up Django stores for testing and development.
#     """
#     from marvin.extensions.utilities.transport import ChannelsConnectionManager
#     from marvin.extensions.storage.custom.dj import ThreadModel, MessageModel, RunModel, AgentModel, DataSourceModel, ToolModel
#     from marvin.extensions.storage import DjangoThreadStore, DjangoMessageStore, DjangoRunStore, DjangoAgentStore, DjangoDataSourceStore, DjangoToolStore
#     return RunContextStores(
#         thread_store=DjangoThreadStore(model=ThreadModel),
#         message_store=DjangoMessageStore(model=MessageModel),
#         run_store=DjangoRunStore(model=RunModel),
#         agent_store=DjangoAgentStore(model=AgentModel),
#         data_source_store=DjangoDataSourceStore(model=DataSourceModel),
#         tool_store=DjangoToolStore(model=ToolModel),
#         file_storage=LocalFileStorage(),
#         connection_manager=ChannelsConnectionManager(),
#     )


def get_vector_store() -> BaseVectorStore:
    """
    Returns the vector store to use for testing and development.
    """
    return InMemoryVectorStore()


def setup_s3():
    from marvin.extensions.settings import s3_settings

    config = BucketConfig(
        bucket_name=s3_settings.bucket_name,
        access_key_id=s3_settings.access_key_id,
        secret_access_key=s3_settings.secret_access_key,
        endpoint_url=s3_settings.endpoint_url,
    )
    return S3Storage(config)
