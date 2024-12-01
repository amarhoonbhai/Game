import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID"))

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
characters_collection = db["characters"]
users_collection = db["users"]

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
def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    with open("philo_game.jpeg", "rb") as image:  # Replace with your image path
        update.message.reply_photo(
            photo=image,
            caption=(
                "🎮 Welcome to **Philo Game Bot**! 🎉\n\n"
                "🌟 Explore the world of rare characters:\n"
                "🌱 Common, ✨ Elite, 🌟 Rare, 🔥 Legendary\n\n"
                "💡 Use /help to learn more about commands and gameplay!"
            ),
            parse_mode="Markdown",
        )
    keyboard = [
        [InlineKeyboardButton("Developer", url="https://t.me/TechPiro")],
        [InlineKeyboardButton("Source Code", url="https://t.me/TechPiroBots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("👇 Explore more:", reply_markup=reply_markup)


def help_command(update: Update, context: CallbackContext) -> None:
    """Handles the /help command."""
    update.message.reply_text(
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


def stats(update: Update, context: CallbackContext) -> None:
    """Handles the /stats command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID and user_id not in sudo_users:
        update.message.reply_text("❌ You are not authorized to use this command.")
        return

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        update.message.reply_text("You have no stats yet!")
        return
    coins = user.get("coins", 0)
    update.message.reply_text(f"📊 **Your Stats:**\nCoins: {coins}")


def upload(update: Update, context: CallbackContext) -> None:
    """Handles the /upload command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID and user_id not in sudo_users:
        update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        update.message.reply_text("⚠️ Usage: /upload <character_name> <image_url> [rarity]")
        return

    character_name = context.args[0]
    image_url = context.args[1]
    rarity = context.args[2].capitalize() if len(context.args) > 2 else None

    if rarity and rarity not in RARITY_EMOJIS:
        update.message.reply_text("⚠️ Invalid rarity! Use one of: Common, Elite, Rare, Legendary.")
        return

    if not rarity:
        rarity = random_rarity()

    characters_collection.insert_one({
        "name": character_name.lower(),
        "rarity": rarity,
        "image_url": image_url,
    })
    update.message.reply_text(
        f"✅ Character {character_name} uploaded successfully!\n"
        f"Rarity: {RARITY_EMOJIS[rarity]} {rarity}"
    )


def levels(update: Update, context: CallbackContext) -> None:
    """Handles the /levels command."""
    top_users = list(users_collection.find().sort("coins", -1).limit(10))
    leaderboard = "\n".join(
        [f"{i+1}. {user['username'] or user['user_id']} - {user['coins']} coins"
         for i, user in enumerate(top_users)]
    )
    update.message.reply_text(f"🏆 **Top 10 Users:**\n{leaderboard}")


def addsudo(update: Update, context: CallbackContext) -> None:
    """Handles the /addsudo command."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) < 1:
        update.message.reply_text("⚠️ Usage: /addsudo <user_id>")
        return

    sudo_user = int(context.args[0])
    sudo_users.append(sudo_user)
    update.message.reply_text(f"✅ User {sudo_user} added as sudo user.")


def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles user messages and the character guessing game."""
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    message_count[user_id] = message_count.get(user_id, 0) + 1

    if message_count[user_id] % 5 == 0:
        character = characters_collection.aggregate([{"$sample": {"size": 1}}])
        character = next(character, None)
        if character:
            rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
            current_characters[user_id] = character["name"]
            update.message.reply_photo(
                photo=character["image_url"],
                caption=f"🎉 **Guess the Character!**\nRarity: {rarity_emoji} {character['rarity']}",
                parse_mode="Markdown",
            )
        else:
            update.message.reply_text("⚠️ No characters available in the database.")
        return

    guess = update.message.text.lower()
    if user_id in current_characters and guess == current_characters[user_id]:
        current_characters.pop(user_id)
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            users_collection.insert_one({"user_id": user_id, "username": username, "coins": 100})
        else:
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"username": username}, "$inc": {"coins": 100}}
            )
        update.message.reply_text("🎉 Correct! You earned 100 coins! 💰")


def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("upload", upload))
    dispatcher.add_handler(CommandHandler("levels", levels))
    dispatcher.add_handler(CommandHandler("addsudo", addsudo))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
