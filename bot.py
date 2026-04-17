import os
import re
import yt_dlp
import requests
import json
from instaloader import Instaloader, Post
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters, CommandHandler

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 5057151278

url_regex = re.compile(r'https?://')

loader = Instaloader()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

try:
    loader.login(IG_USERNAME, IG_PASSWORD)
    print("تم تسجيل الدخول في انستغرام ✅")
except Exception as e:
    print("فشل تسجيل الدخول ❌", e)

# ================== كلاس تحميل تيك توك ==================
class TikTokDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.api_url = "https://tikwm.com/api/"

    def get_data(self, url: str):
        try:
            response = self.session.get(self.api_url, params={"url": url}, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0:
                return data.get('data')
            return None
        except Exception as e:
            print(f"خطأ في جلب بيانات تيك توك: {e}")
            return None

    def download_file(self, file_url: str, filename: str):
        try:
            resp = self.session.get(file_url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"خطأ في تحميل ملف تيك توك: {e}")
            return False

    def get_available_formats(self, data: dict):
        formats = {}
        if data.get('play'):
            formats['mp4'] = data['play']
        if data.get('hdplay'):
            formats['hd'] = data['hdplay']
        if data.get('music'):
            formats['mp3'] = data['music']
        if data.get('cover'):
            formats['cover'] = data['cover']
        if data.get('wmplay'):
            formats['wm'] = data['wmplay']
        return formats

tiktok_downloader = TikTokDownloader()

# ================== دوال مساعدة ==================
def fix_tiktok_url(url):
    try:
        r = requests.get(url, allow_redirects=True)
        url = r.url
    except:
        pass

    if "/photo/" in url:
        url = url.replace("/photo/", "/video/")

    return url

def extract_shortcode(url):
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url)
    return match.group(1) if match else None

def get_instagram_images(url):
    shortcode = extract_shortcode(url)
    if not shortcode:
        return []

    try:
        post = Post.from_shortcode(loader.context, shortcode)
        images = []

        if post.typename == "GraphImage":
            images.append(post.url)

        elif post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if not node.is_video:
                    images.append(node.display_url)

        return images
    except:
        return []

def save_user(user_id):
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except:
        users = []

    if user_id not in users:
        users.append(user_id)
        with open("users.json", "w") as f:
            json.dump(users, f)

