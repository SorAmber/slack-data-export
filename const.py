import logging


class ConstMeta(type):

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise TypeError(f"Can't rebind const ({name})")
        else:
            self.__setattr__(name, value)


class Const(metaclass=ConstMeta):
    # Slack App OAuth Tokens
    USER_TOKEN = "xoxp-xxxxxx"  # Your User Token
    BOT_TOKEN = "xoxb-xxxxxx"  # Your Bot Token

    # Wait time (sec) for an API call or a file download.
    # If change this value, check the rate limits of Slack APIs.
    ACCESS_WAIT = 1.2
    # Export Directory path.
    EXPORT_BASE_PATH = "./export"
    # Logging level for the logging module.
    LOG_LEVEL = logging.INFO
    # Connect and read timeouts (sec) for the requests module.
    REQUESTS_CONNECT_TIMEOUT = 3.05
    REQUESTS_READ_TIMEOUT = 60
    # Whether or not to use the User Token.
    USE_USER_TOKEN = True
    # DEV: Whether or not to export messages in a format similar to official
    # functions.
    IS_SIMILAR_TO_OFFICIAL_FORMAT = True
