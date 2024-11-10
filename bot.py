import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configuration
API_TOKEN = "7579121046:AAFKN4ImzXSZWCUGIdofppsD9Uz0cQXmwD8"  # Replace with your actual bot token
BOT_OWNER_ID = 7222795580  # Bot owner's Telegram ID
CHANNEL_ID = -1002438449944  # Channel ID where characters are posted/logged
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
BONUS_COINS = 5000
COINS_PER_GUESS = 50
STREAK_BONUS_COINS = 1000
MESSAGE_THRESHOLD = 5
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💎',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]
TOP_LEADERBOARD_LIMIT = 10

# Setup MongoDB connection
try:
    client = MongoClient(MONGO_URI)
    db = client['game_database']
    users_collection = db['users']
    characters_collection = db['characters']
    sudo_users_collection = db['sudo_users']  # Collection for sudo users
    print("✅ MongoDB connected successfully.")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

bot = telebot.TeleBot(API_TOKEN)

# Correct guess captions
CORRECT_GUESS_CAPTIONS = [
    "🎉 Brilliant guess! You got it right!",
    "🌟 Well done! You truly know your anime characters!",
    "🔥 Amazing! You nailed it!",
    "🥳 Correct! Your anime knowledge is impressive!",
    "🎊 Spot on! Keep up the great guessing!",
    "💥 Bingo! That’s the one!",
    "👏 Fantastic! You’re on fire with these guesses!"
]

# Global variables
current_character = None
global_message_count = 0

# Helper Functions
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'inventory': [],
            'last_bonus': None,
            'streak': 0
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def fetch_new_character():
    characters = list(characters_collection.find())
    return random.choice(characters) if characters else None

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        try:
            bot.send_photo(chat_id, current_character['image_url'], caption=caption)
        except Exception as e:
            print(f"Error sending character image: {e}")
            bot.send_message(chat_id, "❌ Unable to send character image.")

def is_sudo_user(user_id):
    return sudo_users_collection.find_one({'user_id': user_id}) is not None or user_id == BOT_OWNER_ID

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_message = """
<b>Welcome to the Anime Guessing Game!</b>

🎮 Ready to dive into the world of anime characters? Let’s start collecting and guessing!

Use the commands below to explore all the features!
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="Developer", url="https://t.me/YourDeveloperLink")
    markup.add(developer_button)

    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    current_time = datetime.now()

    if user['last_bonus']:
        time_since_last_bonus = current_time - user['last_bonus']
        if time_since_last_bonus < timedelta(days=1):
            time_remaining = timedelta(days=1) - time_since_last_bonus
            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            bot.reply_to(message, f"🎁 You've already claimed your bonus today! Come back in {hours} hours and {minutes} minutes.")
            return

    new_coins = user['coins'] + BONUS_COINS
    user['streak'] += 1
    streak_bonus = STREAK_BONUS_COINS * user['streak']

    update_user_data(user_id, {
        'coins': new_coins + streak_bonus,
        'last_bonus': current_time,
        'streak': user['streak']
    })

    bot.reply_to(message, f"🎉 You claimed your daily bonus of {BONUS_COINS} coins!\n"
                          f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-day streak!")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_sudo_user(message.from_user.id):
        bot.reply_to(message, "🚫 You are not authorized to use this command.")
        return

    parts = message.text.split()
    if len(parts) < 4:
        bot.reply_to(message, "Usage: /upload <image_url> <character_name> <rarity>")
        return

    image_url = parts[1]
    character_name = parts[2]
    rarity = parts[3].capitalize()

    if rarity not in RARITY_LEVELS:
        bot.reply_to(message, f"Invalid rarity! Choose from: {', '.join(RARITY_LEVELS.keys())}")
        return

    character = {
        'image_url': image_url,
        'character_name': character_name,
        'rarity': rarity
    }
    characters_collection.insert_one(character)
    bot.reply_to(message, f"Character '{character_name}' uploaded successfully with {RARITY_LEVELS[rarity]} rarity!")

@bot.message_handler(commands=['addsudo'])
def add_sudo_user(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "🚫 Only the bot owner can add sudo users.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Usage: /addsudo <user_id>")
        return

    new_sudo_user_id = int(parts[1])
    sudo_users_collection.update_one({'user_id': new_sudo_user_id}, {'$set': {'user_id': new_sudo_user_id}}, upsert=True)
    bot.reply_to(message, f"User {new_sudo_user_id} has been added as a sudo user.")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not is_sudo_user(message.from_user.id):
        bot.reply_to(message, "🚫 You are not authorized to view bot stats.")
        return

    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_sudo_users = sudo_users_collection.count_documents({})

    bot.reply_to(message, f"<b>Bot Statistics:</b>\n"
                          f"👥 Total Users: {total_users}\n"
                          f"🎭 Total Characters: {total_characters}\n"
                          f"🔧 Sudo Users: {total_sudo_users}",
                 parse_mode='HTML')

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>Available Commands:</b>

🎮 <b>Gameplay:</b>
/bonus - Claim your daily bonus
/upload <img_url> <name> <rarity> - Upload a new character (Sudo users only)
/addsudo <user_id> - Add a sudo user (Bot owner only)
/stats - View bot statistics (Sudo users only)
/help - Show this help message
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

# Detect guesses in all messages
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0

    if current_character and user_guess:
        character_name = current_character['character_name'].strip().lower()

        if user_guess in character_name:
            user = get_user_data(user_id)
            new_coins = user['coins'] + COINS_PER_GUESS
            user['correct_guesses'] += 1
            user['streak'] += 1
            streak_bonus = STREAK_BONUS_COINS * user['streak']

            update_user_data(user_id, {
                'coins': new_coins + streak_bonus,
                'correct_guesses': user['correct_guesses'],
                'streak': user['streak'],
                'inventory': user['inventory'] + [current_character]
            })

            caption = random.choice(CORRECT_GUESS_CAPTIONS)
            bot.reply_to(message, f"{caption}\nYou earned {COINS_PER_GUESS} coins!\n"
                                  f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak!")
            
            send_character(chat_id)  # Send a new character after a correct guess

# Start polling
bot.infinity_polling(timeout=60, long_polling_timeout=60)
