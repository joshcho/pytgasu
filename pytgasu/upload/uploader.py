# pytgasu - Automating creation of Telegram sticker packs
# Copyright (C) 2017 Lemon Lam <almk@rmntn.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pathlib import Path
from hashlib import md5
from os import urandom
from ..constants import *

from telethon.tl.types import InputPeerUser

# it only talks to @Stickers, so just hardcode it
# invoke(ResolveUsernameRequest(username='Stickers')) returns
#   contacts.resolvedPeer = \
#       (..., users=[(..., id=429000, access_hash=9143715803499997149, username=Stickers, ...)])
_stickersbot = InputPeerUser(user_id=429000, access_hash=9143715803499997149)

__all__ = ['upload']


def upload(tc, sets, subscribe=False):
    """Talk to Stickers bot and create the sets."""
    if not sets:
        print(ERROR_NO_SET_UPLOAD)
        return

    from functools import partial
    from telethon.tl.functions.messages import InstallStickerSetRequest
    from telethon.tl.types import InputStickerSetShortName
    from telethon.tl.types.messages import StickerSetInstallResultSuccess

    send_bot_cmd = partial(_send_bot_cmd, tc)

    send_bot_cmd(msg=['/cancel', '/start'])

    for _set in sets:
        set_title, set_short_name, stickers = _set

        send_bot_cmd(msg=['/newpack', set_title])
        for index, (sticker_image, emojis) in enumerate(stickers):
            send_bot_cmd(file=sticker_image)
            send_bot_cmd(msg=emojis)
            print(NOTICE_UPLOADED % {'fn': sticker_image.name, 'cur': index + 1, 'total': len(stickers)})
        send_bot_cmd(msg=['/publish', set_short_name])
        print(NOTICE_SET_AVAILABLE % {'title': set_title, 'short_name': set_short_name})

        if subscribe:
            result = tc.invoke(
                InstallStickerSetRequest(
                    InputStickerSetShortName(short_name=set_short_name), archived=False))
            if isinstance(result, StickerSetInstallResultSuccess):
                print(NOTICE_SET_SUBSCRIBED % set_title)


def _get_random_id():
    return int.from_bytes(urandom(8), signed=True, byteorder='little')


def _send_bot_cmd(tc, msg=None, file=None):
    """
    An 'interface' to talk to @Stickers.

    :param tc: A TelegramClient
    :param msg: Bot command string(s), supply a list if you are sending multiple
    :param file: Path-like object to a file
    :return: None
    """
    def wait_for_reply():
        from telethon.tl.functions.messages import ReadHistoryRequest
        from telethon.tl.types import UpdateNewMessage
        while True:
            update = tc.updates.poll(timeout=5)
            if not update:
                continue

            if all([isinstance(update, UpdateNewMessage),
                    update.message.from_id == _stickersbot.user_id,
                    update.message.date > res.date]):
                tc.invoke(ReadHistoryRequest(peer=_stickersbot, max_id=update.message.id))

    if file:
        res = tc.send_message(entity=_stickersbot, file=str(file), force_document=True)
        wait_for_reply()
    else:
        if isinstance(msg, str):
            msg = list(msg)
        for m in msg:
            res = tc.send_message(entity=_stickersbot, message=m)
            wait_for_reply()


def _upload_file(tc, filepath):
    """
    Upload a file to Telegram cloud.
    Stolen from telethon.TelegramClient.upload_file().
    Specialised for upload sticker images.

    :param tc: A TelegramClient
    :param filepath: A path-like object
    :return: An InputFile handle.
    """
    from telethon.tl.types import InputFile
    from telethon.tl.functions.upload import SaveFilePartRequest

    file = Path(filepath)
    file_id = _get_random_id()
    file_name = file.name
    part_size_kb = 32 * 1024  # just hardcode it, every file is under 350KB anyways
    part_count = (file.stat().st_size + part_size_kb - 1) // part_size_kb
    file_hash = md5()
    with open(file, mode='rb') as f:
        for part_index in range(part_count):
            part = f.read(part_size_kb)
            tc.invoke(request=SaveFilePartRequest(file_id, part_index, part))
            file_hash.update(part)
    return InputFile(id=file_id, parts=part_count, name=file_name, md5_checksum=file_hash.hexdigest())
