import telebot
import random
import threading
import time
import requests
from datetime import datetime, timedelta

# Replace with your actual bot API token and owner ID
API_TOKEN = "7740301929:AAGaX84MeVFn0neJ9y0qOI2CLXg9HDywIkw"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
GROUP_CHAT_ID =-1001548130580  # Replace with your group chat ID where codes will be sent

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes
current_redeem_code = None
redeem_code_expiry = None
redeem_code_claims = {}  # Track which users have redeemed codes

user_last_bonus = {}   # To track the last bonus claim time of each user
user_coins = {}  # Dictionary to track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution

# Coins awarded for correct guesses and bonus
COINS_PER_GUESS = 10
COINS_PER_BONUS = 100  # Bonus coins for daily reward
COINS_PER_REDEEM = 50  # Coins per redeem

# Stylish symbols for formatting profile names
STYLE_START = "🔥✨ "
STYLE_END = " ✨🔥"

# Store items with prices (items available for purchase)
STORE_ITEMS = {
    "Sword": 100,
    "Shield": 150,
    "Potion": 50,
    "Magic Scroll": 200
}

### --- 1. Helper Functions --- ###

# Function to add coins to the user's balance
def add_coins(user_id, coins):
    if user_id not in user_coins:
        user_coins[user_id] = 0
    user_coins[user_id] += coins

# Function to check if the user has enough coins to buy an item
def has_enough_coins(user_id, cost):
    return user_coins.get(user_id, 0) >= cost

# Function to fetch a random anime character from MyAnimeList API (via Jikan)
def fetch_anime_character():
    try:
        response = requests.get('https://api.jikan.moe/v4/characters?page=1&limit=1')  # Fetch random anime character
        if response.status_code == 200:
            data = response.json()
            character_info = data['data'][0]
            image_url = character_info['images']['jpg']['image_url']
            character_name = character_info['name']
            return image_url, character_name
    except Exception as e:
        print(f"Error fetching character: {e}")
    return None, None

# Function to format and send a character with an attractive caption
def send_character(chat_id):
    image_url, character_name = fetch_anime_character()
    if image_url and character_name:
        caption = (
            f"🎨 **Guess the Anime Character!**\n\n"
            f"💬 **Name**: ???\n"
            f"🌟 Can you guess this amazing character?\n"
            f"🤩 **Hint**: First letter: **{character_name[0]}**"
        )
        bot.send_photo(chat_id, image_url, caption=caption, parse_mode='Markdown')

# Function to check if the user can claim the bonus (daily reward)
def can_claim_bonus(user_id):
    now = datetime.now()
    last_bonus = user_last_bonus.get(user_id)
    return last_bonus is None or (now - last_bonus).days >= 1

# Function to generate a random 4-digit redeem code
def generate_redeem_code():
    return ''.join(random.choices('0123456789', k=4))

# Function to format user profile names stylishly
def stylish_profile_name(user_id):
    profile_name = user_profiles.get(user_id, "Unknown")
    return f"{STYLE_START}{profile_name}{STYLE_END}"

### --- 2. Command Handlers --- ###

# /redeem command - Allows users to redeem the code for coins
@bot.message_handler(commands=['redeem'])
def redeem_code(message):
    global current_redeem_code, redeem_code_expiry

    if current_redeem_code is None or datetime.now() > redeem_code_expiry:
        bot.reply_to(message, "⏳ There is no active redeem code or it has expired.")
        return

    user_id = message.from_user.id
    redeem_attempt = message.text.split()

    if len(redeem_attempt) < 2 or redeem_attempt[1] != current_redeem_code:
        bot.reply_to(message, "❌ Invalid redeem code.")
        return

    if user_id in redeem_code_claims:
        bot.reply_to(message, "⏳ You have already redeemed this code.")
        return

    # Award coins for redeeming
    add_coins(user_id, COINS_PER_REDEEM)
    redeem_code_claims[user_id] = True
    bot.reply_to(message, f"🎉 You have successfully redeemed the code and earned **{COINS_PER_REDEEM}** coins!")

# /stats command - Only for the owner of the bot to check bot statistics
@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id == BOT_OWNER_ID:
        total_users = len(user_profiles)
        total_groups = len([chat_id for chat_id in user_chat_ids if chat_id < 0])  # Group chats have negative IDs
        bot.reply_to(message, f"📊 Bot Stats:\n\n👥 Total Users: {total_users}\n🛠️ Total Groups: {total_groups}")
    else:
        bot.reply_to(message, "❌ You are not authorized to view this information.")

