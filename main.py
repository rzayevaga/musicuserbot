import os
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
import yt_dlp

# Loglama konfiqurasiyası
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mühit dəyişənləri
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

# Pyrogram client – userbot sessiyası ilə
app = Client(
    SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
)

# PyTgCalls – səsli/videolu yayım üçün
pytgcalls = PyTgCalls(app)

# Hər chat üçün növbə və əlavə konfiqurasiya
queues = {}
volume_config = {}
loop_config = {}

# Youtube və digər mənbələrdən media yükləmək üçün funksiya
async def download_media(query: str, media_type: str = "audio"):
    ytdl_opts = {
        "format": "bestaudio/best" if media_type == "audio" else "best",
        "outtmpl": "%(title)s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
    }
    try:
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            info = ytdl.extract_info(query, download=True)
            file_path = ytdl.prepare_filename(info)
        return file_path, info
    except Exception as e:
        logger.error(f"Media yüklənərkən xəta: {e}")
        return None, None

# /olay əmri – Səsli yayım üçün (audio stream)
@app.on_message(filters.command("play") & filters.me)
async def play_command(client: Client, message: Message):
    await message.reply_text("Sorğu alındı, mahnı məlumatları yoxlanılır...")

    # Əmr arqumentlərindən və ya cavab mesajından sorğunu əldə etmək
    query = " ".join(message.command[1:]) if len(message.command) > 1 else None
    if not query and message.reply_to_message:
        if message.reply_to_message.text:
            query = message.reply_to_message.text.strip()
    if not query:
        await message.reply_text("Zəhmət olmasa, mahnının adını, linkini verin və ya audio fayla cavab verin.")
        return

    media_file, info = await download_media(query, media_type="audio")
    if not media_file:
        await message.reply_text("Mahnı yüklənərkən xəta baş verdi. Linki və ya adı yenidən yoxlayın.")
        return

    chat_id = message.chat.id
    try:
        await pytgcalls.join_group_call(
            chat_id,
            AudioPiped(media_file)
        )
        queues.setdefault(chat_id, []).append(media_file)
        # Elan mesajının hazırlanması
        user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
        title = info.get("title", "Naməlum")
        duration = info.get("duration", "Naməlum")
        announcement = (
            f"❤️‍🔥🎶 Müsiqi yayım edilir\n\n"
            f"Ad: **{title}**\n"
            f"Müddət: **{duration}**\n"
            f"İstəyən: {user_mention}"
        )
        await message.reply_text(announcement, disable_web_page_preview=True)
    except Exception as e:
        await message.reply_text(f"Yayım başlayarkən xəta: {e}")

# /vplay əmri – Video yayım üçün
@app.on_message(filters.command("vplay") & filters.me)
async def vplay_command(client: Client, message: Message):
    await message.reply_text("Sorğu alındı, video məlumatları yoxlanılır...")

    query = " ".join(message.command[1:]) if len(message.command) > 1 else None
    if not query and message.reply_to_message:
        if message.reply_to_message.text:
            query = message.reply_to_message.text.strip()
    if not query:
        await message.reply_text("Zəhmət olmasa, videonun adını, linkini verin və ya video fayla cavab verin.")
        return

    media_file, info = await download_media(query, media_type="video")
    if not media_file:
        await message.reply_text("Video yüklənərkən xəta baş verdi. Linki və ya adı yenidən yoxlayın.")
        return

    chat_id = message.chat.id
    try:
        await pytgcalls.join_group_call(
            chat_id,
            VideoPiped(media_file)
        )
        queues.setdefault(chat_id, []).append(media_file)
        # Elan mesajının hazırlanması
        user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
        title = info.get("title", "Naməlum")
        duration = info.get("duration", "Naməlum")
        announcement = (
            f"❤️‍🔥📹 Video yayımı edilir\n\n"
            f"Ad: **{title}**\n"
            f"Müddət: **{duration}**\n"
            f"İstəyən: {user_mention}"
        )
        await message.reply_text(announcement, disable_web_page_preview=True)
    except Exception as e:
        await message.reply_text(f"Yayım başlayarkən xəta: {e}")

