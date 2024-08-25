from marvin.extensions.utilities.logging import logger, pretty_log
from marvin.utilities.asyncio import ExposeSyncMethodsMixin


def send_event(*args, **kwargs):
    logger.warning("send_event not available in non-django environment")
    pretty_log(*args, **kwargs)


class FakeChannelLayer(ExposeSyncMethodsMixin):
    async def group_send(self, *args, **kwargs):
        #pretty_log(*args, **kwargs)
        pass

def get_channel_layer():
    return FakeChannelLayer()
