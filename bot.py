import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

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
    "Common": "🌱",
    "Elite": "✨",
    "Rare": "🌟",
    "Legendary": "🔥",
}
RARITY_PROBABILITIES = [("Common", 50), ("Elite", 30), ("Rare", 15), ("Legendary", 5)]


def random_rarity():
    """Choose a rarity based on probabilities."""
    choices, weights = zip(*RARITY_PROBABILITIES)
    return random.choices(choices, weights=weights, k=1)[0]


# Commands
async def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    with open("philo_game.jpeg", "rb") as image:  # Replace with your image path
        await update.message.reply_photo(
            photo=image,
            caption=(
                "🎮 Welcome to **Philo Game Bot**! 🎉\n\n"
                "🌟 Explore the world of rare characters:\n"
                "🌱 Common, ✨ Elite, 🌟 Rare, 🔥 Legendary\n\n"
                "💡 Use /help to learn more about commands and gameplay!"
            ),
        )
    keyboard = [
        [InlineKeyboardButton("Developer", url="https://t.me/TechPiro")],
        [InlineKeyboardButton("Source Code", url="https://t.me/TechPiroBots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👇 Explore more:", reply_markup=reply_markup)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Handles the /help command."""
    await update.message.reply_text(
        "📜 **Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/stats - View your stats (Owner & Sudo Only)\n"
        "/upload - Upload a character (Owner & Sudo Only)\n"
        "/levels - Top 10 users\n"
        "/addsudo - Add a sudo user (Owner Only)\n\n"
        "💡 **Gameplay:**\n"
        "- Characters will appear every 5 messages.\n"
        "- Guess the character's name to earn 100 coins!\n\n"
        "🌱 **Rarities**:\n"
        "- 🌱 Common\n"
        "- ✨ Elite\n"
        "- 🌟 Rare\n"
        "- 🔥 Legendary"
    )


async def stats(update: Update, context: CallbackContext) -> None:
    """Handles the /stats command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID and user_id not in sudo_users:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        await update.message.reply_text("You have no stats yet!")
        return
    coins = user.get("coins", 0)
    await update.message.reply_text(f"📊 **Your Stats:**\nCoins: {coins}")


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
        f"✅ Character {character_name} uploaded successfully!\n"
        f"Rarity: {RARITY_EMOJIS[rarity]} {rarity}"
    )


async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles user messages and the character guessing game."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Increment user's message count
    message_count[user_id] = message_count.get(user_id, 0) + 1

    # Check if the user has reached the 5-message threshold
    if message_count[user_id] % 5 == 0:
        character = characters_collection.aggregate([{"$sample": {"size": 1}}])
        character = next(character, None)
        if character:
            rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
            current_characters[user_id] = character["name"]
            await update.message.reply_photo(
                photo=character["image_url"],
                caption=f"🎉 **Guess the Character!**\nRarity: {rarity_emoji} {character['rarity']}",
            )
        else:
            await update.message.reply_text("⚠️ No characters available in the database.")
        return

    # Check if the user guessed correctly
    guess = update.message.text.lower()
    if user_id in current_characters:
        character_name = current_characters[user_id]
        if any(word in character_name.split() for word in guess.split()):
            current_characters.pop(user_id)
            user = users_collection.find_one({"user_id": user_id})
            if not user:
                users_collection.insert_one({"user_id": user_id, "username": username, "coins": 100})
            else:
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"username": username}, "$inc": {"coins": 100}}
                )
            await update.message.reply_text("🎉 Correct! You earned 100 coins! 💰")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
