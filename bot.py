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

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client["telegram_bot"]
    characters_collection = db["characters"]
    users_collection = db["users"]
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

# Function to fetch a random character
def fetch_random_character():
    """Fetch a random character from MongoDB."""
    character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    return character


# Function to send a character to chat
async def send_character(update: Update, user_id: int):
    """Send a random character from the database to the chat."""
    character = fetch_random_character()
    rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
    current_characters[user_id] = character["name"].lower()

    await update.message.reply_photo(
        photo=character["image_url"],
        caption=(
            f"🎉 **A New Challenge Awaits!**\n\n"
            f"🌟 **Character Rarity:** {rarity_emoji}\n"
            f"🧩 **Hint:** The name starts with **'{character['name'][0].upper()}'**.\n\n"
            f"🎯 Guess the name to earn **100 coins**!"
        ),
    )
    logging.info(f"Character '{character['name']}' sent to user {user_id}.")


# Command: /start
async def start(update: Update, context: CallbackContext):
    """Handle the /start command."""
    await update.message.reply_text(
        text=(
            "🎮 **Welcome to Philo Game Bot!** 🎉\n\n"
            "🌟 **Test your detective skills and guess the characters!**\n\n"
            "🔹 **Explore Different Rarities:**\n"
            "🌱 Common, ✨ Elite, 🌟 Rare, 🔥 Legendary\n\n"
            "💡 **How to Play:**\n"
            "1️⃣ Send messages in the chat.\n"
            "2️⃣ After every 5 messages, a character will appear.\n"
            "3️⃣ Guess the character's name (or any part of it) to win **100 coins**.\n\n"
            "🔑 **Explore Commands:**\n"
            "Use /help to view all available commands.\n\n"
            "🎯 **Let the game begin!**"
        ),
        parse_mode="Markdown",
    )


# Command: /help
async def help_command(update: Update, context: CallbackContext):
    """Display help information."""
    await update.message.reply_text(
        "📜 **Commands:**\n"
        "◈ /start - Start the bot and view the welcome message\n"
        "◈ /help - Show this help message\n"
        "◈ /levels - View the leaderboard of top users\n\n"
        "💡 **Gameplay Tips:**\n"
        "🔹 Send messages in the chat to trigger character appearances.\n"
        "🔹 Guess character names (or any part of them) to earn coins.\n\n"
        "Good luck and have fun! 🎉"
    )


# Command: /levels
async def levels(update: Update, context: CallbackContext):
    """Display the leaderboard of top users."""
    top_users = list(users_collection.find().sort("coins", -1).limit(10))
    if not top_users:
        await update.message.reply_text("🚫 No users found.")
        return

    leaderboard = "\n".join(
        [
            f"◈ {i+1}. {user.get('first_name', '')} {user.get('last_name', '')} - {user.get('coins', 0)} coins"
            for i, user in enumerate(top_users)
        ]
    )
    await update.message.reply_text(f"🏆 **Top Users with Highest Coins:**\n{leaderboard}")


# Function to handle user messages
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
        # Check if any word in the user's guess matches any word in the character's name
        if any(word in character_name.split() for word in guess.split()):
            current_characters.pop(user_id)  # Remove the current character for the user
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

    # Trigger new character after every 5 messages
    if message_count[user_id] % 5 == 0:
        await send_character(update, user_id)


# Main function to run the bot
def main():
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("levels", levels))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
