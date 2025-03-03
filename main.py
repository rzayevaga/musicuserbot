import os
import asyncio
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls.streams.input_stream import AudioPiped


# Pyrogram Client (userbot) üçün konfiqurasiya
API_ID = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
app = Client("kellemusic", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
pytgcalls = PyTgCalls(app)



# Yükləmələr üçün qovluq yoxdursa yaradılır
if not os.path.isdir("downloads"):
    os.makedirs("downloads")

# YouTube-dan audio yükləmək üçün konfiqurasiya
YDL_OPTS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
}

# YouTube-dan video yükləmək üçün konfiqurasiya
VIDEO_OPTS = {
    'format': 'best',
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
}

# Əgər cookies.txt faylı mövcuddursa, YDL_OPTS və VIDEO_OPTS-a əlavə edirik
if os.path.exists("cookies.txt"):
    YDL_OPTS["cookiefile"] = "cookies.txt"
    VIDEO_OPTS["cookiefile"] = "cookies.txt"

# YouTube-da axtarış funksiyası
def search_youtube(query, media_type="audio"):
    ydl_opts = {'quiet': True, 'default_search': 'ytsearch1', 'noplaylist': True}
    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if info.get('entries'):
            return info['entries'][0]['webpage_url']
    return None

# Synchronous audio yükləmə funksiyası
def download_audio_sync(url: str) -> dict:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        file_name = ydl.prepare_filename(info)
        if file_name.endswith(".webm") or file_name.endswith(".m4a"):
            file_name = os.path.splitext(file_name)[0] + ".mp3"
        return {"title": info.get("title", "Naməlum mahnı"), "file_path": file_name}

