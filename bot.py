import os
import random
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram import Update, ParseMode, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID"))
CHARACTER_CHANNEL_ID = int(os.getenv("CHARACTER_CHANNEL_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]

# Rarity Levels
RARITY_LEVELS = {
    "Common": "🌟 Common",
    "Elite": "🔥 Elite",
    "Rare": "💎 Rare",
    "Legendary": "🌠 Legendary",
}

# Threshold for messages
MESSAGE_THRESHOLD = 5
message_counters = {}

# Helper Functions
def get_user_profile(user_id, name=None):
    """Fetch or create a user profile in the database."""
    user = users_collection.find_one({"_id": user_id})
    if not user:
        user = {
            "_id": user_id,
            "coins": 0,
            "correct_guesses": 0,
            "games_played": 0,
            "profile_name": name or "Unknown",
        }
        users_collection.insert_one(user)
    return user

def update_user_stats(user_id, coins, correct_guess=False):
    """Update user stats."""
    update_query = {"$inc": {"coins": coins, "games_played": 1}}
    if correct_guess:
        update_query["$inc"]["correct_guesses"] = 1
    users_collection.update_one({"_id": user_id}, update_query)

def get_level_and_tag(coins):
    """Calculate level and tag based on coins."""
    level = coins // 10
    if level < 50:
        tag = "🐣 Novice Explorer"
    elif level < 200:
        tag = "💪 Intermediate Warrior"
    elif level < 500:
        tag = "🏆 Seasoned Fighter"
    elif level < 999:
        tag = "🌟 Heroic Legend"
    elif level == 999:
        tag = "⚡ Master Champion"
    elif level >= 1000:
        tag = "🔥 Overpowered Master"
    return level, tag

def assign_rarity():
    """Randomly assign a rarity based on probabilities."""
    rarities = list(RARITY_LEVELS.keys())
    probabilities = [0.5, 0.3, 0.15, 0.05]  # Probabilities for Common, Elite, Rare, Legendary
    return random.choices(rarities, probabilities, k=1)[0]

def send_new_character(context: CallbackContext, chat_id: int):
    """Send a new character for guessing."""
    chosen_character = characters_collection.aggregate([{ "$sample": { "size": 1 } }]).next()
    if not chosen_character:
        context.bot.send_message(chat_id=chat_id, text="🚨 No characters available in the database!")
        return

    context.chat_data["chosen_character"] = chosen_character
    caption = (
        f"🤔 **Guess the character's name!**\n"
        f"📸 **Image**: {chosen_character['image_url']}\n"
        f"🌟 **Rarity**: {RARITY_LEVELS[chosen_character['rarity']]}"
    )
    context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN)

# Command Handlers
def start(update: Update, context: CallbackContext):
    """Handle /start command."""
    user = update.effective_user
    user_profile = get_user_profile(user.id, user.full_name)
    welcome_message = (
        f"🎮 **Welcome to Philo Guesser, {user.full_name}! 🌟**\n"
        "🎉 Test your knowledge and climb the leaderboard by guessing correctly!"
    )
    update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

def profile(update: Update, context: CallbackContext):
    """Handle /profile command."""
    user = update.effective_user
    user_profile = get_user_profile(user.id, user.full_name)
    coins = user_profile["coins"]
    level, tag = get_level_and_tag(coins)
    profile_message = (
        f"📊 **Your Profile**\n"
        f"👤 **Name**: {user.full_name}\n"
        f"💰 **Coins**: {coins}\n"
        f"🎮 **Level**: {level} {tag}\n"
        f"✔️ **Correct Guesses**: {user_profile['correct_guesses']}\n"
        f"🎮 **Games Played**: {user_profile['games_played']}\n"
        "⭐ Keep playing to level up and earn rewards!"
    )
    update.message.reply_text(profile_message, parse_mode=ParseMode.MARKDOWN)

def stats(update: Update, context: CallbackContext):
    """Handle /stats command (Owner only)."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        update.message.reply_text("❌ You do not have permission to view bot stats.")
        return

    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    stats_message = (
        f"📊 **Bot Stats**:\n"
        f"👥 **Total Users**: {total_users}\n"
        f"🎭 **Total Characters**: {total_characters}"
    )
    update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)

def guess(update: Update, context: CallbackContext):
    """Send a character for guessing."""
    send_new_character(context, chat_id=update.effective_chat.id)

def message_handler(update: Update, context: CallbackContext):
    """Handle user messages for guessing and threshold."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Update message counter for threshold
    if user_id not in message_counters:
        message_counters[user_id] = 0
    message_counters[user_id] += 1

    if message_counters[user_id] >= MESSAGE_THRESHOLD:
        # Reset counter and send new character
        message_counters[user_id] = 0
        send_new_character(context, chat_id=chat_id)
        return

    # Check if the user is guessing a character
    if "chosen_character" not in context.chat_data:
        return

    chosen_character = context.chat_data["chosen_character"]
    guess = update.message.text.strip().lower()
    character_words = set(chosen_character["name"].lower().split())
    guessed_words = set(guess.split())

    if character_words.intersection(guessed_words):
        update_user_stats(user_id, coins=10, correct_guess=True)
        update.message.reply_text(
            f"🎉 **Correct!** The character is **{chosen_character['name']}**. 🏆 You earned 10 coins!",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Send a new character immediately
        send_new_character(context, chat_id=chat_id)
    else:
        update.message.reply_text("❌ **Wrong guess. Try again!** 🚨")

# Main Function
def main():
    """Start the bot."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set. Please check your .env file.")

    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command Handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("profile", profile))
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("guess", guess))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))

    # Start Polling
    print("🤖 Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
