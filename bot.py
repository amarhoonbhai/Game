import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID"))
MESSAGE_THRESHOLD = int(os.getenv("MESSAGE_THRESHOLD", 5))
CHARACTER_CHANNEL_ID = os.getenv("CHARACTER_CHANNEL_ID")

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client["telegram_bot"]
    characters_collection = db["characters"]
    users_collection = db["users"]
    sudo_users_collection = db["sudo_users"]
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    exit()

# Globals
message_count = {}
current_characters = {}

# Define rarity with emojis
RARITY_EMOJIS = {
    "Common": "◈ 🌱 Common",
    "Elite": "◈ ✨ Elite",
    "Rare": "◈ 🌟 Rare",
    "Legendary": "◈ 🔥 Legendary",
}


# Fetch a random character
def fetch_random_character():
    """Fetch a random character from MongoDB."""
    character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    return character


# Send a character to the chat
async def send_character(update: Update, user_id: int):
    """Send a random character from the database to the chat."""
    character = fetch_random_character()
    rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
    current_characters[user_id] = character["name"].lower()

    await update.message.reply_photo(
        photo=character["image_url"],
        caption=(
            f"🎉 **Time for a Challenge!**\n\n"
            f"🌟 **Character Rarity:** {rarity_emoji}\n"
            f"🧩 **Clue:** The name begins with **'{character['name'][0].upper()}'**.\n\n"
            f"🤔 **Can you guess who it is?**\n\n"
            f"🎯 Guess correctly and earn **100 coins!**"
        ),
    )
    logging.info(f"Character '{character['name']}' sent to user {user_id}.")


# /start Command
async def start(update: Update, context: CallbackContext):
    """Handle the /start command."""
    await update.message.reply_text(
        text=(
            "🎮 **Welcome to Philo Game Bot!** 🎉\n\n"
            "🌟 **Test your detective skills and guess the characters!**\n\n"
            "🔹 **Explore Different Rarities:**\n"
            "◈ 🌱 Common, ◈ ✨ Elite, ◈ 🌟 Rare, ◈ 🔥 Legendary\n\n"
            "💡 **How to Play:**\n"
            f"1️⃣ Send messages in the chat.\n"
            f"2️⃣ After every {MESSAGE_THRESHOLD} messages, a character will appear.\n"
            "3️⃣ Guess the character's name (or any part of it) to win **100 coins**.\n\n"
            "🔑 **Explore Commands:**\n"
            "Use /help to view all available commands.\n\n"
            "🎯 **Let the game begin!**"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("◈ Developer - @TechPiro", url="https://t.me/TechPiro")],
                [InlineKeyboardButton("◈ Source Code - @TechPiroBots", url="https://t.me/TechPiroBots")],
            ]
        ),
    )


# Handle messages for gameplay
async def handle_message(update: Update, context: CallbackContext):
    """Handle user messages and game logic."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    first_name = update.message.from_user.first_name or ""
    last_name = update.message.from_user.last_name or ""

    # Increment message count
    message_count[user_id] = message_count.get(user_id, 0) + 1
    logging.info(f"Message count for user {user_id}: {message_count[user_id]}")

    # Check if the user is guessing
    guess = update.message.text.lower()
    if user_id in current_characters:
        character_name = current_characters[user_id]
        if any(word in character_name.split() for word in guess.split()):
            current_characters.pop(user_id)
            users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {"username": username, "first_name": first_name, "last_name": last_name},
                    "$inc": {"coins": 100},
                },
                upsert=True,
            )
            await update.message.reply_text(
                f"🎉 **Correct Guess! You've earned 100 coins!** 💰\n"
                f"🔹 The correct name was: **{character_name.title()}**"
            )
            await send_character(update, user_id)  # Immediately send another character
            return

    # Trigger new character after MESSAGE_THRESHOLD messages
    if message_count[user_id] % MESSAGE_THRESHOLD == 0:
        await send_character(update, user_id)


# Main function to run the bot
async def main():
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    
