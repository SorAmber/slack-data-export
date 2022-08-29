import json
import os
import requests
import shutil
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
    users = get_users(client)
    channels = get_accessible_channels(client, users)

    save_users(users, now)
    save_channels(channels, now)

    for channel in channels:
        messages = get_messages(client, channel["id"])
        messages = sort_messages(messages)
        save_messages(messages, channel["name"], now)
        save_files(messages, channel["name"], now)

    archive_data(now)

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


def get_users(client):
    users = []

    try:
        logger.debug("Call users_list (Slack API)")
        users = client.users_list()["members"]
        # logger.debug(users)
        sleep(Const.ACCESS_WAIT)

    except SlackApiError as e:
        logger.error(e)
        sleep(Const.ACCESS_WAIT)

    return users


def get_accessible_channels(client, users):
    channels = []
    channels_raw = []
    cursor = None

    try:
        while True:
            logger.debug("Call conversations_list (Slack API)")
            conversations_list = client.conversations_list(
                types="public_channel,private_channel,mpim,im",
                cursor=cursor,
                limit=200)
            # logger.debug(conversations_list)

            channels_raw.extend(conversations_list["channels"])
            sleep(Const.ACCESS_WAIT)

            cursor = fetch_next_cursor(conversations_list)
            if not cursor:
                break
            else:
                logger.debug("  next cursor: " + cursor)

        # In the case a im (Direct Messages), "name" dose't exist in "channel",
        # so takes and appends "real_name" from users_list as "name".
        # And append "@" to the beginning of "name" in the case a im, to
        # distinguish from channel names.
        channels = [{
            **x,
            **{
                "name":
                "@" + [y for y in users if y["id"] == x["user"]][0]["real_name"]
            }
        } if x["is_im"] else x for x in channels_raw]

    except SlackApiError as e:
        logger.error(e)
        sleep(Const.ACCESS_WAIT)

    return channels


def save_users(users, now):
    export_path = os.path.join(*[Const.EXPORT_BASE_PATH, now])
    os.makedirs(export_path, exist_ok=True)

    logger.info("Save Users")
    logger.debug("users export path : " + export_path)

    file_path = os.path.join(*[export_path, "users.json"])
    with open(file_path, mode="wt", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    return None


def save_channels(channels, now):
    export_path = os.path.join(*[Const.EXPORT_BASE_PATH, now])
    os.makedirs(export_path, exist_ok=True)

    logger.info("Save Channels")
    logger.debug("channels export path : " + export_path)

    file_path = os.path.join(*[export_path, "channels.json"])
    with open(file_path, mode="wt", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

    return None


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


def sort_messages(org_messages):
    sort_messages = sorted(org_messages, key=lambda x: x["ts"])
    return sort_messages


def save_messages(messages, channel_name, now):
    export_path = os.path.join(*[Const.EXPORT_BASE_PATH, now, channel_name])
    os.makedirs(export_path)

    logger.info("Save Messages of " + channel_name)
    logger.debug("messages export path : " + export_path)

    if Const.SPLIT_MESSAGE_FILES:
        # Get a list of timestamps (Format YY-MM-DD) by excluding duplicate
        # timestamps in messages.
        for day_ts in {
                format_ts(x["ts"]): format_ts(x["ts"])
                for x in messages
        }.values():
            # Extract messages of "day_ts".
            day_messages = [
                x for x in messages if format_ts(x["ts"]) == day_ts
            ]

            file_path = os.path.join(
                *[export_path, "".join([day_ts, ".json"])])
            with open(file_path, mode="at", encoding="utf-8") as f:
                json.dump(day_messages, f, ensure_ascii=False, indent=2)
    else:
        file_path = os.path.join(*[export_path, "messages.json"])
        with open(file_path, mode="wt", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    return None


def format_ts(unix_time_str):
    return datetime.fromtimestamp(float(unix_time_str)).strftime("%Y-%m-%d")


def save_files(messages, channel_name, now):
    export_path = os.path.join(
        *[Const.EXPORT_BASE_PATH, now, channel_name, "files"])
    os.makedirs(export_path)

    logger.info("Save Files of " + channel_name)
    logger.debug("files export path : " + export_path)

    token = Const.USER_TOKEN if Const.USE_USER_TOKEN else Const.BOT_TOKEN

    for files in (x["files"] for x in messages if "files" in x):
        # Downloads files except deleted.
        for fi in (x for x in files if x["mode"] != "tombstone"):
            logger.debug("  * Download " + fi["name"])

            try:
                response = requests.get(
                    fi["url_private"],
                    headers={"Authorization": "Bearer " + token},
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


def archive_data(now):
    root_path = os.path.join(*[Const.EXPORT_BASE_PATH, now])

    logger.info("Archive data")

    shutil.make_archive(root_path, format='zip', root_dir=root_path)
    shutil.rmtree(root_path)

    return None


if __name__ == "__main__":
    main()
