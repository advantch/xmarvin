from marvin.utilities.logging import logger, pretty_log


def send_event(*args, **kwargs):
    logger.warning("send_event not available in non-django environment")
    pretty_log(*args, **kwargs)


class FakeChannelLayer:
    def group_send(self, *args, **kwargs):
        logger.warning("group_send not available in non-django environment")
        pretty_log(*args, **kwargs)


def get_channel_layer():
    return FakeChannelLayer()
