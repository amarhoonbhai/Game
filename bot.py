import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
from threading import Thread

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAGr-NtYLYT1Nd2JxgYUr5tdRZSvGr6wQ6g"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats
    print("🝮︎︎︎ Connected to MongoDB 🝮︎︎︎")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# List of sudo users (user IDs)
SUDO_USERS = [BOT_OWNER_ID, 6180999156]  # Add user IDs of sudo users here

bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Additional coins for continuing a streak
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
TOP_LEADERBOARD_LIMIT = 10  # Limit for leaderboard to only show top 10 users
ITEMS_PER_PAGE = 20  # Number of characters per page in inventory

# Global variables to track the current character and message count
current_character = None
global_message_count = 0  # Global counter for messages in all chats

# Helper Functions
def get_user_data(user_id):
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user is None:
            new_user = {
                'user_id': user_id,
                'coins': 0,
                'correct_guesses': 0,
                'inventory': [],
                'last_bonus': None,
                'streak': 0,
                'profile': None
            }
            users_collection.insert_one(new_user)
            return new_user
        return user
    except Exception as e:
        print(f"Error in get_user_data: {e}")
        return None

def update_user_data(user_id, update_data):
    try:
        users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    except Exception as e:
        print(f"Error in update_user_data: {e}")

# Command Handlers

# Leaderboard Command
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    try:
        top_users = users_collection.find().sort('coins', -1).limit(TOP_LEADERBOARD_LIMIT)
        leaderboard_message = "<b>🏆 Top Players Leaderboard 🏆</b>\n\n"
        for rank, user in enumerate(top_users, start=1):
            profile_name = user.get('profile', 'Unknown User')
            coins = user.get('coins', 0)
            leaderboard_message += f"{rank}. {profile_name} - {coins} coins\n"
        bot.reply_to(message, leaderboard_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error in show_leaderboard: {e}")
        bot.reply_to(message, "⚠️ An error occurred while fetching the leaderboard.")

# Top Groups Command
@bot.message_handler(commands=['topgroups'])
def show_top_groups(message):
    try:
        top_groups = groups_collection.find().sort('message_count', -1).limit(TOP_LEADERBOARD_LIMIT)
        top_groups_message = "<b>🏆 Top Groups 🏆</b>\n\n"
        for rank, group in enumerate(top_groups, start=1):
            group_name = group.get('group_name', 'Unknown Group')
            message_count = group.get('message_count', 0)
            top_groups_message += f"{rank}. {group_name} - {message_count} messages\n"
        bot.reply_to(message, top_groups_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error in show_top_groups: {e}")
        bot.reply_to(message, "⚠️ An error occurred while fetching the top groups.")

# Stats Command (Owner Only)
@bot.message_handler(commands=['stats'])
def show_stats(message):
    try:
        if message.from_user.id != BOT_OWNER_ID:
            bot.reply_to(message, "❌ You are not authorized to use this command.")
            return

        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        total_groups = groups_collection.count_documents({})

        stats_message = f"""
<b>🝮︎︎︎ Bot Stats 🝮︎︎︎</b>
👥 Total Users: {total_users}
🎭 Total Characters: {total_characters}
💬 Total Groups: {total_groups}
"""
        bot.reply_to(message, stats_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error in show_stats: {e}")
        bot.reply_to(message, "⚠️ An error occurred while fetching the bot stats.")

# Delete a Character by ID (Sudo Only)
@bot.message_handler(commands=['delete'])
def delete_character_command(message):
    try:
        if message.from_user.id not in SUDO_USERS:
            bot.reply_to(message, "❌ You are not authorized to use this command.")
            return

        msg_parts = message.text.split()
        if len(msg_parts) < 2:
            bot.reply_to(message, "❌ Invalid format. Use /delete <character_id>")
            return

        try:
            character_id = int(msg_parts[1])
        except ValueError:
            bot.reply_to(message, "❌ Invalid character ID. Please provide a numeric ID.")
            return

        result = delete_character(character_id)
        if result.deleted_count > 0:
            bot.reply_to(message, f"🗑 Character with ID {character_id} deleted.")
        else:
            bot.reply_to(message, f"❌ Character with ID {character_id} not found.")
    except Exception as e:
        print(f"Error in delete_character_command: {e}")
        bot.reply_to(message, "⚠️ An error occurred while deleting the character.")

# Add additional helper functions, command handlers as necessary...

# Start polling the bot
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f"Error in bot polling: {e}")
