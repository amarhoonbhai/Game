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

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with your channel ID

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# Rarity settings
RARITIES = [
    ("Common 🌱", 60),
    ("Uncommon 🌿", 20),
    ("Rare 🌟", 10),
    ("Epic 🌠", 5),
    ("Legendary 🏆", 3),
    ("Mythical 🔥", 2),
]

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Game state
character_cache = []
current_character = None
user_message_count = Counter()


class Game:
    """Game logic and utility methods."""

    @staticmethod
    def assign_rarity():
        total_weight = sum(weight for _, weight in RARITIES)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in RARITIES:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "Common 🌱"

    @staticmethod
    def fetch_random_character():
        global character_cache
        if not character_cache:
            character_cache = list(characters_collection.aggregate([{"$sample": {"size": 10}}]))
        return character_cache.pop() if character_cache else None

    @staticmethod
    def update_user_balance_and_streak(user_id, first_name, last_name, correct_guess):
        user = users_collection.find_one({"user_id": user_id})
        if user:
            if correct_guess:
                new_streak = user.get("streak", 0) + 1
                balance_increment = 10 + (new_streak * 2)
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$inc": {"balance": balance_increment}, "$set": {"streak": new_streak}},
                )
                return balance_increment, new_streak
            else:
                users_collection.update_one({"user_id": user_id}, {"$set": {"streak": 0}})
                return 0, 0
        else:
            users_collection.insert_one(
                {"user_id": user_id, "first_name": first_name, "last_name": last_name, "balance": 0, "streak": 0}
            )
            return 0, 0

    @staticmethod
    def get_user_currency():
        return list(users_collection.find().sort("balance", -1).limit(10))

    @staticmethod
    def is_owner(user_id):
        return user_id == OWNER_ID

    @staticmethod
    def add_sudo_user(user_id):
        sudo_users_collection.insert_one({"user_id": user_id})

    @staticmethod
    def get_bot_stats():
        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        return total_users, total_characters


# ✅ Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 **Welcome to the Anime Guessing Bot!** 🎉\n\n"
        "🕹️ **How to Play:**\n"
        "⦿ Guess anime character names to earn rewards!\n\n"
        "💵 **Rewards:**\n"
        "⦿ Earn $10 for correct guesses.\n"
        "⦿ Bonus rewards for streaks!",
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 **Commands** 📜\n"
        "/start - Start the bot.\n"
        "/profile - Show your profile.\n"
        "/currency - View top balances.\n"
        "/stats - Bot statistics (owner).\n"
        "/addsudo - Add sudo user (owner).\n"
        "/broadcast - Send a global message (owner).\n"
        "/upload - Upload a new character (admin).",
        parse_mode=ParseMode.MARKDOWN,
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        await update.message.reply_text("❌ **Profile not found. Start interacting to build your profile!**")
        return

    level = user.get("level", 1)
    rank = user.get("rank", "#Unranked")
    chat_messages = user.get("chat_messages", 0)
    global_messages = user.get("global_messages", 0)
    balance = user.get("balance", 0)
    streak = user.get("streak", 0)

    base_img = Image.open("/mnt/data/IMG_20241231_222351_702.jpg")
    draw = ImageDraw.Draw(base_img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 24)

    draw.text((50, 50), f"Name: {first_name}", fill="white", font=font)
    draw.text((50, 100), f"Rank: {rank}", fill="white", font=font)
    draw.text((50, 150), f"Level: {level}", fill="white", font=font)
    draw.text((50, 200), f"Messages: {chat_messages}", fill="white", font=font)
    draw.text((50, 250), f"Global Messages: {global_messages}", fill="white", font=font)
    draw.text((50, 300), f"Currency: ${balance}", fill="white", font=font)
    draw.text((50, 350), f"Streak: {streak}", fill="white", font=font)

    buffer = io.BytesIO()
    base_img.save(buffer, format="PNG")
    buffer.seek(0)

    await update.message.reply_photo(photo=buffer, caption="🎮 **Your Profile Overview** 🎮")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users, total_characters = Game.get_bot_stats()
    await update.message.reply_text(
        f"📊 **Bot Statistics** 📊\n👤 Total Users: {total_users}\n🎭 Total Characters: {total_characters}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ✅ Main Function
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("currency", stats))
    application.add_handler(CommandHandler("addsudo", stats))
    application.add_handler(CommandHandler("broadcast", stats))
    application.add_handler(CommandHandler("upload", stats))
    application.add_handler(CommandHandler("stats", stats))
    application.run_polling()


if __name__ == "__main__":
    main()
