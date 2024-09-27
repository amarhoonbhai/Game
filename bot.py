import telebot
import random
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7579121046:AAGPLli-qS53_3RyQwuc7xf39_JeWsa3-Q8"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and guessing game
current_redeem_code = None
redeem_code_expiry = None
redeem_code_claims = {}

user_last_bonus = {}  # Track last bonus claim time of each user
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
characters = []  # Store uploaded characters
user_streaks = defaultdict(int)  # Track correct guess streaks
user_achievements = defaultdict(list)  # Track user achievements
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_favorite_characters = defaultdict(list)  # Track user's favorite characters
user_titles = defaultdict(str)  # Track custom titles

# Counter for unique character IDs
character_id_counter = 1

# Constants
INITIAL_COINS = 10000  # Coins awarded when a user starts the bot for the first time
COINS_PER_GUESS = 10
COINS_PER_HINT = 5
COINS_PER_BONUS = 100  # Bonus coins for daily reward
COINS_PER_REDEEM = 50  # Coins per redeem
COINS_FOR_FAVORITING_CHARACTER = 10  # Bonus for favoriting a character

### --- 1. Helper Functions --- ###

# Function to add coins to the user's balance
def add_coins(user_id, coins):
    user_coins[user_id] += coins

# Function to check if the user is the bot owner or a sudo admin
def is_admin_or_owner(message):
    if message.from_user.id == BOT_OWNER_ID:
        return True
    try:
        chat_admins = bot.get_chat_administrators(message.chat.id)
        return message.from_user.id in [admin.user.id for admin in chat_admins]
    except Exception:
        return False

### --- 2. Command Handlers --- ###

# /start command - Sends welcome message, gives 10,000 coins, and includes /help information
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)

    # Award 10,000 coins to new users
    if user_id not in user_coins:
        add_coins(user_id, INITIAL_COINS)
        bot.reply_to(message, f"💰 **Welcome to the Anime Character Guessing Game!**\nYou've been awarded **{INITIAL_COINS} coins** for starting the game!")

    # Send welcome message along with /help information
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Welcome to the Anime Character Guessing Game!**

🎮 **Commands:**
- /start - Start the game and get 10,000 coins
- /help - Show this help message
- /leaderboard - Show the leaderboard with users and their coins
- /bonus - Claim your daily reward (every 24 hours)
- /redeem <code> - Redeem a valid code for coins
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by ID
- /profile - Show your profile with stats and achievements
- /favorite - Mark a character as your favorite
- /settitle <title> - Set a custom title for your profile
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# /help command - Lists all available commands if requested separately
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Available Commands:**

- /start - Start the game and get 10,000 coins
- /help - Show this help message
- /leaderboard - Show the leaderboard with users and their coins
- /bonus - Claim your daily reward (every 24 hours)
- /redeem <code> - Redeem a valid code for coins
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by ID
- /profile - Show your profile with stats and achievements
- /favorite - Mark a character as your favorite
- /settitle <title> - Set a custom title for your profile
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# Other command handlers (e.g., /leaderboard, /redeem, etc.) go here
# Refer to the full script above for additional commands and logic

### --- 3. Start Polling the Bot --- ###

# Start polling the bot
bot.infinity_polling()
