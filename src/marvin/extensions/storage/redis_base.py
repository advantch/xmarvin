from typing import Optional

try:
    from walrus import Database
except (ImportError, ModuleNotFoundError):
    pass


class RedisBase:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        self.redis_client = None
        self.connection_params = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
            "decode_responses": True,
        }

    def connect(self):
        try:
            self.redis_client = Database(**self.connection_params)
            self.redis_client.ping()
            print("Successfully connected to Redis")
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")

    def disconnect(self):
        if self.redis_client:
            self.redis_client.close()

    # You can keep the async methods if needed, using asyncio
    async def connect_async(self):
        import asyncio

        return await asyncio.to_thread(self.connect)

    async def disconnect_async(self):
        import asyncio

        return await asyncio.to_thread(self.disconnect)