# Synchronous video yükləmə funksiyası
def download_video_sync(url: str) -> dict:
    with yt_dlp.YoutubeDL(VIDEO_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        file_name = ydl.prepare_filename(info)
        return {"title": info.get("title", "Naməlum video"), "file_path": file_name}


# Global növbələr və aktiv səsli söhbətlər (chat_id: növbə listi)
queues = {}
active_chats = set()

def get_queue(chat_id: int) -> list:
    if chat_id not in queues:
        queues[chat_id] = []
    return queues[chat_id]


#####################################
# Yükləmə Əmrləri (song və video)   #
#####################################

@app.on_message(filters.command("song"))
async def download_music(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Zəhmət olmasa, mahnı adını və ya YouTube linkini göndərin.")
        return

    query = " ".join(message.command[1:])
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        await message.reply_text(f"🔎 \"{query}\" axtarılır...")
        url = search_youtube(query, media_type="audio")
        if not url:
            await message.reply_text("❌ Heç bir nəticə tapılmadı.")
            return

    await message.reply_text(f"📥 {query} yüklənir, bir az gözləyin...")

    try:
        result = await asyncio.to_thread(download_audio_sync, url)
        file_name = result["file_path"]
        caption = f"🎵 Mahnı: {result['title']}\n👤 Yüklədi: {message.from_user.mention}"
        await message.reply_audio(audio=file_name, caption=caption, performer="Userbot")
        os.remove(file_name)
    except Exception as e:
        await message.reply_text(f"❌ Xəta baş verdi: {e}")

@app.on_message(filters.command(["video"], prefixes=["/", "!", "."]))
async def download_video(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Zəhmət olmasa, video adını və ya YouTube linkini göndərin.")
        return

    query = " ".join(message.command[1:])
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        await message.reply_text(f"🔎 \"{query}\" axtarılır...")
        url = search_youtube(query, media_type="video")
        if not url:
            await message.reply_text("❌ Heç bir nəticə tapılmadı.")
            return

    await message.reply_text(f"📥 {query} videosu yüklənir, bir az gözləyin...")

    try:
        result = await asyncio.to_thread(download_video_sync, url)
        file_name = result["file_path"]
        caption = f"📹 Video: {result['title']}\n👤 Yüklədi: {message.from_user.mention}"
        await message.reply_video(video=file_name, caption=caption)
        os.remove(file_name)
    except Exception as e:
        await message.reply_text(f"❌ Xəta baş verdi: {e}")

#####################################
# Səsli Yayım Əmrləri (play, skip, end, queue) #
#####################################

@app.on_message(filters.command("play") & filters.group)
async def play_handler(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)

    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("Zəhmət olmasa, mahnı adı/YouTube linki və ya musiqi faylını cavab olaraq göndərin.")
        return

    # Əgər cavab olaraq musiqi faylı göndərilibsə
    if message.reply_to_message and (message.reply_to_message.audio or message.reply_to_message.voice):
        file_path = await client.download_media(message.reply_to_message)
        title = "Telegram Audio"
    else:
        query = " ".join(message.command[1:])
        if "youtube.com" in query or "youtu.be" in query:
            url = query
        else:
            await message.reply_text(f"🔎 \"{query}\" axtarılır...")
            url = search_youtube(query)
            if not url:
                await message.reply_text("❌ Heç bir nəticə tapılmadı.")
                return
        await message.reply_text(f"📥 {query} yüklənir, bir az gözləyin...")
        try:
            result = await asyncio.to_thread(download_audio_sync, url)
            file_path = result["file_path"]
            title = result["title"]
        except Exception as e:
            await message.reply_text(f"❌ Mahnı yüklənərkən xəta baş verdi: {e}")
            return

    # Növbəyə əlavə edirik
    queue.append({"title": title, "file_path": file_path, "requested_by": message.from_user.mention})
    
    # Əgər artıq yayım başlamayıbsa, səsli söhbətə qoşulub ilk mahnını çalırıq
    if chat_id not in active_chats:
        active_chats.add(chat_id)
        try:
            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(file_path),
            )
            await message.reply_text(f"▶️ İndi çalır: {title}")
        except Exception as e:
            await message.reply_text(f"❌ Səsli söhbətə qoşularkən xəta: {e}")
    else:
        await message.reply_text(f"✅ \"{title}\" növbəyə əlavə edildi.")

# Səsli yayım bitdikdə avtomatik növbədən növbəti mahnıya keçid
@pytgcalls.on_stream_end()
async def on_stream_end_handler(_, update):
    chat_id = update.chat_id
    queue = get_queue(chat_id)
    if queue:
        # Cari mahnını növbədən çıxarırıq
        queue.pop(0)
        if queue:
            next_song = queue[0]
            try:
                await pytgcalls.change_stream(
                    chat_id,
                    AudioPiped(next_song["file_path"])
                )
                await app.send_message(chat_id, f"▶️ İndi çalır: {next_song['title']}")
            except Exception as e:
                print("Stream dəyişdirilmə xətası:", e)
        else:
            await pytgcalls.leave_group_call(chat_id)
            active_chats.discard(chat_id)
            await app.send_message(chat_id, "⏹️ Növbə bitdi, səsli söhbətdən çıxıldı.")

# Növbədən keçid (skip)
@app.on_message(filters.command("skip") & filters.group)
async def skip_handler(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if not queue:
        await message.reply_text("❌ Növbə boşdur.")
        return
    if len(queue) > 1:
        queue.pop(0)
        next_song = queue[0]
        try:
            await pytgcalls.change_stream(chat_id, AudioPiped(next_song["file_path"]))
            await message.reply_text(f"▶️ İndi çalır: {next_song['title']}")
        except Exception as e:
            await message.reply_text(f"❌ Xəta baş verdi: {e}")
    else:
        queue.pop(0)
        await pytgcalls.leave_group_call(chat_id)
        active_chats.discard(chat_id)
        await message.reply_text("⏹️ Növbə bitdi, səsli söhbətdən çıxıldı.")

# Yayımı dayandırmaq (end)
@app.on_message(filters.command("end") & filters.group)
async def end_handler(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if not queue:
        await message.reply_text("❌ Səsli söhbətdə heç bir mahnı çalınmır.")
        return
    queue.clear()
    await pytgcalls.leave_group_call(chat_id)
    active_chats.discard(chat_id)
    await message.reply_text("⏹️ Musiqi yayımı dayandırıldı.")

# Növbəni göstərmək (queue)
@app.on_message(filters.command("queue") & filters.group)
async def queue_handler(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if not queue:
        await message.reply_text("Növbə boşdur.")
        return
    text = "Növbədəki mahnılar:\n"
    for idx, song in enumerate(queue, start=1):
        text += f"{idx}. {song['title']}\n"
    await message.reply_text(text)

#####################################
# Botun İşə Salınması               #
#####################################

async def main():
    await app.start()
    await pytgcalls.start()
    print("@kellemusic bot işə düşdü ☊")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
