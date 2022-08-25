import json
import os
import requests
from datetime import datetime
from logging import basicConfig, getLogger
from time import sleep

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from const import Const

# Initialize logger.
basicConfig(format="%(asctime)s %(name)s:%(lineno)s [%(levelname)s]: " +
            "%(message)s (%(funcName)s)")
logger = getLogger(__name__)
logger.setLevel(Const.LOG_LEVEL)


def main():
    logger.info("---- Start Slack Data Export ----")

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    client = init_webclient()
    channel_dict = create_accessible_channel_dict(client)

    for channel_id in channel_dict:
        messages = get_messages(client, channel_id)
        messages = sort_messages(messages)
        export_messages(messages, channel_id, channel_dict[channel_id], now)
        save_files(messages, channel_id, channel_dict[channel_id], now)

    logger.info("---- End Slack Data Export ----")

    return None


def init_webclient():
    client = None

    if Const.USE_USER_TOKEN:
        logger.info("Use USER TOKEN")
        client = WebClient(token=Const.USER_TOKEN)
    else:
        logger.info("Use BOT TOKEN")
        client = WebClient(token=Const.BOT_TOKEN)

    return client


def create_accessible_channel_dict(client):
    # The "(channel) id" and "(channel or user) name" pairs.
    channel_dict = {}
    channels = []
    cursor = None

    try:
        logger.debug("Call users_list (Slack API)")
        users_list = client.users_list()
        sleep(Const.ACCESS_WAIT)

        while True:
            logger.debug("Call conversations_list (Slack API)")
            conversations_list = client.conversations_list(
                types="public_channel,private_channel,mpim,im",
                cursor=cursor,
                limit=200)
            # logger.debug(conversations_list)

            channels.extend(conversations_list["channels"])
            sleep(Const.ACCESS_WAIT)

            cursor = fetch_next_cursor(conversations_list)
            if not cursor:
                break
            else:
                logger.debug("  next cursor: " + cursor)

        for channel in channels:
            if channel["is_im"]:
                # In the case a im (Direct Messages), takes "real_name" from
                # "users_list" since dose not exist in "channel".
                channel_dict[channel["id"]] = [
                    x for x in users_list["members"]
                    if x["id"] == channel["user"]
                ][0]["real_name"]
            else:
                channel_dict[channel["id"]] = channel["name"]
        logger.debug(channel_dict)

    except SlackApiError as e:
        logger.error(e)
        sleep(Const.ACCESS_WAIT)

    return channel_dict


def get_messages(client, channel_id):
    messages = []
    cursor = None

    try:
        logger.info("Get Messages of " + channel_id)

        # Stores channel's messages (other than thread's).
        while True:
            logger.debug("Call conversations_history (Slack API)")
            conversations_history = client.conversations_history(
                channel=channel_id, cursor=cursor, limit=200)
            # logger.debug(conversations_history)

            messages.extend(conversations_history["messages"])
            sleep(Const.ACCESS_WAIT)

            cursor = fetch_next_cursor(conversations_history)
            if not cursor:
                break
            else:
                logger.debug("  next cursor: " + cursor)

        # Stores thread's messages.
        # Extracts messages whose has "thread_ts" is equal to "ts".
        for parent_message in (
                x for x in messages
                if "thread_ts" in x and x["thread_ts"] == x["ts"]):

            while True:
                logger.debug("Call conversations_replies (Slack API): " +
                             parent_message["ts"])
                conversations_replies = client.conversations_replies(
                    channel=channel_id,
                    ts=parent_message["thread_ts"],
                    cursor=cursor,
                    limit=200,
                )
                # logger.debug(conversations_replies)

                # Since parent messages are also returned, excepts them.
                messages.extend([
                    x for x in conversations_replies["messages"]
                    if x["ts"] != x["thread_ts"]
                ])
                sleep(Const.ACCESS_WAIT)

                cursor = fetch_next_cursor(conversations_history)
                if not cursor:
                    break
                else:
                    logger.debug("  next cursor: " + cursor)

    except SlackApiError as e:
        logger.error(e)
        sleep(Const.ACCESS_WAIT)

    return messages


def fetch_next_cursor(api_response):
    if ("response_metadata" in api_response
            and "next_cursor" in api_response["response_metadata"]
            and api_response["response_metadata"]["next_cursor"]):

        return api_response["response_metadata"]["next_cursor"]
    else:
        return None


def save_files(messages, channel_id, channel_name, now):
    export_path = os.path.join(*[
        Const.EXPORT_BASE_PATH, now, "".join([channel_id, "_", channel_name]),
        "files"
    ])
    os.makedirs(export_path)

    logger.info("Save Files of " + channel_id)
    logger.debug("files export path : " + export_path)

    for files in (x["files"] for x in messages if "files" in x):
        # Downloads files except deleted.
        for fi in (x for x in files if x["mode"] != "tombstone"):
            logger.debug("  * Download " + fi["name"])

            try:
                response = requests.get(
                    fi["url_private"],
                    headers={"Authorization": "Bearer " + Const.USER_TOKEN},
                    timeout=(Const.REQUESTS_CONNECT_TIMEOUT,
                             Const.REQUESTS_READ_TIMEOUT))
                sleep(Const.ACCESS_WAIT)

                # If the token's scope doesn't include "files:read", this
                # request should be redirected.
                if len(response.history) != 0:
                    logger.warning("File downloads may fail.")
                    logger.warning(
                        "Check if the list of scopes includes 'files:read'.")

                # NOTE: Content-Type is often set to "binary/octet-stream"
                #       regardless of the file type, so don't "continues" even
                #       if Content-Type and mimetype mismatch.
                # if fi["mimetype"] != response.headers["Content-Type"]:
                #     logger.debug("        mimetype    : " + fi["mimetype"])
                #     logger.debug("        content-type: " +
                #                  response.headers["Content-Type"])
                #     continue

                file_path = os.path.join(
                    *[export_path, "".join([fi["id"], "_", fi["name"]])])
                with open(file_path, mode="wb") as f:
                    f.write(response.content)

            except (requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                logger.error(e)
                logger.error("url_private : " + fi["url_private"])
                sleep(Const.ACCESS_WAIT)

    return None


def sort_messages(org_messages):
    sort_messages = sorted(org_messages, key=lambda x: x["ts"])
    return sort_messages


def export_messages(messages, channel_id, channel_name, now):
    export_path = os.path.join(*[
        Const.EXPORT_BASE_PATH, now, "".join([channel_id, "_", channel_name])
    ])
    os.makedirs(export_path)

    logger.info("Save Messages of " + channel_id)
    logger.debug("messages export path : " + export_path)

    file_path = os.path.join(*[export_path, "messages.json"])
    with open(file_path, mode="wt", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    return None


if __name__ == "__main__":
    main()
