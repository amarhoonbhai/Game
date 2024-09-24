import telebot
import random
import threading
import time
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and owner ID
API_TOKEN = "7740301929:AAHY8CI8o8WcspwtHLj5vUip024z1oVZTw4"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
MONGO_URI = "mongodb+srv://philoamar825:FlashShine@cluster0.7ulvo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB connection string
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with the actual channel ID to log uploaded characters

# Initialize Telegram Bot and MongoDB
bot = telebot.TeleBot(API_TOKEN)
client = MongoClient(MONGO_URI)
db = client['character_database']  # MongoDB database
character_collection = db['characters']  # Collection for storing character data

user_last_bonus = {}   # To track the last bonus claim time of each user
user_coins = {}  # Dictionary to track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)

# Coins awarded for correct guesses and bonus
COINS_PER_GUESS = 10
COINS_PER_BONUS = 100  # Bonus coins for daily reward

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

# /start command - Starts the game
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_profiles[message.from_user.id] = message.from_user.username or message.from_user.first_name
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
    🎮 Guess the name of anime characters from images!
    """
    bot.reply_to(message, help_message)

### --- 3. Message Handling --- ###

# Function to handle guesses and increment message counter
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_guess = message.text.strip().lower()

    # Store user's profile name
    user_profiles[message.from_user.id] = message.from_user.username or message.from_user.first_name

    # Fetch a random character from the database
    character = fetch_random_character()
    
    if character and user_guess == character['character_name']:
        # Correct guess
        add_coins(user_id, COINS_PER_GUESS)  # Award coins for correct guess
        bot.reply_to(message, f"🎉 **Congratulations!** You guessed correctly and earned **{COINS_PER_GUESS}** coins!", parse_mode='Markdown')
        send_character(chat_id, fetch_random_character())  # Send a new character
    else:
        # No incorrect guess messages or revealing the correct name
        send_character(chat_id, character)  # Resend the current character for guessing

### --- 4. Start Polling the Bot --- ###

# Start polling the bot
bot.infinity_polling()