# /playlist əmri – Youtube playlistdən səsli yayım
@app.on_message(filters.command("playlist") & filters.me)
async def playlist_command(client: Client, message: Message):
    await message.reply_text("Playlist yayım üçün sorğu alındı. Məlumatlar yoxlanılır...")
    
    query = message.command[1] if len(message.command) > 1 else None
    if not query and message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    if not query:
        await message.reply_text("Zəhmət olmasa, playlist linkini verin və ya linkə cavab verin.")
        return

    ytdl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "extract_flat": True,
    }
    try:
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            info = ytdl.extract_info(query, download=False)
            entries = info.get("entries", [])
            if not entries:
                await message.reply_text("Playlist boşdur və ya səhv link verilib.")
                return
    except Exception as e:
        await message.reply_text(f"Playlist yüklənərkən xəta: {e}")
        return

    await message.reply_text(f"Playlistdə **{len(entries)}** mahnı tapıldı. İndi sıra ilə yayım başlayır...")

    chat_id = message.chat.id
    for entry in entries:
        video_url = entry.get("url")
        media_file, info_track = await download_media(video_url, media_type="audio")
        if media_file:
            queues.setdefault(chat_id, []).append(media_file)
            await message.reply_text(f"Mahnı **{info_track.get('title', 'Naməlum')}** sıraya əlavə olundu.")
        else:
            await message.reply_text(f"Mahnı yüklənərkən xəta: {video_url}")

    if queues.get(chat_id):
        try:
            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(queues[chat_id][0])
            )
            user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
            title = info.get("title", "Naməlum")
            duration = info.get("duration", "Naməlum")
            announcement = (
                f"❤️‍🔥🎶 Müsiqi yayım edilir\n\n"
                f"Ad: **{title}**\n"
                f"Müddət: **{duration}**\n"
                f"İstəyən: {user_mention}"
            )
            await message.reply_text(announcement, disable_web_page_preview=True)
        except Exception as e:
            await message.reply_text(f"Yayım başlayarkən xəta: {e}")

# /pause əmri – Cari yayımı dayandırır
@app.on_message(filters.command("pause") & filters.me)
async def pause_command(client: Client, message: Message):
    chat_id = message.chat.id
    try:
        await pytgcalls.pause_stream(chat_id)
        await message.reply_text("Cari yayım dayandırıldı (pause)!")
    except Exception as e:
        await message.reply_text(f"Dayandırarkən xəta: {e}")

# /resume əmri – Dayandırılmış yayımı davam etdirir
@app.on_message(filters.command("resume") & filters.me)
async def resume_command(client: Client, message: Message):
    chat_id = message.chat.id
    try:
        await pytgcalls.resume_stream(chat_id)
        await message.reply_text("Dayandırılmış yayım davam etdirildi (resume)!")
    except Exception as e:
        await message.reply_text(f"Davam etdirərkən xəta: {e}")

# /mute əmri – Səsin bağlanması (placeholder nümunə)
@app.on_message(filters.command("mute") & filters.me)
async def mute_command(client: Client, message: Message):
    chat_id = message.chat.id
    try:
        await message.reply_text("Səsli söhbətdə Userbotun səsi bağlandı (mute)!")
    except Exception as e:
        await message.reply_text(f"Səsi bağlayarkən xəta: {e}")

# /unmute əmri – Səsin açılması (placeholder nümunə)
@app.on_message(filters.command("unmute") & filters.me)
async def unmute_command(client: Client, message: Message):
    chat_id = message.chat.id
    try:
        await message.reply_text("Səsli söhbətdə Userbotun səsi açıldı (unmute)!")
    except Exception as e:
        await message.reply_text(f"Səsi açarkən xəta: {e}")

