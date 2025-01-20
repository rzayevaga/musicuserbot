import asyncio
import os
from aiohttp import ClientSession
from yt_dlp import YoutubeDL
from pyrogram import Client, filters
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputAudioStream, InputVideoStream
from pytgcalls.types.stream import StreamAudioEnded, StreamVideoEnded
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant

## aiteknoloji ~ @rzayevaga // 

# Bot məlumatları
API_ID = ""
API_HASH = ""
SESSION_STRING = ""
BOT_OWNER_ID = 1924693109  # Bot sahibinin Telegram ID-sini daxil edin

# Pyrogram və PyTgCalls müştəriləri
app = Client("MusicUserBot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
pytgcalls = PyTgCalls(app)

queue = []  # Mahnılar üçün növbə
is_video_playing = False

# Sahib yoxlama funksiyası
def is_owner(func):
    async def wrapper(client, message: Message):
        if message.from_user and message.from_user.id == BOT_OWNER_ID:
            return await func(client, message)
        await message.reply("Bu əmrdən yalnız bot sahibi istifadə edə bilər.")
    return wrapper

# YouTube-dan media məlumatlarını əldə etmək və yükləmək
async def download_media(query, is_video=False):
    ydl_opts = {
        "format": "bestvideo+bestaudio" if is_video else "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }] if not is_video else None,
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "quiet": True,
    }
    loop = asyncio.get_event_loop()
    with YoutubeDL(ydl_opts) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=True))
        return {
            "file_path": os.path.abspath(ydl.prepare_filename(info)),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
        }

# Səsli söhbətə qoşulma
@pytgcalls.on_stream_end()
async def on_stream_end(update):
    global is_video_playing
    if isinstance(update, (StreamAudioEnded, StreamVideoEnded)):
        if queue:
            next_track = queue.pop(0)
            await pytgcalls.change_stream(
                update.chat_id,
                InputAudioStream(next_track["file_path"]) if not is_video_playing else InputVideoStream(next_track["file_path"]),
            )
        else:
            await pytgcalls.leave_group_call(update.chat_id)
            is_video_playing = False

# Mahnı və ya videonu oynatma funksiyası
async def play_media(chat_id, media_info, requested_by, is_video=False):
    global is_video_playing
    file_path = media_info["file_path"]
    title = media_info["title"]
    duration = media_info["duration"]
    thumbnail = media_info["thumbnail"]

    # Şəkil və məlumat göndərilməsi
    await app.send_photo(
        chat_id,
        photo=thumbnail,
        caption=(
            f"🎶 **Oynadılır:** {title}\n"
            f"⏱ **Müddət:** {duration // 60}:{duration % 60:02d}\n"
            f"👤 **İstəyən:** {requested_by.mention if requested_by else 'Naməlum'}"
        ),
    )

    # Səsli söhbətə qoşulma
    if not is_video_playing:
        await pytgcalls.join_group_call(
            chat_id,
            InputAudioStream(file_path) if not is_video else InputVideoStream(file_path),
        )
        is_video_playing = is_video
    else:
        queue.append(media_info)

# /play əmri
@app.on_message(filters.command("play"))
async def play(_, message: Message):
    global is_video_playing
    chat_id = message.chat.id
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    if not query and not message.reply_to_message:
        await message.reply("Zəhmət olmasa bir YouTube linki, mahnı adı və ya audio fayl cavablayın.")
        return

    if query:
        await message.reply("Mahnı yüklənir, bir az gözləyin...")
        try:
            media_info = await download_media(query)
        except Exception as e:
            await message.reply(f"Mahnını yükləmək mümkün olmadı: {e}")
            return
    elif message.reply_to_message.audio:
        media_info = {
            "file_path": await message.reply_to_message.download(),
            "title": message.reply_to_message.audio.title or "Naməlum",
            "duration": message.reply_to_message.audio.duration or 0,
            "thumbnail": None,
        }
    else:
        await message.reply("Düzgün formatda məlumat daxil edin.")
        return

    if not queue:
        await play_media(chat_id, media_info, message.from_user)
    else:
        queue.append(media_info)
        await message.reply("Mahnı növbəyə əlavə edildi.")

# /vplay əmri
@app.on_message(filters.command("vplay"))
async def vplay(_, message: Message):
    global is_video_playing
    chat_id = message.chat.id
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    if not query and not message.reply_to_message:
        await message.reply("Zəhmət olmasa bir YouTube linki və ya video adı daxil edin.")
        return

    await message.reply("Video yüklənir, bir az gözləyin...")
    try:
        media_info = await download_media(query, is_video=True)
    except Exception as e:
        await message.reply(f"Videonu yükləmək mümkün olmadı: {e}")
        return

    if not queue:
        await play_media(chat_id, media_info, message.from_user, is_video=True)
    else:
        queue.append(media_info)
        await message.reply("Video növbəyə əlavə edildi.")

