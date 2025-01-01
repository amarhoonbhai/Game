import os
import random
import logging
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# --- 🛠️ Environment Setup ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with your channel ID

# --- 💾 MongoDB Setup ---
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# --- 📝 Logging Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- 🎮 Game State ---
character_cache = []
current_character = None
user_message_count = Counter()

# --- 🌟 Rarities ---
RARITIES = [
    ("🌱 Common", 60),
    ("🌿 Uncommon", 20),
    ("🌟 Rare", 10),
    ("🪄 Epic", 5),
    ("🏆 Legendary", 3),
    ("🔥 Mythical", 2),
]


# --- 🧠 Game Logic ---
class Game:
    """Encapsulates game logic and utility methods."""

    @staticmethod
    def assign_rarity():
        total_weight = sum(weight for _, weight in RARITIES)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in RARITIES:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "🌱 Common"

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
                    {"$inc": {"balance": balance_increment}, "$set": {"streak": new_streak}}
                )
                return balance_increment, new_streak
            else:
                users_collection.update_one({"user_id": user_id}, {"$set": {"streak": 0}})
                return 0, 0
        else:
            users_collection.insert_one({
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "balance": 0,
                "streak": 0
            })
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

    @staticmethod
    def broadcast_message(bot, message):
        for user in users_collection.find({}, {"user_id": 1}):
            try:
                bot.send_message(
                    chat_id=user["user_id"],
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Broadcast error to {user['user_id']}: {e}")


# --- 🕹️ Handlers ---
async def show_random_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global current_character
    current_character = Game.fetch_random_character()
    if not current_character:
        current_character = {
            "name": "Unknown",
            "rarity": "Unknown",
            "image_url": "https://via.placeholder.com/500"
        }
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=current_character["image_url"],
        caption=(
            f"🎭 **Guess the Character!** 🎭\n\n"
            f"⭐ **Rarity:** {current_character['rarity']}\n"
            "💬 **Type your guess below!**"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧑‍💻 Dev Profile", url="https://t.me/PhiloWise")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 **Welcome to Anime Guessing Bot!** 🎮\n"
        "🧠 Guess anime characters to earn rewards!\n"
        "🔥 **Let's start playing!**",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    await show_random_character(context, update.effective_chat.id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ **Available Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show all commands\n"
        "/profile - Show your profile\n"
        "/stats - Show bot statistics (Owner only)\n"
        "/currency - View top players\n"
        "/upload - Add a new character (Admin only)\n"
        "/addsudo - Add sudo user (Owner only)\n"
        "/broadcast - Broadcast a message (Owner only)\n"
        "💬 **Simply type to guess a character!**"
    )


# --- 🚀 Main Application ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, show_random_character))
    application.run_polling()


if __name__ == "__main__":
    main()
