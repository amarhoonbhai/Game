import telebot
import random
import threading
import time
import requests
from pymongo import MongoClient
from datetime import datetime, timedelta

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAGJ_2R6ThDTk7C8ZaAfo5FS_CeW2BctVeI"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# MongoDB Setup
MONGO_URI = "mongodb+srv://philoamar825:FlashShine@cluster0.7ulvo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB connection string
client = MongoClient(MONGO_URI)
db = client['anime_game']  # Database name
characters_collection = db['characters']  # Collection for characters
users_collection = db['users']  # Collection for users

# Define bot owner and sudo users
bot_owner_id = "7222795580"  # Replace with your Telegram user ID
sudo_users = "6180999156"  # Add other sudo user IDs if necessary

# Define the log channel ID
log_channel_id = "-1002438449944"  # Replace with your character/log channel ID

# Rarity levels
RARITY_LEVELS = {
    'elite': '⚡',
    'epic': '💫',
    'legendary': '🥂',
    'mythical': '🔮'
}

# Current character being displayed (we'll store its image URL, name, and rarity)
current_character = {
    "image_url": None,
    "name": None,
    "rarity": None
}

# Track users and groups
unique_users = set()
unique_groups = set()

# Track users and groups for statistics
def track_user_and_group(message):
    if message.chat.type == 'private':
        unique_users.add(message.from_user.id)  # Track unique user
    elif message.chat.type in ['group', 'supergroup']:
        unique_groups.add(message.chat.id)  # Track unique group

# Get player data from MongoDB
def get_player_data(user_id, username):
    player = users_collection.find_one({"user_id": user_id})
    if not player:
        player = {
            "user_id": user_id,
            "username": username,
            "coins": 0,
            "correct_guesses": 0,
            "streak": 0,
            "last_daily": None,
            "last_redeem": None
        }
        users_collection.insert_one(player)
    return player

# Update player data in MongoDB
def update_player_data(user_id, coins=None, correct_guesses=None, streak=None, last_daily=None, last_redeem=None):
    player = get_player_data(user_id, "")
    updated_data = {
        "coins": coins if coins is not None else player["coins"],
        "correct_guesses": correct_guesses if correct_guesses is not None else player["correct_guesses"],
        "streak": streak if streak is not None else player["streak"],
        "last_daily": last_daily if last_daily is not None else player["last_daily"],
        "last_redeem": last_redeem if last_redeem is not None else player["last_redeem"]
    }
    users_collection.update_one({"user_id": user_id}, {"$set": updated_data})

# Store uploaded character in MongoDB
def store_character(image_url, name, rarity):
    character = {"image_url": image_url, "name": name.lower(), "rarity": rarity}
    characters_collection.insert_one(character)

# Fetch a random character from MongoDB
def get_random_character():
    characters = list(characters_collection.find())
    if not characters:
        return None
    return random.choice(characters)

# Upload Command - For bot owner and sudo users to upload characters via image URL
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not (message.from_user.id == bot_owner_id or message.from_user.id in sudo_users):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    # Format should be: /upload <image_url> <name> <rarity>
    command_parts = message.text.split()
    if len(command_parts) == 4:
        image_url = command_parts[1]
        name = command_parts[2].lower()
        rarity = command_parts[3].lower()

        if rarity not in RARITY_LEVELS:
            bot.reply_to(message, "❌ Invalid rarity! Use: Elite ⚡, Epic 💫, Legendary 🥂, Mythical 🔮.")
            return

        # Store character in MongoDB
        store_character(image_url, name, rarity)

        bot.reply_to(message, f"✅ Character '{name.capitalize()}' uploaded successfully with rarity: {rarity.capitalize()}")

        # Log the character upload to the log channel
        bot.send_message(log_channel_id, f"📥 A new character was uploaded:\nName: {name.capitalize()}\nRarity: {rarity.capitalize()}\nUploaded by: {message.from_user.first_name}")
    else:
        bot.reply_to(message, "❌ Incorrect format. Use: /upload <image_url> <name> <rarity>")

