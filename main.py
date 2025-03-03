import os
import asyncio
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream

# Bot Konfiqurasiyası
API_ID = int(os.getenv("API_ID", ""))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

app = Client("kellemusic", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
pytgcalls = PyTgCalls(app)

# Yükləmələr üçün qovluq yoxdursa, yaradılır
if not os.path.isdir("downloads"):
    os.makedirs("downloads")

# `cookies.txt` faylının yeri
COOKIES_FILE = "cookies.txt"

# YouTube-dan audio yükləmək üçün konfiqurasiya
YDL_OPTS = {
    'format': 'bestaudio/best',
    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True,
    'cookiefile': COOKIES_FILE,  # cookies.txt istifadə etmək üçün bu əlavə edilir
}

# YouTube axtarış funksiyası
def search_youtube(query):
    with yt_dlp.YoutubeDL({'quiet': True, 'default_search': 'ytsearch1', 'noplaylist': True, 'cookiefile': COOKIES_FILE}) as ydl:
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

# Global növbələr və aktiv səsli söhbətlər
queues = {}
active_chats = set()

def get_queue(chat_id: int) -> list:
    if chat_id not in queues:
        queues[chat_id] = []
    return queues[chat_id]

##########################################
# Səsli Yayım Əmrləri (play, skip, end)  #
##########################################

@app.on_message(filters.command("play") & filters.group)
async def play_handler(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)

    if len(message.command) < 2:
        await message.reply_text("Zəhmət olmasa, mahnı adını və ya YouTube linkini göndərin.")
        return

    query = " ".join(message.command[1:])
    url = query if "youtube.com" in query or "youtu.be" in query else search_youtube(query)

    if not url:
        await message.reply_text("❌ Heç bir nəticə tapılmadı.")
        return

    await message.reply_text(f"📥 `{query}` yüklənir, bir az gözləyin...")

    try:
        result = await asyncio.to_thread(download_audio_sync, url)
        file_path = result["file_path"]
        title = result["title"]
    except Exception as e:
        await message.reply_text(f"❌ Yükləmə zamanı xəta: {e}")
        return

    queue.append({"title": title, "file_path": file_path, "requested_by": message.from_user.mention})

    if chat_id not in active_chats:
        active_chats.add(chat_id)
        try:
            await pytgcalls.join_group_call(chat_id, MediaStream(file_path))
            await message.reply_text(f"▶️ **İndi çalır:** `{title}`")
        except Exception as e:
            await message.reply_text(f"❌ Səsli söhbətə qoşularkən xəta: {e}")
    else:
        await message.reply_text(f"✅ `{title}` növbəyə əlavə edildi.")

# Səsli yayım bitdikdə növbədən növbəti mahnıya keçid
@pytgcalls.on_stream_end()
async def on_stream_end_handler(_, update):
    chat_id = update.chat_id
    queue = get_queue(chat_id)

    if queue:
        queue.pop(0)  # Cari mahnını silirik
        if queue:
            next_song = queue[0]
            try:
                await pytgcalls.change_stream(chat_id, MediaStream(next_song["file_path"]))
                await app.send_message(chat_id, f"▶️ **İndi çalır:** `{next_song['title']}`")
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

    if len(queue) > 1:
        queue.pop(0)
        next_song = queue[0]
        try:
            await pytgcalls.change_stream(chat_id, MediaStream(next_song["file_path"]))
            await message.reply_text(f"▶️ **İndi çalır:** `{next_song['title']}`")
        except Exception as e:
            await message.reply_text(f"❌ Xəta baş verdi: {e}")
    else:
        queue.clear()
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

#####################################
# Botun İşə Salınması               #
#####################################

async def main():
    await app.start()
    await pytgcalls.start()
    print("Bot işə düşdü! 🎶")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
