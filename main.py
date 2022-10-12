import logging
from logging import config
from typing import Optional

from aiogram import Bot, Dispatcher, executor
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)
from aiogram.utils.markdown import quote_html

from settings import (BOT_TOKEN, CONNECTED_CHATS_IDS, MAX_DIMENSION,
                      MAX_DURATION, MAX_SIZE, log_config, strings)
# from utils import check_dimensions, check_duration, check_size, lang, get_kb


config.dictConfig(log_config)
logging.info(f"connected chats ids is {CONNECTED_CHATS_IDS}")
logging.info(f"{MAX_SIZE=}, {MAX_DURATION=}, {MAX_DIMENSION=}")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


def lang(message: Message) -> str:
    if message.from_user.language_code and message.from_user.language_code in strings.keys():
        return message.from_user.language_code
    return "en"


async def get_chat_title(chat_id: str) -> Optional[str]:
    try:
        return (await bot.get_chat(chat_id)).title
    except:
        return None

async def check_size(message: Message) -> bool:
    if message.video.file_size >= MAX_SIZE:
        print(message.video.file_size, MAX_SIZE)
        await bot.send_message(message.chat.id, strings[lang(message)]["size_handler"], parse_mode="Markdown")
    return message.video.file_size < MAX_SIZE


async def check_duration(message: Message) -> bool:
    if message.video.duration > MAX_DURATION:
        await bot.send_message(message.chat.id, strings[lang(message)]["duration_handler"], parse_mode="Markdown")
    return message.video.duration <= MAX_DURATION


async def check_dimensions(message: Message) -> bool:
    if abs(message.video.height - message.video.width) not in {0, 1}:
        await bot.send_message(message.chat.id, strings[lang(message)]["not_square"])
        return False
    if message.video.height > MAX_DIMENSION or message.video.width > MAX_DIMENSION:
        print(message.video.height, message.video.width)
        await bot.send_message(message.chat.id, strings[lang(message)]["dimensions_handler"])
        return False
    return True


async def get_kb(user_id: int) -> Optional[InlineKeyboardMarkup]:
    # TODO user_id
    if CONNECTED_CHATS_IDS:
        kb = InlineKeyboardMarkup()
        for chat_id in CONNECTED_CHATS_IDS:
            logging.info(f"{chat_id=} get keyboard")
            chat_name = await get_chat_title(chat_id) or str(chat_id)
            kb.add(InlineKeyboardButton(chat_name, callback_data="send-{}".format(chat_id)))
        return kb


@dp.callback_query_handler(lambda call: True)
async def callback_buttons(call: CallbackQuery) -> None:
    if call.message and call.data:
        if call.data.startswith("send-"):
            send_chat_id = call.data.replace("send-", "")
            data = call.message.video_note.file_id
            try:
                m = await bot.send_video_note(chat_id=send_chat_id, video_note=data)
                logging.info(f"video sended to {send_chat_id=}.")
            except Exception as e:
                logging.error("Error sending videonote", e)
                m = None
            # TODO: Localization
            if isinstance(m, Message):
                await bot.answer_callback_query(call.id, "Sended ✅")
            else:
                await bot.answer_callback_query(call.id, "Error ❌")


@dp.message_handler(commands=["start"])
async def welcome(message: Message) -> None:
    await bot.send_message(
        message.chat.id,
        strings[lang(message)]["start"].format(quote_html(message.from_user.first_name),
        "https://telegram.org/update"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@dp.message_handler(content_types=["video", "document", "animation"])
async def converting(message: Message) -> None:
    if message.content_type == "video":
        if await check_size(message) and await check_dimensions(message) and await check_duration(message):
            try:
                await bot.send_chat_action(message.chat.id, "record_video_note")
                videonote = await bot.download_file_by_id(message.video.file_id)
                if message.video.height < MAX_DIMENSION:
                    logging.info(f"{message.chat.id} - resized video note sended")
                    sent_note = await bot.send_video_note(message.chat.id, videonote, length=message.video.width)
                else:
                    logging.info(f"{message.chat.id} - video note sended")
                    sent_note = await bot.send_video_note(message.chat.id, videonote)
                if sent_note.content_type != "video_note":
                    await bot.send_message(message.chat.id, strings[lang(message)]["error"])
                    try:
                        await bot.delete_message(sent_note.chat.id, sent_note.message_id)
                    except:
                        pass
                else:
                    logging.info(f"{sent_note=}")
                    kb = await get_kb(message.from_user.id)
                    if kb:
                        await bot.edit_message_reply_markup(
                            chat_id=message.chat.id, message_id=sent_note.message_id, reply_markup=kb
                        )
            except Exception as e:
                logging.exception(e)
                await bot.send_message(message.chat.id, strings[lang(message)]["error"])
        return

    elif (
        message.content_type == "animation" or message.content_type == "document" and (
            message.document.mime_type == "image/gif" or message.document.mime_type == "video/mp4"
        )
    ):
        await bot.send_message(message.chat.id, strings[lang(message)]["content_error"])
        return

    elif (message.content_type == "document" and
          message.document.mime_type == "video/webm"):
        await bot.send_message(message.chat.id, strings[lang(message)]["webm"], parse_mode="HTML")

    else:
        logging.warning(f"{message.chat.id} - content error")
        await bot.send_message(message.chat.id, strings[lang(message)]["content_error"])


@dp.message_handler(content_types=["text"])
async def text_handler(message: Message) -> None:
    if message.content_type == "text" and message.text != "/start":
        await bot.send_message(message.chat.id, strings[lang(message)]["text_handler"])


@dp.message_handler(content_types=["video_note"])
async def video_note_handler(message: Message) -> None:
    await bot.send_chat_action(message.chat.id, "upload_video")
    try:
        await bot.send_video(message.chat.id, await bot.download_file_by_id(message.video_note.file_id))
        logging.info("ACTION - send video")
    except Exception:
        logging.error(f"{message.chat.id} - video note upload error")
        await bot.send_message(message.chat.id, strings[lang(message)]["error"])


if __name__ == "__main__":
    logging.info("start polling")
    executor.start_polling(dp)
