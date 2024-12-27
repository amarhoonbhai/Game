import os
import random
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from collections import defaultdict

# --- ✅ Environment Setup ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944

# --- ✅ MongoDB Setup ---
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# --- ✅ Rarity Settings ---
RARITIES = [
    ("Common 🌱", 60),
    ("Uncommon 🌿", 20),
    ("Rare 🌟", 10),
    ("Epic 🌠", 5),
    ("Legendary 🏆", 3),
    ("Mythical 🔥", 2),
]

# --- ✅ Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- ✅ Game State ---
character_cache = []
current_character = None
user_incorrect_guesses = defaultdict(int)


# --- 🛠️ Game Logic ---
class Game:
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
    def update_user_balance_and_streak(user_id, first_name, last_name):
        user = users_collection.find_one({"user_id": user_id})
        if user:
            new_streak = user.get("streak", 0) + 1
            balance_increment = 10 + (new_streak * 2)
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": balance_increment}, "$set": {"streak": new_streak}},
            )
            return balance_increment, new_streak
        else:
            users_collection.insert_one(
                {"user_id": user_id, "first_name": first_name, "last_name": last_name, "balance": 0, "streak": 0}
            )
            return 10, 1

    @staticmethod
    def is_owner(user_id):
        return user_id == OWNER_ID

    @staticmethod
    def is_admin(user_id):
        return Game.is_owner(user_id) or sudo_users_collection.find_one({"user_id": user_id})

    @staticmethod
    def get_bot_stats():
        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        return total_users, total_characters


# --- 🎯 Guess Handler ---
async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_character
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name or ""

    if not current_character:
        await show_random_character(context, update.effective_chat.id)
        return

    guess = update.message.text.strip().lower()
    character_name = current_character["name"].lower()

    if any(word in character_name for word in guess.split()):
        balance_increment, new_streak = Game.update_user_balance_and_streak(user_id, first_name, last_name)
        user_incorrect_guesses[user_id] = 0
        await update.message.reply_text(
            f"🎉 **Correct!** The character was **{current_character['name']}**.\n"
            f"💵 **You earned ${balance_increment}!**\n"
            f"🔥 **Streak: {new_streak}**",
            parse_mode=ParseMode.MARKDOWN,
        )
        await show_random_character(context, update.effective_chat.id)
    else:
        user_incorrect_guesses[user_id] += 1
        if user_incorrect_guesses[user_id] >= 3:
            user_incorrect_guesses[user_id] = 0
            await update.message.reply_text("🔄 **Switching to a new character after too many incorrect guesses!**")
            await show_random_character(context, update.effective_chat.id)


# --- 🎭 Show Random Character ---
async def show_random_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    global current_character
    current_character = Game.fetch_random_character()
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=current_character.get("image_url", "https://via.placeholder.com/500"),
        caption=(
            f"🎭 **Guess the Character!**\n"
            f"🔹 **Rarity:** {current_character.get('rarity', 'Unknown')}\n"
            f"🔍 **Type your guess in the chat!**"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


# --- 🔑 Commands ---
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users_collection.find_one({"user_id": update.effective_user.id}) or {}
    await update.message.reply_text(f"📊 **Profile:**\n💵 **Balance:** ${user.get('balance', 0)}\n🔥 **Streak:** {user.get('streak', 0)}")


async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = users_collection.find().sort("balance", -1).limit(10)
    response = "\n".join([f"{i+1}. {user['first_name']} – ${user['balance']}" for i, user in enumerate(leaderboard)])
    await update.message.reply_text(f"🏆 **Top Players:**\n{response}")


# --- 🚀 Main Bot Application ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("currency", currency))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("addsudo", addsudo))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess_handler))
    application.run_polling()


if __name__ == "__main__":
    main()
