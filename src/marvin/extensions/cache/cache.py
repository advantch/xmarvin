from ucache import MemoryCache, SqliteCache

m = MemoryCache()


class MemoryCachex:
    def __init__(self):
        self.cache = lambda: m

    def get(self, key):
        return self.cache().get(key)

    def set(self, key, value):
        self.cache().set(key, value)


mem_cache = MemoryCachex()
sqlite_cache = SqliteCache(filename="marvin.db")
