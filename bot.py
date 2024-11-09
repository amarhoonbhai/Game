import random
import logging
from pymongo import MongoClient
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest, Unauthorized, NetworkError

# Set up logging for debugging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB connection details
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
DATABASE_NAME = "anime_game"
CHARACTERS_COLLECTION = "characters"
USERS_COLLECTION = "users"

# Bot token and access control
TOKEN = "6862816736:AAEsACgCBaMHWPq8rKxH5rLcc-NVDNZDXm4"
OWNER_ID = 7222795580
ADMIN_IDS = [OWNER_ID, 987654321]

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
characters_collection = db[CHARACTERS_COLLECTION]
users_collection = db[USERS_COLLECTION]

# Rarity mapping with emojis
RARITY_EMOJIS = {
    "bronze": "🥉",
    "silver": "🥈",
    "gold": "🥇",
    "platinum": "💿",
    "diamond": "💎"
}

# Game state variables
current_character = None
message_count = 0  # Tracks the number of messages since the last character post
THRESHOLD_MESSAGES = 5  # Post a new character after 5 messages

# Dynamic celebratory messages
CELEBRATORY_MESSAGES = [
    "🎉 Awesome! You got it right! 🎉",
    "👏 Well done! That's correct! 👏",
    "🔥 You're on fire! That's the correct answer! 🔥",
    "🎊 Brilliant! You nailed it! 🎊",
    "🥳 Great job! You guessed it! 🥳",
]

def safe_send_message(update, text, parse_mode=None, reply_markup=None):
    """Safely send a message to the user, handling errors gracefully."""
    try:
        if update.message and update.message.chat_id:
            update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"BadRequest: {e}. Could not send message to chat ID {update.message.chat_id}")
    except Unauthorized as e:
        logger.warning(f"Unauthorized: {e}. Bot was removed from chat ID {update.message.chat_id}")
    except NetworkError as e:
        logger.warning(f"NetworkError: {e}. Retrying...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

# Function to post a new character from the database to the chat
def post_random_character(update=None, context=None):
    global current_character, message_count
    chat_id = update.message.chat_id if update else context.job.context

    characters = list(characters_collection.find())
    if not characters:
        return  # Do nothing if there are no characters available

    current_character = random.choice(characters)
    message_count = 0  # Reset message count after posting a new character
    if context:
        context.bot.send_message(chat_id=chat_id, text="✨ A new character has appeared! Can you guess who it is? 🤔")
    else:
        safe_send_message(update, "✨ A new character has appeared! Can you guess who it is? 🤔")

# Start the bot with a welcome message
def start(update: Update, context: CallbackContext) -> None:
    welcome_message = (
        "👋 Welcome To Pʜɪʟᴏ 🝮︎︎︎︎︎︎︎ Gʀᴀʙʙᴇʀ!\n"
        "Let's play a guessing game! Try to guess the anime character! 🎉\n"
        "Use /hello to check if I am active!"
    )
    safe_send_message(update, welcome_message)
    post_random_character(update=update)

# Simple command to check if the bot is active
def hello(update: Update, context: CallbackContext) -> None:
    safe_send_message(update, "Hello! I am active and ready for your guesses! 🎉")

# Help command to show instructions
def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
    🆘 *Help Menu* 🆘

    ⍟ Just type your guess to participate in the game! 🧩
    ⍟ If your guess is correct, the bot will automatically give a new character and your level will increase. 📈
    ⍟ /start - Start the bot and begin character posting 🚀
    ⍟ /hello - Check if the bot is active ✅
    ⍟ /help - Show this help message 📋
    ⍟ /upload [image_url] [character_name] [rarity] - Add a new character (admin only) 👤
    ⍟ /stats - (Owner only) View all user levels 📊
    ⍟ /leaderboard - View the top players by level 🏆
    ⍟ /profile - View your current level, rank, and coins 🧍‍♂️
    """
    safe_send_message(update, help_text, parse_mode=ParseMode.MARKDOWN)

# Admin-only command to upload a new character
def upload(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        safe_send_message(update, "🚫 You don't have permission to use this command.")
        return

    if len(context.args) < 3:
        safe_send_message(update, "⚙️ Usage: /upload [image_url] [character_name] [rarity]")
        return

    image_url = context.args[0]
    rarity = context.args[-1].lower()
    character_name = " ".join(context.args[1:-1])

    if rarity not in RARITY_EMOJIS:
        safe_send_message(update, "❗ Invalid rarity. Rarity must be one of: bronze, silver, gold, platinum, diamond.")
        return

    character_data = {
        "name": character_name,
        "image_url": image_url,
        "rarity": rarity
    }
    characters_collection.insert_one(character_data)

    emoji = RARITY_EMOJIS[rarity]
    safe_send_message(update, f"✅ Character '{character_name}' with rarity {emoji} {rarity.capitalize()} has been added successfully.")

# Guess handling function
def handle_guess(update: Update, context: CallbackContext) -> None:
    global message_count, current_character

    guess = update.message.text.strip()
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    if current_character and guess.lower() == current_character['name'].lower():
        # Correct guess: increase the user's level and award coins
        user = users_collection.find_one({"user_id": user_id})
        coins_awarded = random.randint(10, 50)  # Randomly award between 10 and 50 coins

        if user:
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"level": 1, "coins": coins_awarded}}
            )
            new_level = user["level"] + 1
            new_coins = user.get("coins", 0) + coins_awarded
        else:
            users_collection.insert_one({"user_id": user_id, "username": username, "level": 1, "coins": coins_awarded})
            new_level = 1
            new_coins = coins_awarded

        celebratory_message = random.choice(CELEBRATORY_MESSAGES)
        emoji = RARITY_EMOJIS[current_character['rarity']]
        try:
            update.message.reply_photo(
                current_character['image_url'],
                caption=f"{celebratory_message}\n\nThe character was *{current_character['name']}* - {emoji} {current_character['rarity'].capitalize()}\n"
                        f"⭐️ *Your level is now {new_level}!* ⭐️\n"
                        f"💰 You earned {coins_awarded} coins! Total coins: {new_coins} 💰",
                parse_mode=ParseMode.MARKDOWN
            )
        except BadRequest as e:
            logger.warning(f"Failed to send image message: {e}")
        post_random_character(update)  # Reset after correct guess
    else:
        safe_send_message(update, "❌ Incorrect guess! Try again.")

    # Increase message count and check if threshold is reached
    message_count += 1
    if message_count >= THRESHOLD_MESSAGES:
        safe_send_message(update, "Threshold reached. Here’s a new character to guess.")
        post_random_character(update)

# Profile command to view user's current level, rank, and coins
def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    user = users_collection.find_one({"user_id": user_id})
    if user:
        rank = users_collection.count_documents({"level": {"$gt": user["level"]}}) + 1
        profile_message = (f"🧍 *Profile for @{username}*\n\n"
                           f"🏅 *Level:* {user['level']}\n"
                           f"💰 *Coins:* {user.get('coins', 0)}\n"
                           f"🎖️ *Rank:* #{rank}")
    else:
        profile_message = "🚫 You don't have a profile yet. Start guessing characters to level up and earn coins!"

    keyboard = [
        [InlineKeyboardButton("Developer - @TechPiro", url="https://t.me/TechPiro")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    safe_send_message(update, profile_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# Main function to start the bot
def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("hello", hello))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("upload", upload))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))
    dispatcher.add_handler(CommandHandler("profile", profile))
    dispatcher.add_handler(CommandHandler("stats", stats))  

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_guess))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
