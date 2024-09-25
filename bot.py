import telebot
import random
import threading
import time
from datetime import datetime, timedelta

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7579121046:AAFeRRg0GJ6TdFfav5v_d9pZ1enwn1T59JA"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged
GROUP_CHAT_ID = -1001548130580  # Replace with your group chat ID where codes will be sent

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# Logging setup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# In-memory store for redeem codes, characters, and guessing game
current_redeem_code = None
redeem_code_expiry = None
redeem_code_claims = {}  # Track which users have redeemed codes

user_last_bonus = {}  # To track the last bonus claim time of each user
user_coins = {}  # Dictionary to track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
characters = []  # Store uploaded characters

# Constants
INITIAL_COINS = 10000  # Coins awarded when a user starts the bot for the first time

# Counter to track the number of text messages
message_counter = 0  # We'll reset this after every 2 messages

# Coins awarded for correct guesses and bonus
COINS_PER_GUESS = 10
COINS_PER_BONUS = 100  # Bonus coins for daily reward
COINS_PER_REDEEM = 50  # Coins per redeem

# Rarity levels for characters
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}

# Stylish symbols for formatting profile names
STYLE_START = "🔥✨ "
STYLE_END = " ✨🔥"

# Current character in play for guessing
current_character = None

### --- 1. Helper Functions --- ###

# Function to add coins to the user's balance
def add_coins(user_id, coins):
    if user_id not in user_coins:
        user_coins[user_id] = 0
    user_coins[user_id] += coins

# Function to format user profile names stylishly
def stylish_profile_name(user_id):
    profile_name = user_profiles.get(user_id, None)
    if profile_name:
        return f"{STYLE_START}{profile_name}{STYLE_END}"
    return f"{STYLE_START}Unknown{STYLE_END}"

# Function to check if the user is the bot owner or a sudo admin
def is_admin_or_owner(message):
    if message.from_user.id == BOT_OWNER_ID:
        return True
    try:
        chat_admins = bot.get_chat_administrators(message.chat.id)
        return message.from_user.id in [admin.user.id for admin in chat_admins]
    except Exception as e:
        logger.error(f"Error checking admin rights: {e}")
        return False

# Function to auto-assign rarity
def assign_rarity():
    return random.choice(list(RARITY_LEVELS.keys()))

# Function to generate a random 4-digit redeem code
def generate_redeem_code():
    return ''.join(random.choices('0123456789', k=4))

# Function to send a character for guessing
def send_character(chat_id):
    global current_character
    if characters:
        current_character = random.choice(characters)
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 **Guess the Anime Character!**\n\n"
            f"💬 **Name**: ???\n"
            f"⚔️ **Rarity**: {rarity} {current_character['rarity']}\n"
            f"🌟 Can you guess this amazing character?"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption, parse_mode='Markdown')

### --- 2. Command Handlers --- ###

# /upload command - Allows the owner and admins to upload new characters
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name>")
        return

    # Assign a random rarity and save the character
    rarity = assign_rarity()
    character = {
        'image_url': image_url.strip(),
        'character_name': character_name.strip(),
        'rarity': rarity
    }
    characters.append(character)

    # Log the character to the Telegram channel
    bot.send_message(CHANNEL_ID, f"📥 New Character Uploaded:\n\nName: {character_name}\nRarity: {RARITY_LEVELS[rarity]} {rarity}\nImage URL: {image_url}")
    bot.reply_to(message, f"✅ Character '{character_name}' with rarity '{RARITY_LEVELS[rarity]} {rarity}' has been uploaded successfully!")

# /delete command - Allows the owner and admins to delete characters
@bot.message_handler(commands=['delete'])
def delete_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, character_name = message.text.split(maxsplit=1)
        character_name = character_name.strip()
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /delete <character_name>")
        return

    for character in characters:
        if character['character_name'].lower() == character_name.lower():
            characters.remove(character)
            bot.reply_to(message, f"✅ Character '{character_name}' has been deleted.")
            return

    bot.reply_to(message, f"❌ Character '{character_name}' not found.")

# /guess command - Allows users to guess the character name
@bot.message_handler(func=lambda message: True)
def guess_character(message):
    global current_character, message_counter
    user_guess = message.text.strip().lower()

    if current_character and user_guess == current_character['character_name'].lower():
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        user_profiles[user_id] = username
        add_coins(user_id, COINS_PER_GUESS)
        bot.reply_to(message, f"🎉 **Congratulations {username}**! You guessed correctly and earned **{COINS_PER_GUESS}** coins!", parse_mode='Markdown')

    message_counter += 1
    if message_counter >= 2:
        send_character(message.chat.id)
        message_counter = 0

