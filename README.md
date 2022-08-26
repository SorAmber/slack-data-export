# Slack Data Export

This code exports messages of public channels, private channels, direct
messages and group messages, and downloads files exchanged in those at Slack.

## Requirements

- Python 3.x
- Slack App's Token
  - https://api.slack.com/apps

A Slack app's token is tied to the required scope.

The required scopes to run this code is as follows:

- `channels:history`, `channels:read`
- `files:read`
- `groups:history`, `groups:read`
- `im:history`, `im:read`
- `mpim:history`, `mpim:read`
- `users:read`

![the required scopes](./docs/images/slack-app-scopes.jpg)

## Usage

Rewrite the `USER_TOKEN` and `BOT_TOKEN` values in const.py to those of your
Slack app:

```python
USER_TOKEN = "xoxp-xxxxxx"  # Your User Token
BOT_TOKEN = "xoxb-xxxxxx"  # Your Bot Token
```
![the tokens](./docs/images/slack-app-tokens.jpg)

Run main.py:

```
$ python main.py
```

Export messages and files in `EXPORT_BASE_PATH` for each conversation.

### Configuring

List of configuration values in const.py:

| Name                     | Type     | Description                                         |
| ------------------------ | -------- | --------------------------------------------------- |
| ACCESS_WAIT              | float    | Wait time (sec) for an API call or a file download. |
| EXPORT_BASE_PATH         | string   | Export directory path.                              |
| LOG_LEVEL                | function | Logging level of the logging module.                |
| REQUESTS_CONNECT_TIMEOUT | float    | Connect timeout (sec) for the requests module.      |
| REQUESTS_READ_TIMEOUT    | float    | Read timeout (sec) for the requests module.         |
| USE_USER_TOKEN           | boolean  | Whether or not to use the User Token.               |

If change `ACCESS_WAIT`, check
[the rate limits](https://api.slack.com/docs/rate-limits) of Slack APIs.