# /start command - Starts the game and includes /help information
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_profiles[message.from_user.id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)  # Track chat IDs for sending redeem codes
    
    # Send welcome message along with /help information
    help_message = """
    🤖 Welcome to the Anime Character Guessing Game!
    
    🎮 Commands:
    /start - Start the game
    /help - Show this help message
    /leaderboard - Show the leaderboard with users and their coins
    /bonus - Claim your daily reward (available every 24 hours)
    /redeem <code> - Redeem a valid code for coins
    /store - View items available for purchase
    /buy <item> - Purchase an item from the store
    /stats - (Owner only) Show bot stats
    🎨 Guess the name of anime characters from images!
    """
    bot.reply_to(message, help_message)

    # Fetch and send the first character
    send_character(chat_id)

# /leaderboard command - Shows the leaderboard with user coins and profile names in a stylish format
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

    # Store user's profile name
    user_profiles[message.from_user.id] = message.from_user.username or message.from_user.first_name

    # Check if the user can claim the bonus (once per 24 hours)
    if can_claim_bonus(user_id):
        # Award daily bonus coins
        user_last_bonus[user_id] = datetime.now()  # Record the claim time
        add_coins(user_id, COINS_PER_BONUS)
        bot.reply_to(message, f"🎁 **{username}**, you have claimed your daily bonus and received **{COINS_PER_BONUS}** coins!", parse_mode='Markdown')
    else:
        remaining_time = timedelta(days=1) - (datetime.now() - user_last_bonus[user_id])
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"⏳ You can claim your next bonus in **{hours_left} hours and {minutes_left} minutes**.", parse_mode='Markdown')

# /store command - Lists items available for purchase
@bot.message_handler(commands=['store'])
def show_store(message):
    store_message = "🛒 **Store Items**:\n\n"
    for item, price in STORE_ITEMS.items():
        store_message += f"• **{item}**: 💰 {price} coins\n"
    
    bot.reply_to(message, store_message, parse_mode='Markdown')

# /buy command - Allows users to purchase items from the store
@bot.message_handler(commands=['buy'])
def buy_item(message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Please specify an item to buy. Example: /buy Sword")
        return

    item_to_buy = args[1].strip()

    if item_to_buy not in STORE_ITEMS:
        bot.reply_to(message, f"❌ The item **{item_to_buy}** is not available in the store.")
        return

    item_price = STORE_ITEMS[item_to_buy]

    if has_enough_coins(user_id, item_price):
        # Deduct coins and confirm the purchase
        user_coins[user_id] -= item_price
        bot.reply_to(message, f"🎉 Congratulations! You have purchased **{item_to_buy}** for **{item_price}** coins!")
    else:
        bot.reply_to(message, "❌ You do not have enough coins to purchase this item.")

# /help command - Lists all available commands (if requested separately)
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
    🤖 Available Commands:
    
    /start - Start the game
    /help - Show this help message
    /leaderboard - Show the leaderboard with users and their coins
    /bonus - Claim your daily reward (available every 24 hours)
    /redeem <code> - Redeem a valid code for coins
    /store - View items available for purchase
    /buy <item> - Purchase an item from the store
    /stats - (Owner only) Show bot stats
    🎨 Guess the name of anime characters from images!
    """
    bot.reply_to(message, help_message)

### --- 3. Redeem Code Generation --- ###

# Function to automatically generate a new redeem code every 30 minutes and send it to the group
def auto_generate_redeem_code():
    global current_redeem_code, redeem_code_expiry, redeem_code_claims
    while True:
        current_redeem_code = generate_redeem_code()
        redeem_code_expiry = datetime.now() + timedelta(minutes=30)
        redeem_code_claims.clear()  # Reset the claims for the new code

        # Send the new redeem code to the group and all tracked users
        redeem_message = f"🔑 New Redeem Code: **{current_redeem_code}**\nThis code is valid for 30 minutes. Use /redeem <code> to claim coins!"
        bot.send_message(GROUP_CHAT_ID, redeem_message, parse_mode='Markdown')

        # Send the redeem code to each individual chat that interacted with the bot
        for chat_id in user_chat_ids:
            bot.send_message(chat_id, redeem_message, parse_mode='Markdown')

        # Wait for 30 minutes before generating the next code
        time.sleep(1800)

### --- 4. Start Polling the Bot --- ###

# Start the redeem code generation in a separate thread
threading.Thread(target=auto_generate_redeem_code, daemon=True).start()

# Start polling the bot
bot.infinity_polling()
