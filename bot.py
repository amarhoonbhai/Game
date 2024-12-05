import os
import random
import logging
from time import time
from collections import defaultdict, Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# Enhanced rarities with probabilities
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
    """Encapsulates game logic and utility methods."""

    @staticmethod
    def assign_rarity():
        """Assign rarity based on predefined probabilities."""
        total_weight = sum(weight for _, weight in RARITIES)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in RARITIES:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "Common 🌱"  # Default fallback

    @staticmethod
    def fetch_random_character():
        """Fetch a random character, using cache if available."""
        global character_cache
        if not character_cache:
            character_cache = list(characters_collection.aggregate([{"$sample": {"size": 10}}]))
        return character_cache.pop() if character_cache else None

    @staticmethod
    def update_user_balance(user_id, first_name, last_name, balance_increment):
        """Update user balance in the database."""
        user = users_collection.find_one({"user_id": user_id})
        if user:
            users_collection.update_one({"user_id": user_id}, {"$inc": {"balance": balance_increment}})
        else:
            users_collection.insert_one(
                {"user_id": user_id, "first_name": first_name, "last_name": last_name, "balance": balance_increment}
            )

    @staticmethod
    def get_user_currency():
        """Get leaderboard for currency."""
        return list(users_collection.find().sort("balance", -1).limit(10))

    @staticmethod
    def is_sudo_user(user_id):
        """Check if a user is a sudo user or the owner."""
        return user_id == OWNER_ID or sudo_users_collection.find_one({"user_id": user_id})

    @staticmethod
    def add_sudo_user(user_id):
        """Add a user as sudo."""
        sudo_users_collection.insert_one({"user_id": user_id})

    @staticmethod
    def broadcast_message(bot, message):
        """Send a broadcast message to all users."""
        for user in users_collection.find({}, {"user_id": 1}):
            try:
                bot.send_message(chat_id=user["user_id"], text=message, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error broadcasting to {user['user_id']}: {e}")


async def show_random_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Display a random character in the chat."""
    global current_character
    current_character = Game.fetch_random_character()
    if not current_character:
        current_character = {"name": "Unknown", "rarity": "Unknown", "image_url": "https://via.placeholder.com/500"}
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=current_character["image_url"],
        caption=(
            f"📢 **Guess the Character!** 📢\n\n"
            f"⦿ **Rarity:** {current_character['rarity']}\n\n"
            "🔥 **Can you guess their name? Type it in the chat!** 🔥"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) started the bot.")
    await update.message.reply_text(
        "🎉 **Welcome to the Anime Guessing Bot!** 🎉\n\n"
        "⦿ **Type a character's name to guess and earn $10 for each correct guess!** 💵\n\n"
        "✨ Have fun playing! ✨",
        parse_mode=ParseMode.MARKDOWN
    )
    await show_random_character(context, update.effective_chat.id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📜 **Commands** 📜\n\n"
        "⦿ /start - Start the bot and display a random character.\n"
        "⦿ /help - Show this help menu.\n"
        "⦿ /upload - Upload a character (admin only).\n"
        "⦿ /stats - Check bot statistics.\n"
        "⦿ /currency - View the top 10 players by balance.\n"
        "⦿ /addsudo - Add a sudo user (owner only).\n"
        "⦿ /broadcast - Send a broadcast message (admin only).\n\n"
        "✨ **How to Play** ✨\n\n"
        "1️⃣ A random character will appear.\n"
        "2️⃣ Guess their name by typing it in the chat.\n"
        "3️⃣ Earn $10 for each correct guess!\n\n"
        "💡 **Enjoy the game and aim for the top leaderboard!** 💡",
        parse_mode=ParseMode.MARKDOWN
    )


async def add_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a sudo user (owner only)."""
    if update.effective_user.id == OWNER_ID:
        try:
            user_id = int(context.args[0])
            Game.add_sudo_user(user_id)
            await update.message.reply_text(f"✅ **User {user_id} added as sudo user.**", parse_mode=ParseMode.MARKDOWN)
        except IndexError:
            await update.message.reply_text("⚠️ Usage: /addsudo <user_id>", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.**", parse_mode=ParseMode.MARKDOWN)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a broadcast message (owner and sudo users only)."""
    user_id = update.effective_user.id
    if Game.is_sudo_user(user_id):
        try:
            message = " ".join(context.args)
            Game.broadcast_message(context.bot, message)
            await update.message.reply_text("✅ **Broadcast sent to all users.**", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error during broadcast: {e}")
            await update.message.reply_text("❌ **Failed to send broadcast.**", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.**", parse_mode=ParseMode.MARKDOWN)


async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user guesses."""
    global current_character

    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name or ""
    user_message_count[user_id] += 1

    # Check if character exists
    if not current_character:
        await show_random_character(context, update.effective_chat.id)
        return

    # Compare guess
    guess = update.message.text.strip().lower()
    character_name = current_character["name"].lower()

    if guess in character_name:
        Game.update_user_balance(user_id, first_name, last_name, 10)
        await update.message.reply_text(
            f"🎉 **Correct!** You guessed **{current_character['name']}**.\n"
            f"💵 **You earned $10!**",
            parse_mode=ParseMode.MARKDOWN
        )
        user_message_count[user_id] = 0
        await show_random_character(context, update.effective_chat.id)
    elif user_message_count[user_id] >= 5:
        user_message_count[user_id] = 0
        await show_random_character(context, update.effective_chat.id)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics."""
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    await update.message.reply_text(
        f"📊 **Bot Statistics** 📊\n\n"
        f"⦿ **Total Users:** {total_users}\n"
        f"⦿ **Total Characters:** {total_characters}\n",
        parse_mode=ParseMode.MARKDOWN
    )


async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the currency leaderboard."""
    leaderboard = Game.get_user_currency()
    leaderboard_text = "💰 **Top 10 Players by Balance** 💰\n\n"

    if leaderboard:
        for i, user in enumerate(leaderboard, start=1):
            first_name = user.get("first_name", "Unknown")
            last_name = user.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            balance = user.get("balance", 0)
            leaderboard_text += f"{i}. **{full_name}**\n   ⦿ **Balance:** ${balance}\n\n"
    else:
        leaderboard_text = "⚠️ No players have earned any balance yet. Be the first to play!"

    await update.message.reply_text(leaderboard_text, parse_mode=ParseMode.MARKDOWN)


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("currency", currency))
    application.add_handler(CommandHandler("addsudo", add_sudo))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess_handler))

    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()