# /stats command - Only for the owner of the bot to check bot statistics
@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id == BOT_OWNER_ID:
        total_users = len(user_profiles)
        total_groups = len([chat_id for chat_id in user_chat_ids if chat_id < 0])
        total_characters = len(characters)
        bot.reply_to(message, f"📊 Bot Stats:\n\n👥 Total Users: {total_users}\n🛠️ Total Groups: {total_groups}\n📦 Total Characters: {total_characters}")
    else:
        bot.reply_to(message, "❌ You are not authorized to view this information.")

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
        bot.reply_to(message, f"💰 Welcome! You've been awarded **{INITIAL_COINS}** coins for starting the game!")

    # Send welcome message along with /help information
    help_message = """
    🤖 Welcome to the Anime Character Guessing Game!
    🎮 Commands:
    /start - Start the game and get 10,000 coins
    /help - Show this help message
    /leaderboard - Show the leaderboard with users and their coins
    /bonus - Claim your daily reward (every 24 hours)
    /redeem <code> - Redeem a valid code for coins
    /upload <image_url> <character_name> - (Admins only) Upload a new character
    /delete <character_name> - (Admins only) Delete a character by name
    /stats - (Owner only) Show bot stats
    🎨 Guess the name of anime characters!
    """
    bot.reply_to(message, help_message)

# /leaderboard command - Shows the leaderboard with user coins and profile names
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    if not user_coins:
        bot.reply_to(message, "No leaderboard data available yet.")
        return

    # Sort the users by the number of coins in descending order
    sorted_users = sorted(user_coins.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = "🏆 **Leaderboard**:\n\n"
    for rank, (user_id, coins) in enumerate(sorted_users, start=1):
        profile_name = stylish_profile_name(user_id)
        leaderboard_message += f"{rank}. {profile_name}: 💰 {coins} coins\n"

    bot.reply_to(message, leaderboard_message, parse_mode='Markdown')

# /bonus command - Claim daily reward once every 24 hours
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    user_profiles[user_id] = message.from_user.username or message.from_user.first_name

    if can_claim_bonus(user_id):
        user_last_bonus[user_id] = datetime.now()  # Record the claim time
        add_coins(user_id, COINS_PER_BONUS)
        bot.reply_to(message, f"🎁 **{username}**, you have claimed your daily bonus and received **{COINS_PER_BONUS}** coins!", parse_mode='Markdown')
    else:
        remaining_time = timedelta(days=1) - (datetime.now() - user_last_bonus[user_id])
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"⏳ You can claim your next bonus in **{hours_left} hours and {minutes_left} minutes**.", parse_mode='Markdown')

# /help command - Lists all available commands (if requested separately)
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
    🤖 Available Commands:
    
    /start - Start the game and get 10,000 coins
    /help - Show this help message
    /leaderboard - Show the leaderboard with users and their coins
    /bonus - Claim your daily reward (available every 24 hours)
    /redeem <code> - Redeem a valid code for coins
    /upload <image_url> <character_name> - (Admins only) Upload a new character
    /delete <character_name> - (Admins only) Delete a character by name
    /stats - (Owner only) Show bot stats
    🎨 Guess the name of anime characters!
    """
    bot.reply_to(message, help_message)

### --- 3. Redeem Code Generation --- ###

def auto_generate_redeem_code():
    global current_redeem_code, redeem_code_expiry, redeem_code_claims
    while True:
        current_redeem_code = generate_redeem_code()
        redeem_code_expiry = datetime.now() + timedelta(minutes=30)
        redeem_code_claims.clear()  # Reset the claims for the new code
        redeem_message = f"🔑 New Redeem Code: **{current_redeem_code}**\nThis code is valid for 30 minutes. Use /redeem <code> to claim coins!"
        bot.send_message(GROUP_CHAT_ID, redeem_message, parse_mode='Markdown')
        for chat_id in user_chat_ids:
            bot.send_message(chat_id, redeem_message, parse_mode='Markdown')
        time.sleep(1800)

### --- 4. Start Polling the Bot --- ###

# Start the redeem code generation in a separate thread
threading.Thread(target=auto_generate_redeem_code, daemon=True).start()

# Start polling the bot
bot.infinity_polling()
