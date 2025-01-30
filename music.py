import asyncio
from telethon import TelegramClient, events, Button
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
import yt_dlp
import os
from config import API_ID, API_HASH, BOT_TOKEN, ASSISTANT_PHONE

# Telegram müştəri və səsli zənglər üçün müştəri
bot = TelegramClient("music_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
assistant = TelegramClient("assistant", API_ID, API_HASH)

# PyTgCalls
pytgcalls = PyTgCalls(assistant)

# Musiqi növbəsi
queue = {}

# YouTube-dan musiqi yükləmə funksiyası
def download_audio(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        return os.path.abspath(f"downloads/{info['title']}.mp3"), info['title'], info['duration']

# /start əmri
@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    buttons = [
        [Button.inline("📜 Əmrlər", data="commands"), Button.inline("ℹ️ Haqqında", data="about")],
        [Button.url("➕ Məni qrupa əlavə et", url="https://t.me/YOUR_BOT_USERNAME?startgroup=true"),
         Button.url("🆘 Dəstək Qrupu", url="https://t.me/aitsupport")]
    ]
    await event.reply(
        "👋 **Salam!** Mən səsli söhbətdə musiqi oxudan Telegram botuyam.\n\n"
        "### ~ /// ⚕️ aiteknoloji /// ~ ###",
        buttons=buttons
    )

# Inline düymələr üçün cavab
@bot.on(events.CallbackQuery(pattern=b"commands"))
async def commands(event):
    await event.answer(
        "🎵 **Əmrlər:**\n\n"
        "🎶 /play [ad/link] - Musiqi oxut\n"
        "⏭ /skip - Növbəti musiqiyə keç\n"
        "📜 /queue - Növbəni göstər\n"
        "⏹ /end - Musiqini dayandır",
        alert=True
    )

@bot.on(events.CallbackQuery(pattern=b"about"))
async def about(event):
    await event.answer(
        "🤖 **Musiqi Bot**\n"
        "🔹 Səsli söhbətlərdə musiqi yayımlayan bot.\n"
        "🔹 YouTube-dan musiqi yükləyib oxutmaq mümkündür.\n"
        "🔹 Bütün əmrlər yalnız qruplarda işləyir.",
        alert=True
    )

# Qrupda istifadə məhdudiyyəti
def is_group(event):
    return event.is_group or event.is_channel

# /play əmri (yalnız qruplarda işləyir)
@bot.on(events.NewMessage(pattern="/play"))
async def play(event):
    if not is_group(event):
        await event.reply("⚠️ **Bu əmrdən yalnız qruplarda istifadə edə bilərsən!**")
        return

    chat_id = event.chat_id
    if event.reply_to and event.reply_to.media:
        file = await bot.download_media(event.reply_to.media, "downloads/")
        title = "Telegram Audio"
        duration = 0
    elif event.message.message.split(" ", 1)[1:]:
        query = event.message.message.split(" ", 1)[1]
        file, title, duration = download_audio(query)
    else:
        await event.reply("⚠️ **Musiqi adı, link və ya fayl göndər.**")
        return

    if chat_id not in queue:
        queue[chat_id] = []
    queue[chat_id].append((file, title, duration))

    if len(queue[chat_id]) == 1:
        await play_next(chat_id)

    buttons = [[Button.inline("⏭ Növbəti", data=f"skip_{chat_id}"), Button.inline("⏹ Dayandır", data=f"end_{chat_id}")]]
    await event.reply(f"🎵 **{title}** musiqisi əlavə olundu.", buttons=buttons)

# Musiqini oynatma funksiyası
async def play_next(chat_id):
    if chat_id not in queue or not queue[chat_id]:
        return

    file, title, duration = queue[chat_id].pop(0)
    await pytgcalls.join_group_call(chat_id, AudioPiped(file), stream_type=StreamType().pulse_stream)

    buttons = [[Button.inline("⏭ Növbəti", data=f"skip_{chat_id}"), Button.inline("⏹ Dayandır", data=f"end_{chat_id}")]]
    await bot.send_message(chat_id, f"🎶 **Oynadılır:** {title} \n🕒 **Müddət:** {duration} saniyə", buttons=buttons)

# /skip əmri (yalnız qruplarda işləyir)
@bot.on(events.NewMessage(pattern="/skip"))
@bot.on(events.CallbackQuery(pattern=b"skip_(\\d+)"))
async def skip(event):
    chat_id = int(event.pattern_match.group(1)) if hasattr(event, 'pattern_match') else event.chat_id
    if not is_group(event):
        await event.reply("⚠️ **Bu əmrdən yalnız qruplarda istifadə edə bilərsən!**")
        return

    if chat_id in queue and queue[chat_id]:
        await play_next(chat_id)
        await event.answer("⏭ Növbəti musiqiyə keçildi.", alert=True)
    else:
        await event.answer("📭 Növbədə başqa musiqi yoxdur.", alert=True)

# /queue əmri (yalnız qruplarda işləyir)
@bot.on(events.NewMessage(pattern="/queue"))
async def show_queue(event):
    if not is_group(event):
        await event.reply("⚠️ **Bu əmrdən yalnız qruplarda istifadə edə bilərsən!**")
        return

    chat_id = event.chat_id
    if chat_id in queue and queue[chat_id]:
        queue_text = "\n".join([f"🎵 {song[1]} - {song[2]} saniyə" for song in queue[chat_id]])
        await event.reply(f"📜 **Növbə:**\n{queue_text}")
    else:
        await event.reply("📭 **Növbədə musiqi yoxdur.**")

# /end əmri (yalnız qruplarda işləyir)
@bot.on(events.NewMessage(pattern="/end"))
@bot.on(events.CallbackQuery(pattern=b"end_(\\d+)"))
async def end(event):
    if not is_group(event):
        await event.reply("⚠️ **Bu əmrdən yalnız qruplarda istifadə edə bilərsən!**")
        return

    chat_id = event.chat_id
    await pytgcalls.leave_group_call(chat_id)
    queue[chat_id] = []
    await event.reply("🚫 **Musiqi dayandırıldı və köməkçi hesab səslidən ayrıldı.**")

# Botu işə sal
async def main():
    await assistant.start(phone=ASSISTANT_PHONE)
    print("✅ Bot işə düşdü!")
    await pytgcalls.start()
    await bot.run_until_disconnected()

asyncio.run(main())