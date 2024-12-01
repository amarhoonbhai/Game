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
sudo_users = []

# Rarity emojis and probabilities
RARITY_EMOJIS = {
    "Common": "◈ 🌱 Common",
    "Elite": "◈ ✨ Elite",
    "Rare": "◈ 🌟 Rare",
    "Legendary": "◈ 🔥 Legendary",
}
RARITY_PROBABILITIES = [("Common", 50), ("Elite", 30), ("Rare", 15), ("Legendary", 5)]


def random_rarity():
    """Choose a rarity based on probabilities."""
    choices, weights = zip(*RARITY_PROBABILITIES)
    return random.choices(choices, weights=weights, k=1)[0]


# Commands
async def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    await update.message.reply_text(
        text=(
            "🎮 **Welcome to Philo Game Bot!** 🎉\n\n"
            "🌟 Dive into a world of thrilling character guessing challenges! 🌟\n\n"
            "◈ **Game Overview:**\n"
            "🔹 Guess characters to earn coins.\n"
            "🔹 Compete with others to top the leaderboard.\n"
            "🔹 Discover characters of different rarities:\n"
            "  🌱 Common, ✨ Elite, 🌟 Rare, 🔥 Legendary\n\n"
            "💡 **How to Play:**\n"
            "1️⃣ Send messages in the chat.\n"
            "2️⃣ After every 5 messages, a character will appear.\n"
            "3️⃣ Guess the name of the character to earn 100 coins!\n\n"
            "🔑 **Useful Commands:**\n"
            "Use /help for more details about the commands and gameplay.\n\n"
            "Let the guessing game begin! 🎉"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("◈ Developer 👨‍💻", url="https://t.me/TechPiro")],
                [InlineKeyboardButton("◈ Source Code 🛠️", url="https://t.me/TechPiroBots")],
            ]
        ),
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    """Handles the /help command."""
    await update.message.reply_text(
        "📜 **Commands:**\n"
        "◈ /start - Start the bot and view welcome message\n"
        "◈ /help - Show this help message\n"
        "◈ /stats - View bot statistics\n"
        "◈ /upload - Upload a character (Owner & Sudo Only)\n"
        "◈ /levels - View top users with highest coins\n"
        "◈ /addsudo - Add a sudo user (Owner Only)\n\n"
        "◈ 💡 **Gameplay:**\n"
        "💬 Send messages to trigger characters.\n"
        "🎯 Guess the name and earn coins (100 coins per correct guess).\n\n"
        "◈ 🌟 **Character Rarities:**\n"
        "◈ 🌱 Common, ◈ ✨ Elite, ◈ 🌟 Rare, ◈ 🔥 Legendary"
    )


async def stats(update: Update, context: CallbackContext) -> None:
    """Handles the /stats command to show bot statistics."""
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    common_characters = characters_collection.count_documents({"rarity": "Common"})
    elite_characters = characters_collection.count_documents({"rarity": "Elite"})
    rare_characters = characters_collection.count_documents({"rarity": "Rare"})
    legendary_characters = characters_collection.count_documents({"rarity": "Legendary"})

    await update.message.reply_text(
        f"📊 **Bot Statistics:**\n"
        f"◈ 👥 Total Users: {total_users}\n"
        f"◈ 🧩 Total Characters: {total_characters}\n"
        f"◈ 🌱 Common Characters: {common_characters}\n"
        f"◈ ✨ Elite Characters: {elite_characters}\n"
        f"◈ 🌟 Rare Characters: {rare_characters}\n"
        f"◈ 🔥 Legendary Characters: {legendary_characters}"
    )


async def upload(update: Update, context: CallbackContext) -> None:
    """Handles the /upload command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID and user_id not in sudo_users:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /upload <character_name> <image_url> [rarity]")
        return

    character_name = context.args[0]
    image_url = context.args[1]
    rarity = context.args[2].capitalize() if len(context.args) > 2 else None

    if rarity and rarity not in RARITY_EMOJIS:
        await update.message.reply_text("⚠️ Invalid rarity! Use one of: Common, Elite, Rare, Legendary.")
        return

    if not rarity:
        rarity = random_rarity()

    characters_collection.insert_one({
        "name": character_name.lower(),
        "rarity": rarity,
        "image_url": image_url,
    })

    await update.message.reply_text(
        f"✅ **Character Uploaded!**\n"
        f"◈ 🧩 Name: {character_name}\n"
        f"◈ 🌟 Rarity: {RARITY_EMOJIS[rarity]}"
    )


async def levels(update: Update, context: CallbackContext) -> None:
    """Handles the /levels command."""
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


async def addsudo(update: Update, context: CallbackContext) -> None:
    """Handles the /addsudo command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: /addsudo <user_id>")
        return

    sudo_user = int(context.args[0])
    sudo_users.append(sudo_user)
    await update.message.reply_text(f"✅ User {sudo_user} added as sudo user.")


async def send_character(update: Update, user_id: int):
    """Fetches and sends a new character."""
    character = characters_collection.aggregate([{"$sample": {"size": 1}}])
    character = next(character, None)
    if character:
        rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
        current_characters[user_id] = character["name"]
        await update.message.reply_photo(
            photo=character["image_url"],
            caption=(
                f"🎉 **A New Challenge Awaits!**\n\n"
                f"🌟 **Character Rarity:** {rarity_emoji}\n"
                f"🎯 **Your Task:** Guess the character's name to win 100 coins!"
            ),
        )


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles user messages and the character guessing game."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "User"
    first_name = update.message.from_user.first_name or ""
    last_name = update.message.from_user.last_name or ""

    # Increment user's message count
    message_count[user_id] = message_count.get(user_id, 0) + 1

    # Check if the user guessed correctly
    guess = update.message.text.lower()
    if user_id in current_characters:
        character_name = current_characters[user_id]
        if any(word in character_name.split() for word in guess.split()):
            current_characters.pop(user_id)
            user = users_collection.find_one({"user_id": user_id})
            if not user:
                users_collection.insert_one(
                    {"user_id": user_id, "username": username, "first_name": first_name, "last_name": last_name, "coins": 100}
                )
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {"username": username, "first_name": first_name, "last_name": last_name},
                        "$inc": {"coins": 100},
                    },
                )
            await update.message.reply_text("🎉 **Correct Guess!** You earned 100 coins! 💰")
            await send_character(update, user_id)  # Send the next character immediately
            return

    # Trigger character after 5 messages
    if message_count[user_id] % 5 == 0:
        await send_character(update, user_id)


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("levels", levels))
    application.add_handler(CommandHandler("addsudo", addsudo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
