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

import click
import click_config_file
from datetime import datetime
import email
import logging
from typing import List

import appdirs
from imapclient import IMAPClient


class GlobalOpts:
    username: str
    password: str
    debug: bool


@click.group()
@click.option("--username", required=True, help="GMAIL username.", prompt=True)
@click.option(
    "--password", required=True, help="GMAIL password.", prompt=True, hide_input=True
)
@click.option("--debug/--no-debug", default=False, help="Enable debug logging.")
@click_config_file.configuration_option(
    config_file_name=appdirs.user_config_dir("gmail.cfg")
)
@click.pass_context
def gmail_imap_tool(ctx: click.Context, username: str, password: str, debug: bool):
    global_opts = ctx.obj
    global_opts.username = username
    global_opts.password = password
    global_opts.debug = debug

    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


@gmail_imap_tool.command()
@click.option("--chunk-size", default=1024, help="GMAIL folder to delete.")
@click.option("--confirm/--no-confirm", default=True, help="Just do it.")
@click.option(
    "--dry-run", required=False, default=False, help="dry-run, do not delete."
)
@click.option("--folder", required=True, help="GMAIL folder to delete.")
@click.pass_context
def delete_folder(
    ctx: click.Context, chunk_size: int, confirm: bool, dry_run: bool, folder: str
) -> None:
    global_opts = ctx.obj

    click.echo(f"Removing folder: {folder}")
    client = imap_connect(global_opts.username, global_opts.password)
    resp = client.select_folder(folder)
    logging.debug("select_folder response:", resp)

    message_ids = client.search()
    num_messages = len(message_ids)

    if confirm and click.confirm(
        f"Do you want to preview {num_messages} messages from {folder!r}?"
    ):
        preview_ids = list(set(message_ids[:128] + message_ids[-128:]))
        print_emails(client, preview_ids)

    if not confirm or click.confirm(
        f"Do you want to delete {num_messages} messages from {folder!r}?"
    ):
        while len(message_ids) > 0:
            current_ids = message_ids[:chunk_size]
            click.echo(
                "[{}] Deleting {} of {} messages, {} to go...".format(
                    datetime.now(), len(current_ids), num_messages, len(message_ids)
                )
            )
            message_ids = message_ids[chunk_size:]

            logging.debug("Setting label to Trash...")
            resp = client.set_gmail_labels(current_ids, "\\Trash")
            logging.debug("set_gmail_labels response:", resp)

            logging.debug("Deleting messages...")
            resp = client.delete_messages(current_ids)
            logging.debug("delete_messages response:", resp)

        logging.info("Expunging messages...")
        client.expunge()

    client.close_folder()
    client.logout()


@gmail_imap_tool.command()
@click.pass_context
def print_folders(ctx: click.Context) -> None:
    global_opts = ctx.obj
    client = imap_connect(global_opts.username, global_opts.password)
    for folder in client.list_folders():
        name = folder[2]
        click.echo(name)
    client.logout()


def imap_connect(username: str, password: str) -> IMAPClient:
    logging.debug("Connecting to GMAIL...")
    client = IMAPClient("imap.gmail.com", ssl=True)
    client.login(username, password)
    logging.debug("Connected...")
    return client


def print_emails(client: IMAPClient, message_ids: List[int]) -> None:
    messages = client.fetch(message_ids, ("RFC822",))
    for message in messages.values():
        message_data = message[b"RFC822"]
        message = email.message_from_bytes(message_data)
        click.echo(message["subject"])


if __name__ == "__main__":
    gmail_imap_tool(obj=GlobalOpts)
