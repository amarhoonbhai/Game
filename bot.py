import telebot
import random
import threading
import time
from datetime import datetime
from pymongo import MongoClient

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAGp98173eXRUZ86DvxyYQy6RDLtRawbzdw"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Define bot owner and sudo users
bot_owner_id = "7222795580"   # Replace with your Telegram user ID
sudo_users = "6180999156"  # Add other sudo user IDs if necessary

# MongoDB Setup
MONGO_URI = "mongodb+srv://philoamar825:FlashShine@cluster0.7ulvo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB connection string
client = MongoClient(MONGO_URI)
db = client['anime_game']  # Database name
characters_collection = db['characters']
players_collection = db['players']

# Helper function to get player data from MongoDB
def get_player_data(user_id, username):
    player = players_collection.find_one({"user_id": user_id})
    if not player:
        # Add a new player if not found
        player = {
            "user_id": user_id,
            "username": username,
            "coins": 0,
            "correct_guesses": 0,
            "streak": 0,
            "last_daily": None
        }
        players_collection.insert_one(player)
    return player

# Update player data in MongoDB
def update_player_data(user_id, coins=None, correct_guesses=None, streak=None, last_daily=None):
    player = get_player_data(user_id, "")
    updated_data = {
        "coins": coins if coins is not None else player["coins"],
        "correct_guesses": correct_guesses if correct_guesses is not None else player["correct_guesses"],
        "streak": streak if streak is not None else player["streak"],
        "last_daily": last_daily if last_daily is not None else player["last_daily"]
    }
    players_collection.update_one({"user_id": user_id}, {"$set": updated_data})

# Store character data (image URL and rarity) in MongoDB
def store_character(image_url, rarity):
    character = {"image_url": image_url, "rarity": rarity}
    characters_collection.insert_one(character)

# Get a random character from MongoDB
def get_random_character():
    characters = list(characters_collection.find())
    if not characters:
        return None
    return random.choice(characters)

# Check if the user is an owner or sudo user
def is_owner_or_sudo(user_id):
    return user_id == bot_owner_id or user_id in sudo_users

# Upload Command - For bot owner and sudo users to upload characters via image URL
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_owner_or_sudo(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    # Check if the message contains the image URL and rarity
    command_parts = message.text.split()
    if len(command_parts) == 3:
        image_url = command_parts[1]
        rarity = command_parts[2].lower()

        if rarity not in ['elite', 'epic', 'legendary', 'mythical']:
            bot.reply_to(message, "❌ Invalid rarity! Use: Elite-⚡, Epic-💫, Legendary-🥂, Mythical-🔮.")
            return

        # Store the character's image URL and rarity in MongoDB
        store_character(image_url, rarity)
        bot.reply_to(message, f"✅ Character uploaded successfully with rarity: {rarity.capitalize()}")
    else:
        bot.reply_to(message, "❌ Please provide both an image URL and a rarity (Elite-⚡, Epic-💫, Legendary-🥂, Mythical-🔮). Example: /upload https://image.url Epic")

# Start Command - Starts the bot and automatically begins sending images
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /upload to add characters with image URLs and rarity. Use /help to see all available commands.")
    # Automatically start sending images after 10 seconds
    threading.Thread(target=automatic_image_sending, args=(message.chat.id,)).start()

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/upload <image_url> <rarity> - (Sudo/Owner only) Upload a character by image URL and its rarity (Elite-⚡, Epic-💫, Legendary-🥂, Mythical-🔮)
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/help - Show this help message
"""
    bot.reply_to(message, help_message)

# Automatically send random images every 10 seconds
def automatic_image_sending(chat_id):
    while True:
        send_random_character(chat_id)
        time.sleep(10)

# Send a random character to the chat
def send_random_character(chat_id):
    character = get_random_character()
    if character is None:
        bot.send_message(chat_id, "Sorry, no characters have been uploaded yet. Please ask the admin to upload some.")
        return

    # Extract image_url and rarity
    image_url = character["image_url"]
    rarity = character["rarity"]

    # Assign rarity emoji
    rarity_emojis = {
        'elite': '⚡',
        'epic': '💫',
        'legendary': '🥂',
        'mythical': '🔮'
    }
    rarity_emoji = rarity_emojis.get(rarity, '')

    # Send the character image URL with rarity
    bot.send_photo(chat_id, image_url, caption=f"Guess the name of this anime character! Rarity: {rarity.capitalize()} {rarity_emoji}")

# Daily Reward Command - Claim a daily reward
@bot.message_handler(commands=['daily_reward'])
def daily_reward(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Get player data
    player = get_player_data(user_id, username)
    now = datetime.now()
    last_claim = player["last_daily"]

    # Check if 24 hours have passed since the last claim
    if last_claim is None or (now - datetime.fromisoformat(last_claim)).days >= 1:
        # Award 50 coins for daily reward
        new_coins = player["coins"] + 50
        update_player_data(user_id, coins=new_coins, last_daily=now.isoformat())
        bot.reply_to(message, f"🎁 You claimed your daily reward of 50 coins! Total coins: {new_coins}")
    else:
        bot.reply_to(message, "🕒 You have already claimed your daily reward. Come back tomorrow!")

# Leaderboard Command - Displays the Top Players by Coins and Correct Guesses
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    players = list(players_collection.find().sort("coins", -1).limit(10))

    leaderboard_message = "🏆 Leaderboard:\n"
    for rank, player in enumerate(players, start=1):
        leaderboard_message += f"{rank}. {player['username']}: {player['coins']} coins, {player['correct_guesses']} correct guesses, {player['streak']} streak\n"

    bot.reply_to(message, leaderboard_message)

# Guess Handler - Detect User Messages for Guesses
@bot.message_handler(func=lambda message: True)
def detect_guess(message):
    guess_text = message.text.lower()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Check if this message is a guess and if the user matches the active game
    if hasattr(bot, 'current_image_url'):
        # Get player data
        player = get_player_data(user_id, username)

        if guess_text == "some correct answer":  # Replace this with actual logic for correct answer
            # Correct guess: Add 10 coins + streak bonus (5 coins per streak)
            streak = player["streak"] + 1  # Increase streak
            coins_awarded = 10 + (5 * streak)  # Add bonus for streak
            new_coins = player["coins"] + coins_awarded
            new_correct_guesses = player["correct_guesses"] + 1
            update_player_data(user_id, coins=new_coins, correct_guesses=new_correct_guesses, streak=streak)
            bot.reply_to(message, f"🎉 Correct! You've earned {coins_awarded} coins (with a streak of {streak}). Total coins: {new_coins}. A new character will be fetched in 30 seconds.")
            # Fetch a new character after 30 seconds
            threading.Thread(target=automatic_image_sending, args=(message.chat.id,)).start()
        else:
            bot.incorrect_guess_count += 1
            bot.reply_to(message, "❌ Wrong! Try again.")

# Run the bot
bot.infinity_polling()