# Start Command - Starts the bot and shows a welcome message
@bot.message_handler(commands=['start'])
def send_welcome(message):
    track_user_and_group(message)
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /help for available commands.")

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    track_user_and_group(message)
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/upload <image_url> <name> <rarity> - (Sudo/Owner only) Upload a character by image URL, name, and rarity (Elite ⚡, Epic 💫, Legendary 🥂, Mythical 🔮)
/redeem - Redeem coins (available every hour)
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/help - Show this help message
"""
    bot.reply_to(message, help_message)

# Send a random character to the chat
def send_random_character(chat_id):
    global current_character

    character = get_random_character()
    if not character:
        bot.send_message(chat_id, "No characters have been uploaded yet. Please ask an admin to upload some.")
        return

    # Extract image_url, name, and rarity
    image_url = character["image_url"]
    name = character["name"]
    rarity = character["rarity"]

    # Assign rarity emoji
    rarity_emoji = RARITY_LEVELS.get(rarity, '')

    # Store the current character for future guessing
    current_character["image_url"] = image_url
    current_character["name"] = name
    current_character["rarity"] = rarity

    # Send the character image with an attractive caption
    attractive_captions = [
        f"✨ Behold! An {rarity.capitalize()} waifu has appeared! {rarity_emoji}",
        f"💖 Feast your eyes on this beautiful {rarity.capitalize()} waifu! {rarity_emoji}",
        f"🌟 A rare gem just for you! Here's an {rarity.capitalize()} waifu! {rarity_emoji}",
        f"🔥 You’re lucky! An {rarity.capitalize()} character is here to charm you! {rarity_emoji}"
    ]
    caption = random.choice(attractive_captions)

    # Send the image with the attractive caption
    bot.send_photo(chat_id, image_url, caption=caption)

    # Log this character to the log channel (without the URL)
    bot.send_message(log_channel_id, f"Character displayed:\nName: {name.capitalize()}\nRarity: {rarity.capitalize()}")

# Award coins and streak bonus for a correct guess
def award_coins(user_id, username):
    player = get_player_data(user_id, username)
    
    # Base coins for a correct guess
    base_coins = 10
    # Bonus coins for streak (5 coins per streak level)
    streak_bonus = 5 * player["streak"]

    # Update player's streak, coins, and correct guesses
    player["streak"] += 1  # Increase streak
    player["correct_guesses"] += 1  # Increase correct guesses
    player["coins"] += base_coins + streak_bonus  # Add coins with bonus

    # Save updated player data
    update_player_data(user_id, coins=player["coins"], correct_guesses=player["correct_guesses"], streak=player["streak"])

    # Notify the user of their reward
    bot.reply_to(message, f"🎉 Congratulations {username}! You guessed correctly and earned {base_coins + streak_bonus} coins (Base: {base_coins} + Streak Bonus: {streak_bonus}). Total coins: {player['coins']} (Streak: {player['streak']})")

# Reset streak on an incorrect guess
def reset_streak(user_id):
    if user_id in players_data:
        update_player_data(user_id, streak=0)  # Reset the streak

# Handle guesses from users
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    global current_character

    # Normalize guess text
    guess_text = message.text.strip().lower()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if guess_text == current_character["name"]:
        # Award coins and streak bonus for a correct guess
        award_coins(user_id, username)
        # Fetch and send a new character immediately after a correct guess
        send_random_character(message.chat.id)
    else:
        bot.reply_to(message, "❌ Incorrect guess, try again!")
        # Reset the player's streak on incorrect guess
        reset_streak(user_id)

# Redeem Command - Allows users to redeem coins every hour
@bot.message_handler(commands=['redeem'])
def redeem_coins(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Get player data
    player = get_player_data(user_id, username)
    now = datetime.now()

    # Check if the user has redeemed within the last hour
    if player["last_redeem"] is None or (now - player["last_redeem"]) >= timedelta(hours=1):
        # Award 20 coins for redeeming
        new_coins = player["coins"] + 20
        update_player_data(user_id, coins=new_coins, last_redeem=now)

        bot.reply_to(message, f"🎉 You redeemed 20 coins! Total coins: {new_coins}")
    else:
        time_left = timedelta(hours=1) - (now - player["last_redeem"])
        minutes_left = time_left.seconds // 60
        bot.reply_to(message, f"⏳ You can redeem again in {minutes_left} minutes.")

# Run the bot
bot.infinity_polling()
