import os
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped, VideoPiped

# Logger konfiqurasiyası
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# API məlumatları
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

# Mühit dəyişənlərini yoxla
if not API_ID or not API_HASH or not SESSION_STRING:
    logger.error("API_ID, API_HASH və ya SESSION_STRING tapılmadı! Zəhmət olmasa, mühit dəyişənlərini konfiqurasiya edin.")
    exit(1)

# Pyrogram müştərisini yarat
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# PyTgCalls müştərisi
pytgcalls = PyTgCalls(app)

# Mahnı növbəsi
queues = {}

async def download_media(query: str, media_type: str = "audio"):
    """
    YouTube-dan media faylı yükləyir (audio/video).
    `cookies.txt` faylı ilə autentifikasiya dəstəklənir.
    """
    ytdl_opts = {
        "format": "bestaudio/best" if media_type == "audio" else "best",
        "outtmpl": "%(title)s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "cookiefile": "cookies.txt"  # YouTube autentifikasiyası üçün
    }

    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            info = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=True))
            file_path = ytdl.prepare_filename(info)
            return file_path, info
    except Exception as e:
        logger.error(f"Media yüklənərkən xəta: {e}")
        return None, None

@app.on_message(filters.command("play") & filters.me)
async def play_command(client: Client, message: Message):
    """
    `/play {YouTube linki və ya ad}` əmri ilə musiqi oxutmaq.
    """
    chat_id = message.chat.id
    query = " ".join(message.command[1:])

    if not query:
        await message.reply_text("❌ **Zəhmət olmasa, bir musiqi adı və ya link daxil edin!**")
        return

    await message.reply_text("🔍 **Axtarılır və yüklənir...**")

    media_file, info = await download_media(query, "audio")

    if not media_file:
        await message.reply_text("❌ **Mahnı tapılmadı və ya yüklənərkən xəta baş verdi!**")
        return

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(media_file)

    if len(queues[chat_id]) == 1:
        try:
            await pytgcalls.join_group_call(chat_id, AudioPiped(media_file))  # StreamType silindi
            await message.reply_text(f"🎵 **İfa olunur:** `{info['title']}`")
        except Exception as e:
            await message.reply_text(f"❌ Yayım zamanı xəta: {e}")

@app.on_message(filters.command("vplay") & filters.me)
async def vplay_command(client: Client, message: Message):
    """
    `/vplay {YouTube linki və ya ad}` əmri ilə video oxutmaq.
    """
    chat_id = message.chat.id
    query = " ".join(message.command[1:])

    if not query:
        await message.reply_text("❌ **Zəhmət olmasa, bir video adı və ya link daxil edin!**")
        return

    await message.reply_text("🔍 **Axtarılır və yüklənir...**")

    media_file, info = await download_media(query, "video")

    if not media_file:
        await message.reply_text("❌ **Video tapılmadı və ya yüklənərkən xəta baş verdi!**")
        return

    await pytgcalls.join_group_call(chat_id, VideoPiped(media_file))  # StreamType silindi
    await message.reply_text(f"🎬 **Video oxudulur:** `{info['title']}`")

@app.on_message(filters.command("skip") & filters.me)
async def skip_command(client: Client, message: Message):
    """
    `/skip` əmri ilə növbəti musiqiyə keçid.
    """
    chat_id = message.chat.id

    if chat_id in queues and len(queues[chat_id]) > 1:
        queues[chat_id].pop(0)
        next_track = queues[chat_id][0]
        try:
            await pytgcalls.change_stream(chat_id, AudioPiped(next_track))  # StreamType silindi
            await message.reply_text(f"🎵 **Növbəti mahnıya keçid edildi!**\nMahnı: `{next_track}`")
        except Exception as e:
            await message.reply_text(f"Növbəti mahnıya keçid zamanı xəta: {e}")
    else:
        await message.reply_text("❌ Keçid etmək üçün növbədə başqa mahnı yoxdur.")

@app.on_message(filters.command("pause") & filters.me)
async def pause_command(client: Client, message: Message):
    """
    `/pause` əmri ilə musiqini dayandırmaq.
    """
    chat_id = message.chat.id
    await pytgcalls.pause_stream(chat_id)
    await message.reply_text("⏸ **Musiqi dayandırıldı!**")

@app.on_message(filters.command("resume") & filters.me)
async def resume_command(client: Client, message: Message):
    """
    `/resume` əmri ilə dayandırılmış musiqini davam etdirmək.
    """
    chat_id = message.chat.id
    await pytgcalls.resume_stream(chat_id)
    await message.reply_text("▶️ **Musiqi davam etdirildi!**")

@app.on_message(filters.command("stop") & filters.me)
async def stop_command(client: Client, message: Message):
    """
    `/stop` əmri ilə yayımı dayandırmaq.
    """
    chat_id = message.chat.id
    await pytgcalls.leave_group_call(chat_id)
    queues.pop(chat_id, None)  # Bu qrupa aid növbəni sil
    await message.reply_text("🛑 **Yayım dayandırıldı və növbə sıfırlandı!**")

@app.on_message(filters.command("queue") & filters.me)
async def queue_command(client: Client, message: Message):
    """
    `/queue` əmri ilə musiqi növbəsini göstərmək.
    """
    chat_id = message.chat.id

    if chat_id in queues and queues[chat_id]:
        queue_list = "\n".join([f"{i+1}. `{song}`" for i, song in enumerate(queues[chat_id])])
        await message.reply_text(f"🎶 **Növbədə olan mahnılar:**\n{queue_list}")
    else:
        await message.reply_text("🚫 **Növbədə heç bir mahnı yoxdur.**")

async def main():
    await app.start()
    await pytgcalls.start()
    logger.info("🎵 Bot işə düşdü!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
