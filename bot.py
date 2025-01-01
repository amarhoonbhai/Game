import os
import random
import logging
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ------------------------------
# Environment Setup
# ------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with your channel ID

# ------------------------------
# Database Setup
# ------------------------------

client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# ------------------------------
# Constants
# ------------------------------

RARITIES = [
    ("Common 🌱", 60),
    ("Uncommon 🌟", 20),
    ("Rare 🌠", 10),
    ("Epic 🌌", 5),
    ("Legendary 🏆", 3),
    ("Mythical 🔥", 2),
]

# ------------------------------
# Logging Setup
# ------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ------------------------------
# Global Variables
# ------------------------------

character_cache = []
current_character = None
user_message_count = Counter()

# ------------------------------
# Game Class
# ------------------------------

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
        return "Common 🌱"

    @staticmethod
    def fetch_random_character():
        global character_cache
        if not character_cache:
            character_cache = list(
                characters_collection.aggregate([{"$sample": {"size": 10}}])
            )
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
                {
                    "user_id": user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "balance": 0,
                    "streak": 0,
                }
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

# ------------------------------
# Command Handlers
# ------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 **Welcome to the Anime Guessing Bot!** 🎮\n\n"
        "🕹️ **How to Play:**\n"
        "➤ A random anime character will be shown.\n"
        "➤ Guess their name to earn rewards!\n\n"
        "💰 **Rewards:**\n"
        "➤ Earn $10 for each correct guess.\n"
        "➤ Get bonus rewards for streaks!\n\n"
        "🔥 **Let's start the game! Good luck!** 🔥",
        parse_mode=ParseMode.MARKDOWN,
    )
    await show_random_character(context, update.effective_chat.id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 **Bot Commands:** 📚\n"
        "/start - Start the game\n"
        "/help - Show this help message\n"
        "/upload - Upload a new character (Admin Only)\n"
        "/currency - Show top players by balance\n"
        "/addsudo - Add a sudo user (Owner Only)\n"
        "/broadcast - Broadcast a message (Owner Only)\n"
        "/stats - Show bot statistics",
        parse_mode=ParseMode.MARKDOWN,
    )


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (Game.is_owner(user_id) or sudo_users_collection.find_one({"user_id": user_id})):
        await update.message.reply_text("❌ Unauthorized.", parse_mode=ParseMode.MARKDOWN)
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /upload <image_url> <character_name>")
        return

    image_url, character_name = context.args[0], " ".join(context.args[1:])
    rarity = Game.assign_rarity()
    characters_collection.insert_one({
        "name": character_name,
        "rarity": rarity,
        "image_url": image_url,
    })
    await update.message.reply_text(f"✅ Character **{character_name}** uploaded successfully!")


async def addsudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not Game.is_owner(user_id):
        await update.message.reply_text("❌ Unauthorized.", parse_mode=ParseMode.MARKDOWN)
        return
    target_user_id = int(context.args[0])
    Game.add_sudo_user(target_user_id)
    await update.message.reply_text(f"✅ User **{target_user_id}** added as sudo user.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users, total_characters = Game.get_bot_stats()
    await update.message.reply_text(
        f"📊 **Bot Statistics:**\n"
        f"👥 **Total Users:** {total_users}\n"
        f"🎭 **Total Characters:** {total_characters}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = Game.get_user_currency()
    leaderboard_text = "\n".join(
        f"{i+1}. {user.get('first_name', 'Unknown')} - 💰 {user.get('balance', 0)}"
        for i, user in enumerate(leaderboard)
    )
    await update.message.reply_text(f"🏆 **Top Players:**\n{leaderboard_text}")


# ------------------------------
# Main Function
# ------------------------------

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("currency", currency))
    application.add_handler(CommandHandler("addsudo", addsudo))
    application.add_handler(CommandHandler("stats", stats))

    application.run_polling()


if __name__ == "__main__":
    main()
