import telebot
import random
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7579121046:AAHpWOGqhK-bw4RA5xT9cRpO2G6c-83GlSE"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and guessing game
current_redeem_code = None
redeem_code_expiry = None
redeem_code_claims = {}

user_last_claim = {}  # Track the last time each user claimed daily reward
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
characters = []  # Store uploaded characters
user_streaks = defaultdict(int)  # Track correct guess streaks
user_achievements = defaultdict(list)  # Track user achievements
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_favorite_characters = defaultdict(list)  # Track user's favorite characters
user_titles = defaultdict(str)  # Track custom titles

# Constants
DAILY_REWARD_COINS = 10000  # Coins given as a daily reward
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

# /start command - Sends welcome message with the /help information
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)

    # Send welcome message along with /help information
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Welcome to the Anime Character Guessing Game!**

🎮 **Commands:**
- /claim - Claim your daily reward of 10,000 coins
- /help - Show this help message
- /leaderboard - Show the leaderboard with users and their coins
- /bonus - Claim additional bonuses (if available)
- /redeem <code> - Redeem a valid code for coins
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by ID
- /profile - Show your profile with stats and achievements
- /favorite - Mark a character as your favorite
- /settitle <title> - Set a custom title for your profile
- /stats - (Owner only) Show bot stats
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# /claim command - Allows users to claim daily rewards (10,000 coins once every 24 hours)
@bot.message_handler(commands=['claim'])
def claim_daily_reward(message):
    user_id = message.from_user.id
    now = datetime.now()

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

# /stats command - Only for the owner of the bot to check bot statistics
@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id == BOT_OWNER_ID:
        total_users = len(user_profiles)
        total_groups = len([chat_id for chat_id in user_chat_ids if chat_id < 0])  # Group chats have negative IDs
        bot.reply_to(message, f"📊 **Bot Stats**:\n\n👥 **Total Users**: {total_users}\n💬 **Total Groups**: {total_groups}")
    else:
        bot.reply_to(message, "❌ You are not authorized to view this information.")

# /leaderboard command - Shows the leaderboard with users and their coins
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    if not user_coins:
        bot.reply_to(message, "No leaderboard data available yet.")
        return

    sorted_users = sorted(user_coins.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = "🏆 **Leaderboard**:\n\n"
    for rank, (user_id, coins) in enumerate(sorted_users, start=1):
        profile_name = user_profiles.get(user_id, "Unknown")
        leaderboard_message += f"{rank}. {profile_name}: {coins} coins\n"

    bot.reply_to(message, leaderboard_message, parse_mode='Markdown')

# /profile command - Shows the user's profile with stats
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    total_coins = user_coins.get(user_id, 0)
    correct_guesses = user_correct_guesses.get(user_id, 0)
    streak = user_streaks.get(user_id, 0)
    achievements = user_achievements.get(user_id, [])
    favorite_characters = user_favorite_characters.get(user_id, [])
    title = user_titles.get(user_id, "Newbie")

    profile_message = (
        f"👤 **Profile**\n"
        f"💰 **Coins**: {total_coins}\n"
        f"✅ **Correct Guesses**: {correct_guesses}\n"
        f"🔥 **Current Streak**: {streak}\n"
        f"🏅 **Achievements**: {', '.join(achievements) if achievements else 'None'}\n"
        f"💖 **Favorite Characters**: {', '.join(favorite_characters) if favorite_characters else 'None'}\n"
        f"👑 **Title**: {title}"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# /favorite command - Mark a character as a user's favorite
@bot.message_handler(commands=['favorite'])
def favorite_character(message):
    global current_character
    user_id = message.from_user.id

    if not current_character:
        bot.reply_to(message, "❌ There's no character to favorite.")
        return

    if current_character['character_name'] in user_favorite_characters[user_id]:
        bot.reply_to(message, "⚠️ You've already marked this character as a favorite.")
        return

    user_favorite_characters[user_id].append(current_character['character_name'])
    add_coins(user_id, COINS_FOR_FAVORITING_CHARACTER)
    bot.reply_to(message, f"💖 You marked **{current_character['character_name']}** as a favorite and earned **{COINS_FOR_FAVORITING_CHARACTER}** coins!")

# /settitle command - Set a custom title for the user's profile
@bot.message_handler(commands=['settitle'])
def set_title(message):
    user_id = message.from_user.id
    try:
        _, new_title = message.text.split(maxsplit=1)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /settitle <title>")
        return

    user_titles[user_id] = new_title.strip()
    bot.reply_to(message, f"👑 Your title has been set to **{new_title}**!")

# /help command - Lists all available commands if requested separately
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Available Commands:**

- /claim - Claim your daily reward of 10,000 coins
- /help - Show this help message
- /leaderboard - Show the leaderboard with users and their coins
- /bonus - Claim additional bonuses (if available)
- /redeem <code> - Redeem a valid code for coins
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by ID
- /profile - Show your profile with stats and achievements
- /favorite - Mark a character as your favorite
- /settitle <title> - Set a custom title for your profile
- /stats - (Owner only) Show bot stats
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

### --- 3. Start Polling the Bot --- ###

# Start polling the bot
bot.infinity_polling()