# /skip əmri – Növbəti mahnıya/videoya keçid edir
@app.on_message(filters.command("skip") & filters.me)
async def skip_command(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in queues and len(queues[chat_id]) > 1:
        queues[chat_id].pop(0)
        next_track = queues[chat_id][0]
        try:
            await pytgcalls.change_stream(chat_id, AudioPiped(next_track))
            await message.reply_text("Növbəti mahnıya keçid edildi!")
        except Exception as e:
            await message.reply_text(f"Növbəti mahnıya keçid zamanı xəta: {e}")
    else:
        await message.reply_text("Keçid etmək üçün növbədə başqa mahnı yoxdur.")

# /stop əmri – Yayımı dayandırır və növbəni sıfırlayır
@app.on_message(filters.command("stop") & filters.me)
async def stop_command(client: Client, message: Message):
    chat_id = message.chat.id
    try:
        await pytgcalls.leave_group_call(chat_id)
        queues[chat_id] = []
        await message.reply_text("Yayım dayandırıldı!")
    except Exception as e:
        await message.reply_text(f"Yayım dayandırılarkən xəta: {e}")

# /vol əmri – Səs səviyyəsini tənzimləyir
@app.on_message(filters.command("vol") & filters.me)
async def volume_command(client: Client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("Zəhmət olmasa, səs səviyyəsini verin. Məsələn: /vol 50")
        return
    try:
        vol = int(message.command[1])
        if vol < 1 or vol > 200:
            await message.reply_text("Səs səviyyəsi 1 ilə 200 arasında olmalıdır.")
            return
        volume_config[chat_id] = vol
        await message.reply_text(f"Səs səviyyəsi **{vol}** dərəcəsinə tənzimləndi!")
    except Exception as e:
        await message.reply_text(f"Səs səviyyəsi tənzimlənərkən xəta: {e}")

# /loop əmri – Cari mahnı/video 5 dəfə təkrar
@app.on_message(filters.command("loop") & filters.me)
async def loop_command(client: Client, message: Message):
    chat_id = message.chat.id
    loop_config[chat_id] = 5
    await message.reply_text("Mahnı/video 5 dəfə təkrar ediləcək (loop aktiv edildi)!")

# /endloop əmri – Təkrarı dayandırır
@app.on_message(filters.command("endloop") & filters.me)
async def endloop_command(client: Client, message: Message):
    chat_id = message.chat.id
    loop_config[chat_id] = 0
    await message.reply_text("Təkrar (loop) bağlandı!")

# /song əmri – Mahnını Telegrama yükləyərək göndərir
@app.on_message(filters.command("song") & filters.me)
async def song_command(client: Client, message: Message):
    await message.reply_text("Mahnı yüklənir və Telegrama göndərilir...")
    
    query = " ".join(message.command[1:]) if len(message.command) > 1 else None
    if not query:
        await message.reply_text("Zəhmət olmasa, mahnının adını və ya linkini verin.")
        return

    media_file, info = await download_media(query, media_type="audio")
    if not media_file:
        await message.reply_text("Mahnı yüklənərkən xəta baş verdi!")
        return

    await message.reply_text(f"Mahnı **{info.get('title', 'Naməlum')}** yükləndi. Göndərilir...")
    try:
        user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
        caption = (
            f"Ad: {info.get('title', 'Naməlum')}\n"
            f"Müddət: {info.get('duration', 'Naməlum')}\n"
            f"İstəyən: {user_mention}"
        )
        await message.reply_document(
            media_file,
            caption=caption,
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply_text(f"Mahnı göndərilərkən xəta: {e}")

# /video əmri – Videonu Telegrama yükləyərək göndərir
@app.on_message(filters.command("video") & filters.me)
async def video_command(client: Client, message: Message):
    await message.reply_text("Video yüklənir və Telegrama göndərilir...")
    
    query = " ".join(message.command[1:]) if len(message.command) > 1 else None
    if not query:
        await message.reply_text("Zəhmət olmasa, videonun adını və ya linkini verin.")
        return

    media_file, info = await download_media(query, media_type="video")
    if not media_file:
        await message.reply_text("Video yüklənərkən xəta baş verdi!")
        return

    await message.reply_text(f"Video **{info.get('title', 'Naməlum')}** yükləndi. Göndərilir...")
    try:
        user_mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
        caption = (
            f"Ad: {info.get('title', 'Naməlum')}\n"
            f"Müddət: {info.get('duration', 'Naməlum')}\n"
            f"İstəyən: {user_mention}"
        )
        await message.reply_document(
            media_file,
            caption=caption,
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply_text(f"Video göndərilərkən xəta: {e}")

# Əsas funksiya – app və pytgcalls-i işə salır
async def main():
    await app.start()
    await pytgcalls.start()
    logger.info("Userbot və PyTgCalls işə düşdü!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
