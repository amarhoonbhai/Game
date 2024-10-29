import os
import telebot
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access environment variables
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB Connection
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_collection = db['sudo_users']  # Collection to store sudo users
    print("Connected to MongoDB")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Settings
CORRECT_GUESS_REWARD = 1000  # Coins rewarded for a correct guess
INCORRECT_GUESS_PENALTY = 500  # Coins deducted for an incorrect guess
DAILY_BONUS = 1000  # Daily bonus coins
TOP_LEADERBOARD_LIMIT = 10

bot = telebot.TeleBot(API_TOKEN)

# Track the last character displayed for each user
last_character_displayed = {}

# Utility function to log errors for the bot owner
def log_owner(message):
    try:
        bot.send_message(BOT_OWNER_ID, message)
    except Exception as e:
        print(f"Logging failed: {e}")

# Check if user is sudo
def is_sudo(user_id):
    return sudo_collection.find_one({"user_id": user_id}) is not None

# Enhanced `/upload` Command with Channel Announcement
@bot.message_handler(commands=['upload'])
def upload_character(message):
    user_id = message.from_user.id
    if user_id != BOT_OWNER_ID and not is_sudo(user_id):
        bot.reply_to(message, "🚫 Unauthorized command.")
        log_owner(f"⚠️ Unauthorized /upload attempt by user {user_id}")
        return

    try:
        _, image_url, character_name, rarity = message.text.split(" ", 3)
        rarity = rarity.capitalize()
    except ValueError:
        bot.reply_to(message, "❗ Incorrect format. Use: /upload <image_url> <character_name> <rarity>")
        return

    if rarity not in ["Common", "Rare", "Epic", "Legendary"]:
        bot.reply_to(message, "❌ Invalid rarity. Use one of: Common, Rare, Epic, Legendary.")
        return

    character = {
        "image_url": image_url,
        "name": character_name,
        "rarity": rarity,
    }

    try:
        characters_collection.insert_one(character)
        bot.reply_to(message, f"🎉 Character '{character_name}' ({rarity}) uploaded successfully!")
        log_owner(f"✅ New character '{character_name}' ({rarity}) added by {'bot owner' if user_id == BOT_OWNER_ID else 'sudo user'} {user_id}.")

        # Announce the new character in the channel
        bot.send_photo(
            CHANNEL_ID,
            photo=image_url,
            caption=(
                f"📢 <b>New Character Added!</b>\n\n"
                f"✨ Name: {character_name}\n"
                f"🌟 Rarity: {rarity}\n\n"
                f"Get ready to guess and win coins! 💰"
            ),
            parse_mode='HTML'
        )

    except errors.PyMongoError as e:
        bot.reply_to(message, "⚠️ Error: Could not upload the character.")
        log_owner(f"🚨 Database error adding character '{character_name}': {e}")

# Enhanced `/profile` Command
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)

    profile_message = (
        f"<b>📝 Your Profile:</b>\n\n"
        f"👤 Username: {user['profile']['username']}\n"
        f"💰 Coins: {user['coins']}\n"
        f"🎯 Correct Guesses: {user['correct_guesses']}\n"
        f"🔥 Streak: {user['streak']} days\n"
    )
    bot.reply_to(message, profile_message, parse_mode='HTML')

# Enhanced `/bonus` Command for Daily Bonus
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = datetime.now()

    if user.get('last_bonus') and (current_time - user['last_bonus']).days < 1:
        bot.reply_to(message, "🕒 Bonus already claimed today! Come back tomorrow.")
    else:
        update_user_data(user_id, {
            'coins': user['coins'] + DAILY_BONUS,
            'last_bonus': current_time
        })
        bot.reply_to(message, f"🎉 Daily Bonus Claimed! You've received {DAILY_BONUS} coins!")

# Enhanced `/topcoins` Leaderboard Command
@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    top_users = users_collection.find().sort('coins', -1).limit(TOP_LEADERBOARD_LIMIT)
    top_message = "<b>🏆 Top 10 Users by Coins</b>\n\n"
    for rank, user in enumerate(top_users, start=1):
        username = user['profile'].get('username', 'Anonymous')
        coins = user['coins']
        top_message += f"{rank}. {username} - {coins} coins 💰\n"
    bot.reply_to(message, top_message, parse_mode='HTML')

# Enhanced Message Handler for Auto-Detecting Rarity Guess
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)

    if user_id not in last_character_displayed:
        return

    character = last_character_displayed[user_id]
    rarity_guessed = message.text.capitalize()

    if rarity_guessed in ["Common", "Rare", "Epic", "Legendary"]:
        if rarity_guessed == character["rarity"]:
            update_user_data(user_id, {
                'coins': user['coins'] + CORRECT_GUESS_REWARD,
                'correct_guesses': user['correct_guesses'] + 1
            })
            bot.reply_to(message, f"🎉 Correct! You earned {CORRECT_GUESS_REWARD} coins!")
            fetch_and_display_character(user_id)
        else:
            if user['coins'] >= INCORRECT_GUESS_PENALTY:
                update_user_data(user_id, {'coins': user['coins'] - INCORRECT_GUESS_PENALTY})
            else:
                update_user_data(user_id, {'coins': 0})

# Command to Start the Game
@bot.message_handler(commands=['startgame'])
def start_game(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "🎲 Let's begin the guessing game!")
    fetch_and_display_character(user_id)

# Utility Functions
def get_user_data(user_id, username=None):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'last_bonus': None,
            'streak': 0,
            'profile': {
                'username': username or "Anonymous",
                'profile_link': f"https://t.me/{username}" if username else f"https://t.me/user?id={user_id}"
            }
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    try:
        users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    except errors.PyMongoError as e:
        log_owner(f"Database update error for user {user_id}: {e}")

def fetch_and_display_character(user_id):
    character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    character_data = {
        "name": character["name"],
        "rarity": character["rarity"],
        "image_url": character["image_url"]
    }
    last_character_displayed[user_id] = character_data

    bot.send_photo(
        user_id,
        photo=character_data['image_url'],
        caption=(
            f"✨ <b>{character_data['name']} just appeared!</b> ✨\n\n"
            "🤔 <b>Can you guess its rarity?</b>\n"
            "👉 <i>Choose:</i> Common, Rare, Epic, or Legendary\n\n"
            "💸 <b>Win coins for the right guess!</b> Good luck! 🍀"
        ),
        parse_mode='HTML'
    )

bot.infinity_polling(timeout=60, long_polling_timeout=60)
