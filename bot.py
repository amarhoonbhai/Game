import os
import random
import logging
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io

# 🝮︎︎︎︎︎︎︎ Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with your channel ID

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

# 🝮︎︎︎︎︎︎︎ Game state
character_cache = []
current_character = None
user_message_count = Counter()


class Game:
    """🝮︎︎︎︎︎︎︎ Game logic and utility methods."""

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
        total_weight = sum(weight for _, weight in rarities)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in rarities:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "🝮︎︎︎︎︎︎︎ Common 🌱"

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
        sudo_users_collection.insert_one({"user_id": user_id})

    @staticmethod
    def get_user_currency():
        return list(users_collection.find().sort("balance", -1).limit(10))


# ✅ 🝮︎︎︎︎︎︎︎ Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🝮︎︎︎︎︎︎︎ **Welcome to the Anime Guessing Bot!** 🝮︎︎︎︎︎︎︎\n\n"
        "📝 **How to Play:**\n"
        "⦿ A random anime character will be shown.\n"
        "⦿ Guess their name to earn rewards.\n\n"
        "💰 **Rewards:**\n"
        "⦿ 🝮︎︎︎︎︎︎︎ $10 for each correct guess.\n"
        "⦿ 🝮︎︎︎︎︎︎︎ Bonus rewards for streaks!\n\n"
        "🛠️ **Commands:** Use `/help` to explore all features.",
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🝮︎︎︎︎︎︎︎ **Command Menu 🝮︎︎︎︎︎︎︎**\n\n"
        "🟢 **General Commands:**\n"
        "  - 🝮︎︎︎︎︎︎︎ `/start` → Start the bot\n"
        "  - 🝮︎︎︎︎︎︎︎ `/profile` → View your profile\n"
        "  - 🝮︎︎︎︎︎︎︎ `/currency` → Top users by balance\n"
        "  - 🝮︎︎︎︎︎︎︎ `/stats` → Bot statistics\n\n"
        "🛡️ **Admin Commands:**\n"
        "  - 🝮︎︎︎︎︎︎︎ `/addsudo` → Add a sudo user\n"
        "  - 🝮︎︎︎︎︎︎︎ `/broadcast` → Broadcast a message\n"
        "  - 🝮︎︎︎︎︎︎︎ `/upload` → Upload a new character",
        parse_mode=ParseMode.MARKDOWN
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        await update.message.reply_text("❌ **🝮︎︎︎︎︎︎︎ Profile not found. Start interacting to build your profile!**")
        return

    balance = user.get("balance", 0)
    streak = user.get("streak", 0)

    await update.message.reply_text(
        f"🝮︎︎︎︎︎︎︎ **Your Profile:**\n\n"
        f"👤 **Name:** {first_name}\n"
        f"💰 **Currency:** ${balance}\n"
        f"🔥 **Streak:** {streak}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users, total_characters = Game.get_bot_stats()
    await update.message.reply_text(
        f"🝮︎︎︎︎︎︎︎ **Bot Statistics:**\n\n"
        f"👥 **Total Users:** {total_users}\n"
        f"🎭 **Total Characters:** {total_characters}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Game.is_owner(update.effective_user.id):
        await update.message.reply_text("❌ **🝮︎︎︎︎︎︎︎ You are not authorized to use this command!**")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ **🝮︎︎︎︎︎︎︎ Usage:** `/broadcast <message>`")
        return

    message = " ".join(context.args)
    failed = 0
    for user in users_collection.find({}, {"user_id": 1}):
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message)
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send message to {user['user_id']}: {e}")
    
    await update.message.reply_text(
        f"✅ **🝮︎︎︎︎︎︎︎ Broadcast completed.**\n"
        f"❌ **Failed Deliveries:** {failed}"
    )


# ✅ 🝮︎︎︎︎︎︎︎ Main Function
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("currency", stats))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("addsudo", Game.add_sudo_user))
    application.add_handler(CommandHandler("broadcast", broadcast))

    application.run_polling()


if __name__ == "__main__":
    main()