# ================== أوامر البوت ==================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    text = update.message.text
    message = text[len("/allm"):].strip()
    if not message:
        message = "تنبيه للكل يرجى انضمام الى قناة التحديثات من فضلكم 🤍\nhttps://t.me/SADOWNLOADER"

    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except:
        users = []

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except:
            pass

    await update.message.reply_text("تم ارسال الرسالة لجميع المستخدمين ✅")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    text = update.message.text

    if not url_regex.search(text):
        await update.message.reply_text(
            "حبيبي حط رابط تضحك عليه انت ههههههههههههههههههههههههههههههههه "
        )
        return

    url = fix_tiktok_url(text)
    context.user_data["url"] = url

    buttons = [
        [InlineKeyboardButton("📷 تحميل كصورة", callback_data="image")],
        [InlineKeyboardButton("🎧 تحميل كبصمة", callback_data="voice")],
        [InlineKeyboardButton("🎥 تحميل كفيديو", callback_data="video")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        "اختر نوع التحميل",
        reply_markup=keyboard
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("غلط بالرابط تأكد منه")
        return

    rocket = await query.message.reply_text("🚀")

    try:
        # ------------------ تحميل كصورة ------------------
        if query.data == "image":
            # محاولة انستغرام
            if "instagram.com" in url:
                images = get_instagram_images(url)
                if images:
                    await query.message.reply_text("✅")
                    for img in images:
                        await query.message.reply_photo(photo=img)
                    await rocket.delete()
                    return

            # محاولة تيك توك (صور متعددة أو صورة الغلاف)
            if "tiktok.com" in url:
                try:
                    data = tiktok_downloader.get_data(url)
                    if data:
                        images = data.get("images", [])
                        if images:
                            await query.message.reply_text("✅")
                            for img in images:
                                await query.message.reply_photo(photo=img)
                            await rocket.delete()
                            return
                        # إذا لم توجد صور متعددة، جرب صورة الغلاف
                        cover = data.get("cover")
                        if cover:
                            await query.message.reply_text("✅")
                            await query.message.reply_photo(photo=cover)
                            await rocket.delete()
                            return
                except:
                    pass

            # محاولة يوتيوب (صورة مصغرة)
            if "youtube.com" in url or "youtu.be" in url:
                try:
                    ydl_opts = {"quiet": True}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        thumb = info.get("thumbnail")
                    if thumb:
                        await query.message.reply_text("✅")
                        await query.message.reply_photo(photo=thumb)
                        await rocket.delete()
                        return
                except:
                    pass

            # إذا لم ينجح أي شيء
            await rocket.delete()
            await query.message.reply_text("ماكو صورة حمل كفيديو")
            return

        # ------------------ تحميل كفيديو ------------------
        elif query.data == "video":
            # انستغرام
            if "instagram.com" in url:
                try:
                    shortcode = extract_shortcode(url)
                    post = Post.from_shortcode(loader.context, shortcode)
                    if post.is_video:
                        await query.message.reply_text("✅")
                        await query.message.reply_video(video=post.video_url)
                        await rocket.delete()
                        return
                except:
                    pass

            # تيك توك (باستخدام الكود المخصص)
            if "tiktok.com" in url:
                try:
                    data = tiktok_downloader.get_data(url)
                    if data:
                        # نفضل HD إن وجد، وإلا العادي
                        video_url = data.get("hdplay") or data.get("play")
                        if video_url:
                            # اسم مؤقت
                            filename = "tiktok_video.mp4"
                            if tiktok_downloader.download_file(video_url, filename):
                                await query.message.reply_text("✅")
                                with open(filename, "rb") as f:
                                    await query.message.reply_video(video=f)
                                os.remove(filename)
                                await rocket.delete()
                                return
                except Exception as e:
                    print(f"خطأ في فيديو تيك توك: {e}")

            # يوتيوب أو أي رابط آخر باستخدام yt-dlp
            ydl_opts = {
                "format": "mp4",
                "outtmpl": "video.%(ext)s",
                "quiet": True,
                "nocheckcertificate": True,
                "ignoreerrors": True,
                "no_warnings": True,
                "user_agent": "Mozilla/5.0"
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                await query.message.reply_text("✅")
                with open(filename, "rb") as f:
                    await query.message.reply_video(video=f)
                os.remove(filename)
                await rocket.delete()
                return
            except:
                pass

            await rocket.delete()
            await query.message.reply_text("غلط بالرابط تاكد منه")
            return

        # ------------------ تحميل كبصمة (صوت) ------------------
        elif query.data == "voice":
            # تيك توك (تحميل الصوت مباشرة)
            if "tiktok.com" in url:
                try:
                    data = tiktok_downloader.get_data(url)
                    if data:
                        music_url = data.get("music")
                        if music_url:
                            filename = "tiktok_audio.mp3"
                            if tiktok_downloader.download_file(music_url, filename):
                                await query.message.reply_text("✅")
                                with open(filename, "rb") as f:
                                    await query.message.reply_voice(voice=f)
                                os.remove(filename)
                                await rocket.delete()
                                return
                except Exception as e:
                    print(f"خطأ في صوت تيك توك: {e}")

            # يوتيوب أو غيره باستخدام yt-dlp
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "voice.%(ext)s",
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }]
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    filename = os.path.splitext(filename)[0] + ".mp3"
                await query.message.reply_text("✅")
                with open(filename, "rb") as f:
                    await query.message.reply_voice(voice=f)
                os.remove(filename)
                await rocket.delete()
                return
            except:
                pass

            await rocket.delete()
            await query.message.reply_text("غلط بالرابط تاكد منه")

    except Exception as e:
        print(f"خطأ عام: {e}")
        await rocket.delete()
        await query.message.reply_text("غلط بالرابط تاكد منه")

# ================== تشغيل البوت ==================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("allm", broadcast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()
