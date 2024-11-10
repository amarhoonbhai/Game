import logging
import os
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram.error import TelegramError, BadRequest, Unauthorized

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# MongoDB connection
try:
    client = MongoClient(MONGO_URI)
    db = client['waifu_bot']
    users_collection = db['users']
    characters_collection = db['characters']
    logging.info("✅ MongoDB connected successfully.")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Helper function to safely send messages
def safe_send_message(update: Update, text: str, **kwargs) -> None:
    try:
        update.message.reply_text(text, **kwargs)
    except (TelegramError, BadRequest, Unauthorized) as e:
        logging.error(f"Failed to send message: {e}")

# /start command
def start(update: Update, context: CallbackContext) -> None:
    logging.info("Received /start command")
    welcome_message = "👋 Welcome to the Waifu Bot! Start guessing characters to earn coins and level up!"
    safe_send_message(update, welcome_message, parse_mode=ParseMode.MARKDOWN)

# /hello command to check bot activity
def hello(update: Update, context: CallbackContext) -> None:
    logging.info("Received /hello command")
    safe_send_message(update, "🤖 Bot is active and ready!")

# /help command
def help_command(update: Update, context: CallbackContext) -> None:
    logging.info("Received /help command")
    help_message = (
        "📜 *Help Menu* 📜\n\n"
        "/start - Start the bot\n"
        "/hello - Check if bot is active\n"
        "/upload - Upload a new character\n"
        "/leaderboard - View the leaderboard\n"
        "/profile - View your profile\n"
        "/stats - View bot stats (Owner only)\n"
    )
    safe_send_message(update, help_message, parse_mode=ParseMode.MARKDOWN)

# /upload command (only for character uploads by owner)
def upload(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Received /upload command from user_id={user_id}")

    if user_id != OWNER_ID:
        safe_send_message(update, "⚠️ Uploading is restricted to the owner.")
        return

    args = context.args
    if len(args) < 2:
        safe_send_message(update, "Usage: /upload <character_name> <rarity>")
        return

    character_name, rarity = args[0], args[1]
    characters_collection.insert_one({"name": character_name, "rarity": rarity})
    safe_send_message(update, f"✅ Character '{character_name}' with rarity '{rarity}' uploaded successfully!")

# /leaderboard command
def leaderboard(update: Update, context: CallbackContext) -> None:
    logging.info("Received /leaderboard command")
    top_users = list(users_collection.find().sort("level", -1).limit(10))

    if not top_users:
        safe_send_message(update, "🏆 No players on the leaderboard yet!")
        return

    leaderboard_message = "🏆 *Top Players Leaderboard* 🏆\n\n"
    for rank, user in enumerate(top_users, 1):
        leaderboard_message += f"{rank}. @{user.get('username', 'Unknown')} - Level {user['level']} 🌟\n"
    
    safe_send_message(update, leaderboard_message, parse_mode=ParseMode.MARKDOWN)

# /profile command
def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Received /profile command from user_id={user_id}")

    user = users_collection.find_one({"user_id": user_id})
    if user:
        profile_message = (
            f"👤 *{user.get('username', 'Unknown')}'s Profile*\n\n"
            f"🌟 Level: {user['level']}\n"
            f"💰 Coins: {user['coins']}\n"
        )
    else:
        profile_message = "🚫 You don't have a profile yet. Start guessing characters to level up and earn coins!"

    keyboard = [[InlineKeyboardButton("Developer - @TechPiro", url="https://t.me/TechPiro")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    safe_send_message(update, profile_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# /stats command (owner-only)
def stats(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Received /stats command from user_id={user_id}")

    if user_id != OWNER_ID:
        safe_send_message(update, "🚫 You don't have permission to access the stats.")
        return

    total_users = users_collection.count_documents({})
    avg_level = users_collection.aggregate([{"$group": {"_id": None, "avgLevel": {"$avg": "$level"}}}])
    avg_level = next(avg_level, {}).get("avgLevel", 0)

    stats_message = (
        f"📊 *Bot Statistics* 📊\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📈 Average Level: {avg_level:.2f}\n"
    )
    safe_send_message(update, stats_message, parse_mode=ParseMode.MARKDOWN)

# Handle character guesses
def handle_guess(update: Update, context: CallbackContext) -> None:
    guess = update.message.text.strip()
    logging.info(f"Received guess: '{guess}' from user_id={update.message.from_user.id}")
    character = characters_collection.find_one({"name": guess})

    if character:
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "Unknown"
        user = users_collection.find_one({"user_id": user_id})

        if not user:
            user = {"user_id": user_id, "username": username, "level": 1, "coins": 0}
            users_collection.insert_one(user)
            logging.info(f"New user profile created for user_id={user_id}")

        users_collection.update_one({"user_id": user_id}, {"$inc": {"level": 1, "coins": 10}})
        safe_send_message(update, f"🎉 Correct! You guessed '{character['name']}'! Level up! +10 coins.")
    else:
        safe_send_message(update, "❌ Incorrect guess. Try again!")

# Main function to start the bot
def main():
    logging.info("Starting bot...")
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("hello", hello))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("upload", upload))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
    dispatcher.add_handler(CommandHandler("profile", profile))
    dispatcher.add_handler(CommandHandler("stats", stats))

    # Register message handler for guesses
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_guess))

    # Start polling and log the polling status
    updater.start_polling()
    logging.info("Bot is now polling for updates...")

    # Run the bot until manually stopped
    updater.idle()

if __name__ == '__main__':
    main()
