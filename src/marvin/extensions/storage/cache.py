class SimpleCache:
    """
    Simple in memory cache for the run
    Replace with a redis cache
    """
    cache = {}

    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value

    @classmethod
    def create(cls):
        return cls()


cache = SimpleCache()