import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

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

# Define levels based on coins
levels = [
    (0, "Beginner 🌟"),
    (1000, "Novice 🥉"),
    (5000, "Intermediate 🥈"),
    (10000, "Advanced 🥇"),
    (20000, "Expert 🌟"),
    (50000, "Master 🏆"),
]

# Global variable to track the current character
current_character = None


# Helper Functions
def assign_random_rarity():
    """Assign a random rarity."""
    return random.choice(list(rarities.values()))


def get_user_level(coins):
    """Determine the level based on coins."""
    for coin_threshold, level in reversed(levels):
        if coins >= coin_threshold:
            return level
    return "Unranked"


def update_user_coins(user_id, first_name, last_name, coins):
    """Update user's coins."""
    user = users_collection.find_one({"user_id": user_id})
    if user:
        users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": coins}})
    else:
        users_collection.insert_one({"user_id": user_id, "first_name": first_name, "last_name": last_name, "coins": coins})


def add_character_to_db(name, rarity, image_url):
    """Add a character to the database."""
    character = {"name": name, "rarity": rarity, "image_url": image_url}
    characters_collection.insert_one(character)


def is_sudo_user(user_id):
    """Check if the user is a sudo user or the owner."""
    return user_id == OWNER_ID or sudo_users_collection.find_one({"user_id": user_id})


async def show_random_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Show a random character in the chat."""
    global current_character
    try:
        current_character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
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
    except Exception as e:
        await context.bot.send_message(chat_id, "⚠️ No characters in the database! Add some using /upload.")
        print(f"Error showing random character: {e}")


# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome the user and start the bot."""
    await update.message.reply_text(
        "🎉 **Welcome to the Anime Guessing Bot!** 🎉\n\n"
        "⦿ **Type a character's name to guess and earn coins!** 💰\n\n"
        "✨ Have fun playing! ✨",
        parse_mode=ParseMode.MARKDOWN
    )
    await show_random_character(context, update.effective_chat.id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the help message."""
    await update.message.reply_text(
        "📜 **Commands** 📜\n\n"
        "⦿ /start - Start the bot and display a random character.\n"
        "⦿ /help - Show this help menu.\n"
        "⦿ /upload - Upload a character (owner/sudo only).\n"
        "⦿ /stats - Check bot statistics.\n"
        "⦿ /levels - View the top 10 players and their levels.\n"
        "⦿ /addsudo - Add a sudo user (owner only).\n"
        "⦿ /rmsudo - Remove a sudo user (owner only).\n"
        "✨ **How to Play** ✨\n\n"
        "1️⃣ A random character will appear.\n"
        "2️⃣ Guess their name by typing it in the chat.\n"
        "3️⃣ Earn coins for correct guesses!\n\n"
        "💡 **Enjoy the game and aim for the top leaderboard!** 💡",
        parse_mode=ParseMode.MARKDOWN
    )


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow the owner or sudo users to upload a character."""
    user_id = update.message.from_user.id
    if is_sudo_user(user_id):
        try:
            image_url = context.args[0]
            name = context.args[1] if len(context.args) > 1 else f"Character {characters_collection.count_documents({}) + 1}"
            rarity = context.args[2].lower() if len(context.args) > 2 else None

            rarity = rarities.get(rarity, assign_random_rarity())

            add_character_to_db(name, rarity, image_url)

            await update.message.reply_text(
                f"✅ **Character added successfully!** ✅\n\n"
                f"⦿ **Name:** {name}\n"
                f"⦿ **Rarity:** {rarity}",
                parse_mode=ParseMode.MARKDOWN
            )
        except IndexError:
            await update.message.reply_text("⚠️ Usage: /upload <image_url> [name] [rarity]", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


async def add_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a sudo user (owner only)."""
    if update.message.from_user.id == OWNER_ID:
        try:
            user_id = int(context.args[0])
            sudo_users_collection.insert_one({"user_id": user_id})
            await update.message.reply_text(f"✅ **User {user_id} added to sudo list.** ✅", parse_mode=ParseMode.MARKDOWN)
        except IndexError:
            await update.message.reply_text("⚠️ Usage: /addsudo <user_id>", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


async def remove_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a sudo user (owner only)."""
    if update.message.from_user.id == OWNER_ID:
        try:
            user_id = int(context.args[0])
            sudo_users_collection.delete_one({"user_id": user_id})
            await update.message.reply_text(f"✅ **User {user_id} removed from sudo list.** ✅", parse_mode=ParseMode.MARKDOWN)
        except IndexError:
            await update.message.reply_text("⚠️ Usage: /rmsudo <user_id>", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.** ❌", parse_mode=ParseMode.MARKDOWN)


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


async def levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the top 10 users with their levels and coins."""
    top_users = users_collection.find().sort("coins", -1).limit(10)
    leaderboard = "🏆 **Top 10 Players and Levels** 🏆\n\n"
    buttons = []

    if top_users:
        for i, user in enumerate(top_users, start=1):
            first_name = user.get("first_name", "Unknown")
            last_name = user.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip()
            coins = user.get("coins", 0)
            level = get_user_level(coins)
            leaderboard += f"{i}. **{full_name}**\n   ⦿ **Level:** {level}\n   ⦿ **Coins:** {coins}\n\n"
            buttons.append([InlineKeyboardButton(f"{i}. {full_name}", callback_data=f"details_{user['user_id']}")])
    else:
        leaderboard = "⚠️ No users have earned coins yet. Be the first to play and get on the leaderboard!"

    await update.message.reply_text(leaderboard, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(buttons))


async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user guesses."""
    global current_character
    if not current_character:
        return

    user_id = update.message.from_user.id
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name or ""
    guess = update.message.text.strip().lower()
    character_name = current_character["name"].lower()

    if guess in character_name:
        update_user_coins(user_id, first_name, last_name, 1000)
        await update.message.reply_text(
            f"🎉 **Correct!** You guessed **{current_character['name']}**.\n"
            f"💰 **You earned 1000 coins!**",
            parse_mode=ParseMode.MARKDOWN
        )
        await show_random_character(context, update.effective_chat.id)
    else:
        await update.message.reply_text("❌ **Wrong guess! Try again!**", parse_mode=ParseMode.MARKDOWN)


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("addsudo", add_sudo))
    application.add_handler(CommandHandler("rmsudo", remove_sudo))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("levels", levels))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess_handler))

    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()
