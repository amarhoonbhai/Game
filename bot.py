import os
import random
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io

# 🝮︎︎︎︎︎︎︎ Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# 🝮︎︎︎︎︎︎︎ MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# 🝮︎︎︎︎︎︎︎ Logging setup
logging.basicConfig(
    format="%(asctime)s - 🝮︎︎︎︎︎︎︎ [%(name)s] %(levelname)s → %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("🝮︎︎︎︎︎︎︎ AnimeBot")


# 🛠️ Utility Functions
class Game:
    @staticmethod
    def assign_rarity():
        rarities = [
            ("🝮︎︎︎︎︎︎︎ Common 🌱", 60),
            ("🝮︎︎︎︎︎︎︎ Uncommon 🌿", 20),
            ("🝮︎︎︎︎︎︎︎ Rare 🌟", 10),
            ("🝮︎︎︎︎︎︎︎ Epic 🌠", 5),
            ("🝮︎︎︎︎︎︎︎ Legendary 🏆", 3),
            ("🝮︎︎︎︎︎︎︎ Mythical 🔥", 2),
        ]
        choice = random.choices([r[0] for r in rarities], weights=[r[1] for r in rarities], k=1)[0]
        return choice

    @staticmethod
    def get_bot_stats():
        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        return total_users, total_characters

    @staticmethod
    def is_owner(user_id):
        return user_id == OWNER_ID

    @staticmethod
    def add_sudo_user(user_id):
        if not sudo_users_collection.find_one({"user_id": user_id}):
            sudo_users_collection.insert_one({"user_id": user_id})

    @staticmethod
    def get_user_currency():
        return list(users_collection.find({}, {"first_name": 1, "balance": 1}).sort("balance", -1).limit(10))


# ✅ 🝮︎︎︎︎︎︎︎ Command Handlers

## 🟢 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🝮︎︎︎︎︎︎︎ **Welcome to Anime Guessing Bot!** 🝮︎︎︎︎︎︎︎\n"
        "📝 **Use /help to see available commands.**",
        parse_mode=ParseMode.MARKDOWN
    )


## 🟢 /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🝮︎︎︎︎︎︎︎ **Command Menu:**\n"
        "🟢 /start - Start Bot\n"
        "🟢 /profile - View Profile\n"
        "🟢 /currency - Top 10 Users\n"
        "🟢 /stats - Bot Stats\n\n"
        "🛡️ Admin:\n"
        "🛡️ /addsudo - Add Sudo User\n"
        "🛡️ /broadcast - Broadcast Message\n"
        "🛡️ /upload - Upload Character",
        parse_mode=ParseMode.MARKDOWN
    )


## 🟢 /profile
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        await update.message.reply_text("❌ **Profile not found. Start interacting!**")
        return

    profile_photos = await context.bot.get_user_profile_photos(user_id)
    photo = profile_photos.photos[0][-1] if profile_photos.total_count > 0 else None

    profile_pic = None
    if photo:
        photo_buffer = io.BytesIO()
        await context.bot.get_file(photo.file_id).download_to_memory(photo_buffer)
        profile_pic = Image.open(photo_buffer).resize((150, 150))

    # Banner creation
    banner = Image.new("RGBA", (800, 400), (50, 50, 100, 255))
    draw = ImageDraw.Draw(banner)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 24)

    if profile_pic:
        banner.paste(profile_pic, (20, 100))

    draw.text((200, 100), f"👤 Name: {user.get('first_name', 'Unknown')}", fill="white", font=font)
    draw.text((200, 150), f"💰 Balance: ${user.get('balance', 0)}", fill="gold", font=font)
    draw.text((200, 200), f"🔥 Streak: {user.get('streak', 0)} Days", fill="orange", font=font)

    buffer = io.BytesIO()
    banner.save(buffer, format="PNG")
    buffer.seek(0)

    await update.message.reply_photo(photo=buffer, caption="🝮︎︎︎︎︎︎︎ **Your Profile 🝮︎︎︎︎︎︎︎**")


## 🛡️ /broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Game.is_owner(update.effective_user.id):
        await update.message.reply_text("❌ **Unauthorized!**")
        return

    for user in users_collection.find({}, {"user_id": 1}):
        await context.bot.send_message(chat_id=user["user_id"], text=" ".join(context.args))


## ✅ Main Function
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("addsudo", Game.add_sudo_user))
    application.run_polling()


if __name__ == "__main__":
    main()