# /queue əmri
@app.on_message(filters.command("queue"))
async def show_queue(_, message):
    if not queue:
        await message.reply("Növbədə mahnı yoxdur.")
    else:
        queue_list = "\n".join([f"{i+1}. {track['title']}" for i, track in enumerate(queue)])
        await message.reply(f"Növbədəki mahnılar:\n\n{queue_list}")

# /skip əmri
@app.on_message(filters.command("skip"))
async def skip(_, message):
    chat_id = message.chat.id
    if queue:
        next_track = queue.pop(0)
        await pytgcalls.change_stream(
            chat_id,
            InputAudioStream(next_track["file_path"]) if not is_video_playing else InputVideoStream(next_track["file_path"]),
        )
        await message.reply("Növbəti oynadılır.")
    else:
        await pytgcalls.leave_group_call(chat_id)
        await message.reply("Növbədə mahnı yoxdur.")

# /end əmri
@app.on_message(filters.command("end"))
async def end(_, message):
    global is_video_playing
    chat_id = message.chat.id
    await pytgcalls.leave_group_call(chat_id)
    queue.clear()
    is_video_playing = False
    await message.reply("Səsli söhbət bitirildi.")

# Bot sahibinə məxsus xüsusi əmrlər
@app.on_message(filters.command("ping"))
@is_owner
async def ping(_, message):
    start_time = asyncio.get_event_loop().time()
    sent_message = await message.reply("Ping yoxlanılır...")
    end_time = asyncio.get_event_loop().time()
    latency = (end_time - start_time) * 1000
    await sent_message.edit_text(f"🏓 **Ping:** `{latency:.2f}ms`")

@app.on_message(filters.command("reklam"))
@is_owner
async def reklam(_, message: Message):
    # Şəxsi söhbətə mesaj göndərir
    await message.reply("Reklam mesajı şəxsi söhbətə göndərildi!")

@app.on_message(filters.command("qreklam"))
@is_owner
async def qreklam(_, message: Message):
    # Qruplara mesaj göndərir
    if message.chat.type == "private":
        await message.reply("Bu əmri yalnız qruplarda istifadə edə bilərsiniz!")
    else:
        await message.reply("Reklam mesajı qruplara göndərildi!")

@app.on_message(filters.command("greklam"))
@is_owner
async def greklam(_, message: Message):
    # Şəxsi söhbətlərə və qruplara mesaj göndərir
    if message.chat.type == "private":
        await message.reply("Reklam mesajı şəxsi söhbətə göndərildi!")
    else:
        await message.reply("Reklam mesajı qruplara göndərildi!")

@app.on_message(filters.command("gban"))
@is_owner
async def gban(_, message: Message):
    # Global ban əmri
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        try:
            # Bütün qruplarda həmin istifadəçini qadağa qoyur
            for chat in await app.get_chat_members(message.chat.id):
                if chat.user.id == user_id:
                    await app.kick_chat_member(message.chat.id, user_id)
            await message.reply(f"İstifadəçi {user_id} global olaraq banlandı!")
        except Exception as e:
            await message.reply(f"Xəta baş verdi: {e}")
    else:
        await message.reply("Zəhmət olmasa banlamaq istədiyiniz istifadəçini seçin!")

@app.on_message(filters.command("ungban"))
@is_owner
async def ungban(_, message: Message):
    # Global banı açır
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        try:
            # Bütün qruplarda həmin istifadəçini unblock edir
            for chat in await app.get_chat_members(message.chat.id):
                if chat.user.id == user_id:
                    await app.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"İstifadəçi {user_id} global banından azad edildi!")
        except Exception as e:
            await message.reply(f"Xəta baş verdi: {e}")
    else:
        await message.reply("Zəhmət olmasa unblock etmək istədiyiniz istifadəçini seçin!")

@app.on_message(filters.command("info"))
@is_owner
async def info(_, message):
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else None
    if user_id:
        user = await app.get_users(user_id)
        await message.reply(f"İstifadəçi haqqında məlumat:\n\n"
                            f"İstifadəçi Adı: {user.username}\n"
                            f"Adı: {user.first_name}\n"
                            f"Soyadı: {user.last_name}\n"
                            f"İD: {user.id}\n"
                            f"Bio: {user.bio or 'Yoxdur'}")
    else:
        await message.reply("Yanıt verdiyiniz mesajda istifadəçi olmalıdır.")

# Botun işə salınması
async def main():
    os.makedirs("downloads", exist_ok=True)
    await app.start()
    await pytgcalls.start()
    print("✅ Bot işləyir..")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
