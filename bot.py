import telebot
import random
import threading
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import ssl

# Replace with your actual bot API token and owner ID
API_TOKEN = "7740301929:AAGaX84MeVFn0neJ9y0qOI2CLXg9HDywIkw"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
MONGO_URI = "mongodb+srv://philoamar825:FlashShine@cluster0.7ulvo.mongodb.net/mydatabase?retryWrites=true&w=majority&appName=Cluster0"
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with the actual channel ID to log uploaded characters
GROUP_CHAT_ID = -1001548130580  # Replace with your group chat ID where codes will be sent

# Initialize Telegram Bot and MongoDB client with SSL verification disabled
client = MongoClient(MONGO_URI, ssl=True, ssl_cert_reqs=ssl.CERT_NONE)
db = client['mydatabase']  # Replace 'mydatabase' with the actual database name
character_collection = db['characters']  # Collection for storing character data

# Initialize bot
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

# Rarity levels for characters
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}

### --- 1. Helper Functions --- ###

# Function to check if the user is an admin or owner
def is_admin_or_owner(message):
    if message.from_user.id == BOT_OWNER_ID:
        return True
    chat_admins = bot.get_chat_administrators(message.chat.id)
    return message.from_user.id in [admin.user.id for admin in chat_admins]

# Function to add coins to the user's balance
def add_coins(user_id, coins):
    if user_id not in user_coins:
        user_coins[user_id] = 0
    user_coins[user_id] += coins

# Function to fetch a random character from the database
def fetch_random_character():
    characters = list(character_collection.find())
    if characters:
        return random.choice(characters)
    return None

# Function to format and send a character with an attractive caption
def send_character(chat_id, character):
    if character:
        rarity = character['rarity']
        emoji_rarity = RARITY_LEVELS.get(rarity, '⭐')
        caption = (
            f"🎨 **Guess the Character!**\n\n"
            f"💬 **Name**: ???\n"
            f"⚔️ **Rarity**: {emoji_rarity} {rarity}\n\n"
            f"🌟 Can you guess this amazing character? Let's see!"
        )
        bot.send_photo(chat_id, character['image_url'], caption=caption, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "⚠️ No characters available in the database!")

# Function to check if the user can claim the bonus (daily reward)
def can_claim_bonus(user_id):
    now = datetime.now()
    last_bonus = user_last_bonus.get(user_id)
    return last_bonus is None or (now - last_bonus).days >= 1

# Function to generate a random 4-digit redeem code
def generate_redeem_code():
    return ''.join(random.choices('0123456789', k=4))

### --- 2. Command Handlers --- ###

# /upload command - Allows the owner and admins to upload a new character
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return
    
    # Expecting the format: /upload <image_url> <character_name> <rarity>
    try:
        _, image_url, character_name, rarity = message.text.split(maxsplit=3)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name> <rarity>")
        return

    if rarity not in RARITY_LEVELS:
        bot.reply_to(message, "⚠️ Invalid rarity. Choose from: Common, Rare, Epic, Legendary.")
        return

    try:
        # Add the character to the MongoDB database
        character = {
            'image_url': image_url,
            'character_name': character_name.lower(),  # Store names in lowercase for easier comparison
            'rarity': rarity
        }
        character_collection.insert_one(character)
        
        # Send confirmation message and log to the character channel
        bot.reply_to(message, f"✅ Character '{character_name}' has been uploaded successfully with rarity '{rarity}'!")
        bot.send_message(CHARACTER_CHANNEL_ID, f"📥 New character uploaded:\n\nName: {character_name}\nRarity: {rarity}")
    
    except Exception as e:
        # Log any errors during the MongoDB insertion process
        bot.reply_to(message, f"❌ Error while adding character to the database: {e}")

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

# /start command - Starts the game
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_profiles[message.from_user.id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)  # Track chat IDs for sending redeem codes
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Guess the character name.")
    character = fetch_random_character()
    send_character(chat_id, character)

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
        profile_name = user_profiles.get(user_id, "Unknown")
        leaderboard_message += f"{rank}. **{profile_name}**: 💰 {coins} coins\n"

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

# /help command - Lists all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
    🤖 Available Commands:
    
    /start - Start the game
    /help - Show this help message
    /leaderboard - Show the leaderboard with users and their coins
    /bonus - Claim your daily reward (available every 24 hours)
    /upload <image_url> <character_name> <rarity> - (Admins only) Upload a new character
    /redeem <code> - Redeem a valid code for coins
    /stats - (Owner only) Show bot stats
    🎮 Guess the name of anime characters from images!
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
