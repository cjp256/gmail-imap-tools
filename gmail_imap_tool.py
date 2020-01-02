#!/usr/bin/env python3
#
# Copyright (c) 2020 Chris Patterson <cjp256@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import email
import logging
from datetime import datetime
from typing import List

import appdirs
import click
import click_config_file
import click_log
from imapclient import IMAPClient

logger = logging.getLogger(__name__)
click_log.basic_config(logger)


class GlobalOpts:
    username: str
    password: str


@click.group()
@click.option("--username", required=True, help="GMAIL username.", prompt=True)
@click.option(
    "--password", required=True, help="GMAIL password.", prompt=True, hide_input=True
)
@click_log.simple_verbosity_option(logger)
@click_config_file.configuration_option(
    config_file_name=appdirs.user_config_dir("gmail.cfg")
)
@click.pass_context
def gmail_imap_tool(ctx: click.Context, username: str, password: str):
    global_opts = ctx.obj
    global_opts.username = username
    global_opts.password = password


@gmail_imap_tool.command()
@click.option("--chunk-size", default=1024, help="GMAIL folder to delete.")
@click.option("--confirm/--no-confirm", default=True, help="Just do it.")
@click.option("--folder", required=True, help="GMAIL folder to delete.")
@click.pass_context
def delete_folder(
    ctx: click.Context, chunk_size: int, confirm: bool, folder: str
) -> None:
    global_opts = ctx.obj

    logger.info(f"Removing folder {folder!r}...")
    client = imap_connect(global_opts.username, global_opts.password)

    logger.info(f"Selecting folder {folder!r}...")
    resp = client.select_folder(folder)
    logger.debug(f"select_folder response: {resp!r}")

    logger.info(f"Searching messages in folder {folder!r}...")
    message_ids = client.search()
    num_messages = len(message_ids)
    logger.info(f"Found {num_messages} in folder {folder!r}.")

    if confirm and click.confirm(
        f"Do you want to preview some of the messages from {folder!r}?"
    ):
        preview_ids = list(set(message_ids[:128] + message_ids[-128:]))
        print_emails(client, preview_ids)

    if not confirm or click.confirm(
        f"Do you want to delete {num_messages} messages from {folder!r}?"
    ):
        while len(message_ids) > 0:
            current_ids = message_ids[:chunk_size]
            logger.info(
                "[{}] Deleting {} of {} messages, {} to go...".format(
                    datetime.now(), len(current_ids), num_messages, len(message_ids)
                )
            )
            message_ids = message_ids[chunk_size:]

            logger.debug("Setting label to Trash...")
            resp = client.set_gmail_labels(current_ids, "\\Trash")
            logger.debug("set_gmail_labels response:", resp)

            logger.debug("Deleting messages...")
            resp = client.delete_messages(current_ids)
            logger.debug(f"delete_messages response: {resp!r}")

        logger.info("Expunging messages...")
        client.expunge()

    client.close_folder()
    client.logout()


@gmail_imap_tool.command()
@click.option("--confirm/--no-confirm", default=True, help="Just do it.")
@click.pass_context
def delete_empty_folders(ctx: click.Context, confirm: bool) -> None:
    global_opts = ctx.obj

    logger.info("Removing empty folders...")
    client = imap_connect(global_opts.username, global_opts.password)

    for raw_folder in list(client.list_folders()):
        folder = str(raw_folder[2])
        if len(folder) > 1:
            if folder.startswith("[Gmail]"):
                logger.info(f"Skipping GMAIL-specific folder: {folder!r}")
                continue

        logger.debug(f"Selecting folder {folder!r}...")
        try:
            print(folder)
            resp = client.select_folder(folder)
            logger.debug(f"select_folder response: {resp!r}")
        except IMAPClient.Error as error:
            logger.info(f"Skipping mailbox {folder!r} due to error: {error}")
            continue

        logger.debug(f"Searching messages in folder {folder!r}...")
        message_ids = client.search()
        num_messages = len(message_ids)
        logger.info(f"Found {num_messages} in folder {folder!r}.")

        client.close_folder()

        if num_messages > 0:
            continue

        if not confirm or click.confirm(
            f"Do you want to delete empty folder {folder!r}?"
        ):
            logger.debug(f"Deleting folder {folder!r}...")
            resp = client.delete_folder(folder)
            logger.debug(f"delete_folder response: {resp!r}")

    client.logout()


@gmail_imap_tool.command()
@click.pass_context
def print_folders(ctx: click.Context) -> None:
    global_opts = ctx.obj
    client = imap_connect(global_opts.username, global_opts.password)
    for folder in client.list_folders():
        name = folder[2]
        logger.info(name)
    client.logout()


def imap_connect(username: str, password: str) -> IMAPClient:
    logger.info("Connecting to GMAIL...")
    client = IMAPClient("imap.gmail.com", ssl=True)
    client.login(username, password)
    logger.info("Connected.")
    return client


def print_emails(client: IMAPClient, message_ids: List[int]) -> None:
    messages = client.fetch(message_ids, ("RFC822",))
    for message in messages.values():
        message_data = message[b"RFC822"]
        message = email.message_from_bytes(message_data)
        logger.info(message["subject"])


if __name__ == "__main__":
    gmail_imap_tool(obj=GlobalOpts)
