import telebot
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token
API_TOKEN = "7579121046:AAGKT7JvhL6xDcCtRUWU8NNitVYqLvAeTrk-83GlSE"  # Replace with your Telegram bot API token

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and guessing game
user_last_claim = {}  # Track the last time each user claimed daily reward
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution

DAILY_REWARD_COINS = 10000  # Coins given as a daily reward

### Helper Functions ###
def add_coins(user_id, coins):
    user_coins[user_id] += coins
    print(f"User {user_id} awarded {coins} coins. Total: {user_coins[user_id]}")

### Command Handlers ###

# /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"Received /start from {message.chat.id}")
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)
    
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Welcome to the Anime Character Guessing Game!**
🎮 **Commands:**
- /claim - Claim your daily reward of 10,000 coins
- /help - Show this help message
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# /claim command
@bot.message_handler(commands=['claim'])
def claim_daily_reward(message):
    user_id = message.from_user.id
    now = datetime.now()
    print(f"User {user_id} attempted to claim daily reward")

    # Check if the user has already claimed within the past 24 hours
    if user_id in user_last_claim:
        last_claim_time = user_last_claim[user_id]
        time_since_last_claim = now - last_claim_time
        if time_since_last_claim < timedelta(days=1):
            remaining_time = timedelta(days=1) - time_since_last_claim
            hours_left = remaining_time.seconds // 3600
            minutes_left = (remaining_time.seconds % 3600) // 60
            bot.reply_to(message, f"⏳ You can claim your next reward in **{hours_left} hours and {minutes_left} minutes**.")
            return

    # Award daily reward coins
    add_coins(user_id, DAILY_REWARD_COINS)
    user_last_claim[user_id] = now
    bot.reply_to(message, f"🎉 You have successfully claimed **{DAILY_REWARD_COINS} coins** as your daily reward!")

# /help command
@bot.message_handler(commands=['help'])
def show_help(message):
    print(f"Received /help from {message.chat.id}")
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Available Commands:**
- /claim - Claim your daily reward of 10,000 coins
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# Catch all other messages
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(f"Received unknown message from {message.chat.id}: {message.text}")

# Start polling the bot
print("Bot is polling...")
bot.infinity_polling()
