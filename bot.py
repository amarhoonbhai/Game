import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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

# Define rarity levels
rarities = {
    "common": "Common 🌱",
    "elite": "Elite ✨",
    "rare": "Rare 🌟",
    "legendary": "Legendary 🌠"
}

# Global variable to track the current character
current_character = None


# Helper Functions
def assign_random_rarity():
    """Assign a random rarity."""
    return random.choice(list(rarities.values()))


def add_character_to_db(name, rarity, image_url):
    """Add a character to MongoDB."""
    character = {"name": name, "rarity": rarity, "image_url": image_url}
    characters_collection.insert_one(character)
    return character


def update_user_coins(user_id, user_name, coins):
    """Update user's coins."""
    user = users_collection.find_one({"user_id": user_id})
    if user:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": coins}})
    else:
        users_collection.insert_one({"user_id": user_id, "name": user_name, "coins": coins})


def show_random_character(context: CallbackContext, chat_id: int):
    """Show a random character in the chat."""
    global current_character
    current_character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    context.bot.send_photo(
        chat_id=chat_id,
        photo=current_character["image_url"],
        caption=(
            f"📢 **Guess the Character!** 📢\n\n"
            f"⦿ **Rarity:** {current_character['rarity']}\n\n"
            "🔥 **Can you guess their name? Type it in the chat!** 🔥"
        ),
        parse_mode=ParseMode.MARKDOWN
    )


def is_sudo_user(user_id):
    """Check if a user is an owner or a sudo user."""
    return user_id == OWNER_ID or sudo_users_collection.find_one({"user_id": user_id}) is not None


# Command: /upload
def upload(update: Update, context: CallbackContext):
    """Allow the owner or sudo users to upload a character."""
    user_id = update.message.from_user.id
    if is_sudo_user(user_id):
        try:
            image_url = context.args[0]
            name = context.args[1] if len(context.args) > 1 else f"Character {characters_collection.count_documents({}) + 1}"
            rarity = context.args[2].lower() if len(context.args) > 2 else None

            # Validate rarity or assign random
            rarity = rarities.get(rarity, assign_random_rarity())

            # Add character to MongoDB
            add_character_to_db(name, rarity, image_url)

            # Confirm success
            update.message.reply_text(
                f"✅ **Character added successfully!** ✅\n\n"
                f"⦿ **Name:** {name}\n"
                f"⦿ **Rarity:** {rarity}",
                parse_mode=ParseMode.MARKDOWN
            )
        except IndexError:
            update.message.reply_text("⚠️ Usage: /upload <image_url> [name] [rarity]", parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


# Command: /addsudo
def addsudo(update: Update, context: CallbackContext):
    """Add a sudo user (owner only)."""
    if update.message.from_user.id == OWNER_ID:
        try:
            user_id = int(context.args[0])
            sudo_users_collection.insert_one({"user_id": user_id})
            update.message.reply_text(f"✅ **User {user_id} added to sudo list.** ✅", parse_mode=ParseMode.MARKDOWN)
        except IndexError:
            update.message.reply_text("⚠️ Usage: /addsudo <user_id>", parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


# Command: /rmsudo
def rmsudo(update: Update, context: CallbackContext):
    """Remove a sudo user (owner only)."""
    if update.message.from_user.id == OWNER_ID:
        try:
            user_id = int(context.args[0])
            sudo_users_collection.delete_one({"user_id": user_id})
            update.message.reply_text(f"✅ **User {user_id} removed from sudo list.** ✅", parse_mode=ParseMode.MARKDOWN)
        except IndexError:
            update.message.reply_text("⚠️ Usage: /rmsudo <user_id>", parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


# Command: /start
def start(update: Update, context: CallbackContext):
    """Welcome the user and start the bot."""
    update.message.reply_text(
        "🎉 **Welcome to the Anime Guessing Bot!** 🎉\n\n"
        "⦿ **Type a character's name to guess and earn coins!** 💰\n\n"
        "✨ Have fun playing! ✨",
        parse_mode=ParseMode.MARKDOWN
    )
    # Show the first random character
    show_random_character(context, update.effective_chat.id)


# Command: /help
def help_command(update: Update, context: CallbackContext):
    """Show the help message."""
    update.message.reply_text(
        "📜 **Commands** 📜\n\n"
        "⦿ /start - Start the bot and display a random character.\n"
        "⦿ /help - Show this help menu.\n"
        "⦿ /upload - Upload a character (owner/sudo only).\n"
        "⦿ /stats - Check bot statistics.\n"
        "⦿ /level - View the top 10 players.\n"
        "⦿ /addsudo - Add a sudo user (owner only).\n"
        "⦿ /rmsudo - Remove a sudo user (owner only).\n\n"
        "✨ **How to Play** ✨\n\n"
        "1️⃣ A random character will appear.\n"
        "2️⃣ Guess their name by typing it in the chat.\n"
        "3️⃣ Earn coins for correct guesses!\n\n"
        "💡 **Enjoy the game and aim for the top leaderboard!** 💡",
        parse_mode=ParseMode.MARKDOWN
    )


# Command: /stats
def stats(update: Update, context: CallbackContext):
    """Show bot stats."""
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_coins = sum(user["coins"] for user in users_collection.find())

    update.message.reply_text(
        f"📊 **Bot Stats** 📊\n\n"
        f"⦿ **Total Users:** {total_users}\n"
        f"⦿ **Total Characters:** {total_characters}\n"
        f"⦿ **Total Coins Earned:** {total_coins}\n\n"
        f"✨ Thank you for playing and supporting the bot! ✨",
        parse_mode=ParseMode.MARKDOWN
    )


# Command: /level
def level(update: Update, context: CallbackContext):
    """Show the top 10 players."""
    top_users = users_collection.find().sort("coins", -1).limit(10)
    leaderboard = "🏆 **Top 10 Players** 🏆\n\n"
    for i, user in enumerate(top_users, start=1):
        leaderboard += f"⦿ {i}. **{user['name']}** - 💰 {user['coins']} coins\n"
    update.message.reply_text(leaderboard, parse_mode=ParseMode.MARKDOWN)


# Guess Handler
def guess_handler(update: Update, context: CallbackContext):
    """Handle user guesses."""
    global current_character
    if not current_character:
        return

    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name
    guess = update.message.text.strip().lower()
    character_name = current_character["name"].lower()

    if guess in character_name:
        # Correct guess
        update_user_coins(user_id, user_name, 1000)
        update.message.reply_text(
            f"🎉 **Correct!** You guessed **{current_character['name']}**.\n"
            f"💰 **You earned 1000 coins!**",
            parse_mode=ParseMode.MARKDOWN
        )
        # Show the next character
        show_random_character(context, update.effective_chat.id)
    else:
        # Incorrect guess
        update.message.reply_text("❌ **Wrong guess! Try again!**", parse_mode=ParseMode.MARKDOWN)


# Main Function
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("upload", upload))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("level", level))
    dp.add_handler(CommandHandler("addsudo", addsudo))
    dp.add_handler(CommandHandler("rmsudo", rmsudo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))

    # Start the Bot
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
