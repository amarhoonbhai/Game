import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = "6862816736:AAGP7FEk2AkT4gWqMgShsvSfCYnfIgVFLO4"
BOT_OWNER_ID = 1234567890  # Replace with the owner's Telegram ID
CHANNEL_ID = -100123456789  # Replace with your Telegram channel ID

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://username:password@cluster.mongodb.net/mydatabase?retryWrites=true&w=majority"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats
    print("Connected to MongoDB")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# Settings
BONUS_COINS = 50000  # Daily bonus
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Bonus for continuing a streak
RARITY_LEVELS = {'Common': '⭐', 'Rare': '🌟', 'Epic': '💫', 'Legendary': '✨'}
RARITY_WEIGHTS = [60, 25, 10, 5]
TOP_LEADERBOARD_LIMIT = 10  # Limit for top coins leaderboard

bot = telebot.TeleBot(API_TOKEN)

# Get or create user data
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'last_bonus': None,
            'streak': 0,
            'profile': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

# Topcoins Command Handler
@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    top_users = users_collection.find().sort('coins', -1).limit(TOP_LEADERBOARD_LIMIT)
    top_message = "<b>🏆 Top 10 Users by Coins 🝮︎︎︎</b>\n\n"
    for rank, user in enumerate(top_users, start=1):
        top_message += f"{rank}. {user.get('profile', 'Anonymous')} - {user['coins']} coins 🝮︎︎︎\n"
    bot.reply_to(message, top_message, parse_mode='HTML')

# Bonus Command Handler
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()
    base_bonus = BONUS_COINS

    # Check last bonus time
    if user['last_bonus']:
        time_since_last_bonus = current_time - user['last_bonus']
        if time_since_last_bonus < timedelta(days=1):
            time_remaining = timedelta(days=1) - time_since_last_bonus
            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"🝮︎︎︎ Bonus already claimed today! Return in {hours}h {minutes}m.")
            return
        
    # Award bonus
    user['streak'] += 1
    streak_bonus = STREAK_BONUS_COINS * user['streak']
    total_bonus = base_bonus + streak_bonus

    update_user_data(user_id, {
        'coins': user['coins'] + total_bonus,
        'last_bonus': current_time,
        'streak': user['streak']
    })

    bot.reply_to(message, f"🎁 Daily Bonus: {base_bonus} coins\n"
                          f"🔥 Streak Bonus: +{streak_bonus} coins for {user['streak']} days!\n"
                          f"Total: {total_bonus} coins 🝮︎︎︎")

# Help Command
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>📜 🝮︎︎︎ Available Commands 🝮︎︎︎ 📜</b>
🎮 <b>Character Commands:</b>
/bonus - Claim your daily bonus 🝮︎︎︎
/topcoins - Show the top 10 users by coins 🝮︎︎︎

📊 <b>Bot Stats:</b>
/stats - Show the bot's stats (total users, characters, groups) 🝮︎︎︎

ℹ️ <b>Miscellaneous:</b>
/upload - Upload a new character (Sudo only) 🝮︎︎︎
/delete - Delete a character by ID (Sudo only) 🝮︎︎︎
/help - Show this help message 🝮︎︎︎
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
