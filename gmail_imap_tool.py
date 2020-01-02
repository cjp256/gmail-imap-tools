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
import email
from typing import List

import appdirs
from imapclient import IMAPClient


@click.group()
@click.option("--username", required=True, help="GMAIL username.")
@click.option("--password", required=True, help="GMAIL password.")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging.")
@click_config_file.configuration_option(
    config_file_name=appdirs.user_config_dir("gmail.cfg")
)
@click.pass_context
def gmail_imap_tool(ctx, username, password, debug):
    ctx.obj["USERNAME"] = username
    ctx.obj["PASSWORD"] = password
    ctx.obj["DEBUG"] = debug


@gmail_imap_tool.command()
@click.option("--folder", required=True, help="GMAIL folder to delete.")
@click.option(
    "--dry-run", required=False, default=False, help="dry-run, do not delete."
)
@click.pass_context
def delete_folder(ctx, folder: str, dry_run: bool) -> None:
    username = ctx.obj["USERNAME"]
    password = ctx.obj["PASSWORD"]
    debug = ctx.obj["DEBUG"]

    click.echo(f"Removing folder: {folder}")
    client = imap_connect(username, password)
    resp = client.select_folder(folder)
    if debug:
        print("select_folder response:", resp)

    message_ids = client.search()
    num_messages = len(message_ids)

    if click.confirm(
        f"Do you want to preview {num_messages} messages from {folder!r}?"
    ):
        preview_ids = list(set(message_ids[:128] + message_ids[-128:]))
        print_emails(client, preview_ids)

    if click.confirm(f"Do you want to delete {num_messages} messages from {folder!r}?"):
        click.echo("Setting label to Trash...")
        resp = client.set_gmail_labels(message_ids, "\\Trash")
        if debug:
            print("set_gmail_labels response:", resp)

        click.echo("Deleting messages...")
        resp = client.delete_messages(message_ids)
        if debug:
            print("delete_messages response:", resp)

        click.echo("Expunging messages...")
        resp = client.expunge()
        if debug:
            print("expunging messages response:", resp)

    client.close_folder()
    client.logout()


@gmail_imap_tool.command()
@click.pass_context
def print_folders(ctx) -> None:
    username = ctx.obj["USERNAME"]
    password = ctx.obj["PASSWORD"]
    client = imap_connect(username, password)
    click.echo("Found folders:")
    for folder in client.list_folders():
        name = folder[2]
        click.echo(f"\t{name}")
    client.logout()


def imap_connect(username: str, password: str) -> IMAPClient:
    click.echo("Connecting to GMAIL...")
    client = IMAPClient("imap.gmail.com", ssl=True)
    client.login(username, password)
    click.echo("Connected...")
    return client


def print_emails(client: IMAPClient, message_ids: List[int]) -> None:
    messages = client.fetch(message_ids, ("RFC822",))
    for message in messages.values():
        message_data = message[b"RFC822"].decode()
        message = email.message_from_string(message_data)
        print(message["subject"])


if __name__ == "__main__":
    gmail_imap_tool(obj={})
