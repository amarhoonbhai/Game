import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = "7579121046:AAHXwXrOgIjIeSPQIOSMJ8bVtamLmsWzHIk"
CHANNEL_ID = -1002438449944
BOT_OWNER_ID = 7222795580

MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
client = MongoClient(MONGO_URI)
db = client['philo_grabber']
users_collection = db['users']
characters_collection = db['characters']

bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 5000
BONUS_INTERVAL = timedelta(days=1)
COINS_PER_GUESS = 50
LEVEL_UP_REQUIREMENT = 5
MESSAGE_THRESHOLD = 5
current_character = None
global_message_count = 0

captions = [
    "🎉 Awesome! You got it right!",
    "🌟 That’s correct! Great job!",
    "🎊 Impressive! Another one down!",
    "🔥 You’re on fire!",
    "🎈 Well done! You’ve earned more coins!",
    "🥳 Correct! Keep going!",
    "🎆 Another great guess!"
]

# Commands for admin access
SUDO_USERS = [BOT_OWNER_ID]  # Add additional user IDs if needed

# Helper functions
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'level': 1,
            'last_bonus': None,
            'streak': 0,
            'profile': None,
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def send_character(chat_id):
    global current_character
    current_character = random.choice(list(characters_collection.find()))  # Random character
    caption = f"🔍 Guess the Character!\n\n🌌 Name: ???\n🌟 Rarity: {current_character['rarity']}"
    try:
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)
    except Exception as e:
        bot.send_message(chat_id, "❌ Couldn’t send character image.")
        print(f"Error sending character image: {e}")

def handle_correct_guess(user, chat_id):
    user['coins'] += COINS_PER_GUESS
    user['correct_guesses'] += 1
    if user['correct_guesses'] % LEVEL_UP_REQUIREMENT == 0:
        user['level'] += 1
        bot.send_message(chat_id, f"✨ Level Up! You’re now level {user['level']}!")
    update_user_data(user['user_id'], user)
    bot.send_message(chat_id, random.choice(captions))
    send_character(chat_id)

# Command Handlers
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()
    if user['last_bonus']:
        time_since_bonus = current_time - user['last_bonus']
        if time_since_bonus < BONUS_INTERVAL:
            remaining_time = BONUS_INTERVAL - time_since_bonus
            bot.reply_to(message, f"💸 Already claimed! Come back in {remaining_time}.")
            return
    user['coins'] += BONUS_COINS
    user['last_bonus'] = current_time
    update_user_data(user_id, user)
    bot.reply_to(message, f"🎁 Bonus claimed! You’ve received {BONUS_COINS} coins.")

@bot.message_handler(commands=['profile'])
def profile(message):
    user = get_user_data(message.from_user.id)
    bot.reply_to(message, f"👤 Profile:\nCoins: {user['coins']}\nLevel: {user['level']}\nCorrect Guesses: {user['correct_guesses']}")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    leaderboard = users_collection.find().sort("coins", -1).limit(10)
    leaderboard_text = "🏆 Top 10 Users 🏆\n"
    for rank, user in enumerate(leaderboard, start=1):
        leaderboard_text += f"{rank}. User {user['user_id']}: {user['coins']} coins\n"
    bot.reply_to(message, leaderboard_text)

@bot.message_handler(commands=['stats'])
def stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    bot.reply_to(message, f"📊 Bot Stats:\nUsers: {total_users}\nCharacters: {total_characters}")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.id in SUDO_USERS:
        try:
            _, img_url, name = message.text.split(maxsplit=2)
            rarity = random.choice(['Common', 'Rare', 'Epic', 'Legendary'])
            characters_collection.insert_one({'image_url': img_url, 'character_name': name, 'rarity': rarity})
            bot.reply_to(message, f"🖼️ Character {name} added with rarity {rarity}!")
        except ValueError:
            bot.reply_to(message, "❌ Invalid format. Use: /upload <img_url> <character_name>")

@bot.message_handler(commands=['addsudo'])
def add_sudo(message):
    if message.from_user.id == BOT_OWNER_ID:
        try:
            _, user_id = message.text.split(maxsplit=1)
            user_id = int(user_id)
            if user_id not in SUDO_USERS:
                SUDO_USERS.append(user_id)
                bot.reply_to(message, f"✅ User {user_id} has been added as a sudo user.")
            else:
                bot.reply_to(message, f"⚠️ User {user_id} is already a sudo user.")
        except ValueError:
            bot.reply_to(message, "❌ Invalid format. Use: /addsudo <user_id>")

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🌟 Welcome to the Bot! Use /help for all commands.")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, """
    🎉 Available Commands:
    /bonus - Claim daily bonus
    /profile - Show your profile
    /leaderboard - Show leaderboard
    /stats - Bot statistics
    /upload - Upload a character (admin)
    /addsudo - Add a sudo user (owner only)
    """)

# Automatic Guess Detection and Message Counter
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global global_message_count
    global current_character
    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1
        if global_message_count >= MESSAGE_THRESHOLD:
            send_character(message.chat.id)
            global_message_count = 0

    if current_character and current_character['character_name'].lower() in message.text.lower():
        user = get_user_data(message.from_user.id)
        handle_correct_guess(user, message.chat.id)

bot.infinity_polling()
