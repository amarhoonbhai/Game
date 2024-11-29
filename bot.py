import os
import random
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

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
sudo_users_collection = db["sudo_users"]

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

def is_sudo_user(user_id):
    """Check if a user is a sudo user."""
    return bool(sudo_users_collection.find_one({"_id": user_id})) or user_id == OWNER_ID

def get_level_and_tag(coins):
    """Calculate level and tag based on coins."""
    level = coins // 10  # Each level requires 10 coins
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
    else:  # Level 1000 and above
        tag = "🔥 Overpowered Master"
    return level, tag

async def send_new_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Send a new character for guessing."""
    chosen_character = characters_collection.aggregate([{ "$sample": { "size": 1 } }]).next()
    if not chosen_character:
        await context.bot.send_message(chat_id=chat_id, text="🚨 No characters available in the database!")
        return

    context.chat_data["chosen_character"] = chosen_character
    caption = (
        f"🤔 **Guess the character's name!**\n"
        f"📸 **Image**: {chosen_character['image_url']}\n"
        f"🌟 **Rarity**: {RARITY_LEVELS[chosen_character['rarity']]}"
    )
    await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.MARKDOWN)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    get_user_profile(user.id, user.full_name)
    welcome_message = (
        f"🎮 **Welcome to Philo Guesser, {user.full_name}! 🌟**\n"
        "🎉 Test your knowledge and climb the leaderboard by guessing correctly!"
    )
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command."""
    user = update.effective_user
    user_profile = get_user_profile(user.id, user.full_name)
    coins = user_profile["coins"]
    level, tag = get_level_and_tag(coins)
    profile_message = (
        f"📊 **Your Profile**\n"
        f"👤 **Name**: {user.full_name}\n"
        f"💰 **Coins**: {coins}\n"
        f"🎮 **Level**: {level}\n"
        f"🏅 **Rank**: {tag}\n"
        f"✔️ **Correct Guesses**: {user_profile['correct_guesses']}\n"
        f"🎮 **Games Played**: {user_profile['games_played']}\n"
        "⭐ Keep playing to level up and earn rewards!"
    )
    await update.message.reply_text(profile_message, parse_mode=ParseMode.MARKDOWN)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (Owner only)."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You do not have permission to view bot stats.")
        return

    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    stats_message = (
        f"📊 **Bot Stats**:\n"
        f"👥 **Total Users**: {total_users}\n"
        f"🎭 **Total Characters**: {total_characters}"
    )
    await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages for guessing and threshold."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Initialize or update message counter for the user
    if user_id not in message_counters:
        message_counters[user_id] = 0
    message_counters[user_id] += 1

    # Check if the user has reached the message threshold
    if message_counters[user_id] >= MESSAGE_THRESHOLD:
        # Reset counter and send a new character
        message_counters[user_id] = 0
        await send_new_character(context, chat_id=chat_id)
        return

    # If a character is already chosen, check for a guess
    if "chosen_character" not in context.chat_data:
        return

    chosen_character = context.chat_data["chosen_character"]
    guess = update.message.text.strip().lower()
    character_words = set(chosen_character["name"].lower().split())
    guessed_words = set(guess.split())

    # Check if the guess is correct
    if character_words.intersection(guessed_words):
        update_user_stats(user_id, coins=100, correct_guess=True)  # Reward 100 coins
        await update.message.reply_text(
            f"🎉 **Correct!** The character is **{chosen_character['name']}**. 🏆 You earned 100 coins!",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Immediately send a new character after a correct guess
        await send_new_character(context, chat_id=chat_id)
    else:
        await update.message.reply_text("❌ **Wrong guess. Try again!** 🚨")

async def send_help_message(update: Update):
    """Send a list of available commands."""
    help_message = (
        "🛠 **Available Commands:**\n"
        "/start - Start the bot\n"
        "/profile - View your profile\n"
        "/stats - View bot stats (Owner only)\n"
        "/guess - Start a guessing game\n"
        "/help - Show this help message\n"
        "/addsudo [user_id] - Add a sudo user (Owner only)\n"
        "/upload [image_url] [character_name] [rarity] - Add a new character to the database (Owner/Sudo only)"
    )
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

async def add_sudo_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a user as a sudo user."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can add sudo users.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Usage: /addsudo [user_id]")
        return

    sudo_user_id = int(context.args[0])
    if sudo_users_collection.find_one({"_id": sudo_user_id}):
        await update.message.reply_text("✅ This user is already a sudo user.")
    else:
        sudo_users_collection.insert_one({"_id": sudo_user_id})
        await update.message.reply_text(f"✅ User {sudo_user_id} has been added as a sudo user.")

async def upload_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload a new character to the database."""
    user_id = update.effective_user.id
    if not is_sudo_user(user_id):
        await update.message.reply_text("❌ You do not have permission to add characters.")
        return

    if len(context.args) < 3:
        await update.message.reply_text("⚠️ Usage: /upload [image_url] [character_name] [rarity]")
        return

    image_url = context.args[0]
    character_name = " ".join(context.args[1:-1])
    rarity = context.args[-1].capitalize()

    if rarity not in RARITY_LEVELS:
        await update.message.reply_text(f"⚠️ Invalid rarity level. Choose from: {', '.join(RARITY_LEVELS.keys())}")
        return

    # Insert character into the database
    characters_collection.insert_one({
        "name": character_name,
        "image_url": image_url,
        "rarity": rarity
    })
    await update.message.reply_text(f"✅ Character '{character_name}' added with rarity '{rarity}'.")

# Main Function
def main():
    """Start the bot."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set. Please check your .env file.")

    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", send_help_message))
    application.add_handler(CommandHandler("addsudo", add_sudo_user))
    application.add_handler(CommandHandler("upload", upload_character))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start the bot
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
