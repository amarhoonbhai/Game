import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAFaqKS0Z8GzyAR5qk47X8nP7QcJLMCBiok"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats (for /stats)
    print("🝮︎︎︎ Connected to MongoDB 🝮︎︎︎")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

# List of sudo users (user IDs)
SUDO_USERS = [7222795580, 6180999156]  # Add user IDs of sudo users here

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

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_user_rank(user_id):
    user = get_user_data(user_id)
    user_coins = user['coins']

    # Count users with more coins than the current user
    higher_ranked_users = users_collection.count_documents({'coins': {'$gt': user_coins}})
    # Total users
    total_users = users_collection.count_documents({})

    # Rank is one more than the number of users with more coins (as rank 1 is the top player)
    rank = higher_ranked_users + 1

    # Find the user directly above the current user in rank (for "next rank" calculation)
    next_user = users_collection.find_one({'coins': {'$gt': user_coins}}, sort=[('coins', 1)])
    if next_user:
        coins_to_next_rank = next_user['coins'] - user_coins
    else:
        coins_to_next_rank = None  # User is already at the highest rank

    return rank, total_users, coins_to_next_rank

def get_character_data():
    return list(characters_collection.find())

def add_character(image_url, character_name, rarity):
    character_id = characters_collection.count_documents({}) + 1
    character = {
        'id': character_id,
        'image_url': image_url,
        'character_name': character_name,
        'rarity': rarity
    }
    characters_collection.insert_one(character)
    return character

def delete_character(character_id):
    return characters_collection.delete_one({'id': character_id})

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    if characters:
        return random.choice(characters)
    return None

# Sending a character to chat
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
        # Send character image and handle errors if any
        try:
            bot.send_photo(chat_id, current_character['image_url'], caption=caption)
        except Exception as e:
            print(f"Error sending character image: {e}")
            bot.send_message(chat_id, "❌ Unable to send character image.")

def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# Welcome Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    welcome_message = """
<b>🝮︎︎︎ Welcome to Pʜɪʟᴏ 🝮︎︎︎ Gᴀᴍᴇ 🝮︎︎︎</b>

🎮 Ready to dive into the world of anime characters? Let’s start collecting and guessing!

🝮︎︎︎ Use the commands below to explore all the features!
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="Developer - @TechPiro", url="https://t.me/TechPiro")
    markup.add(developer_button)

    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>📜 🝮︎︎︎ Available Commands 🝮︎︎︎ 📜</b>

🎮 <b>Character Commands:</b>
/bonus - Claim your daily bonus 🝮︎︎︎
/inventory - View your character inventory 🝮︎︎︎
/gift - Gift coins to another user by tagging them 🝮︎︎︎
/profile - Show your personal stats (rank, coins, guesses, etc.) 🝮︎︎︎

🏆 <b>Leaderboards:</b>
/leaderboard - Show the top 10 users by coins 🝮︎︎︎
/topcoins - Show the top 10 users by coins earned today 🝮︎︎︎

📊 <b>Bot Stats:</b>
/stats - Show the bot's stats (total users, characters, groups) 🝮︎︎︎

ℹ️ <b>Miscellaneous:</b>
/upload - Upload a new character (Sudo only) 🝮︎︎︎
/delete - Delete a character by ID (Sudo only) 🝮︎︎︎
/help - Show this help message 🝮︎︎︎

🝮︎︎︎ Have fun and start collecting! 🝮︎︎︎
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

# /inventory command with rarity-based pagination and character multiples display (×N for duplicates)
def paginate_inventory(user_id, page=1):
    user = get_user_data(user_id)
    inventory = user.get('inventory', [])

    # Group characters by rarity and count duplicates
    rarity_groups = {
        'Common': {},
        'Rare': {},
        'Epic': {},
        'Legendary': {}
    }

    for character in inventory:
        if isinstance(character, dict):
            rarity = character['rarity']
            name = character['character_name']
            if name in rarity_groups[rarity]:
                rarity_groups[rarity][name] += 1
            else:
                rarity_groups[rarity][name] = 1

    # Prepare the list of all characters in order of rarity
    all_characters = []
    for rarity in ['Legendary', 'Epic', 'Rare', 'Common']:
        for name, count in rarity_groups[rarity].items():
            all_characters.append((name, rarity, count))

    total_items = len(all_characters)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    inventory_page = all_characters[start:end]

    message = f"🎒 **Your Character Inventory (Page {page}/{total_pages}) 🝮︎︎︎:**\n"
    
    # Add rarity headers and format inventory nicely
    current_rarity = None
    for name, rarity, count in inventory_page:
        if current_rarity != rarity:  # Add header if new rarity section starts
            current_rarity = rarity
            message += f"\n<b>🝮︎︎︎ {RARITY_LEVELS[current_rarity]} {current_rarity} 🝮︎︎︎</b>\n"
        message += f"🝮︎︎︎ {name} ×{count}\n"

    return message, total_pages

@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    page = 1
    inventory_message, total_pages = paginate_inventory(user_id, page)

    markup = InlineKeyboardMarkup()
    if total_pages > 1:
        markup.add(InlineKeyboardButton('Next 🝮︎︎︎', callback_data=f'inventory_{page+1}'))

    bot.send_message(message.chat.id, inventory_message, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('inventory_'))
def paginate_inventory_callback(call):
    user_id = call.from_user.id
    page = int(call.data.split('_')[1])

    inventory_message, total_pages = paginate_inventory(user_id, page)

    markup = InlineKeyboardMarkup()
    if page > 1:
        markup.add(InlineKeyboardButton('Previous 🝮︎︎︎', callback_data=f'inventory_{page-1}'))
    if page < total_pages:
        markup.add(InlineKeyboardButton('Next 🝮︎︎︎', callback_data=f'inventory_{page+1}'))

    bot.edit_message_text(inventory_message, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    # Increment the global message count for group chats
    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    # Check if message threshold is reached, then send a new character
    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0  # Reset message count after sending character

    # If there's a current character and the user makes a guess
    if current_character and user_guess:
        character_name = current_character['character_name'].strip().lower()

        # Check if any part of the user's guess matches the character name
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

            bot.reply_to(message, f"🎉 Congratulations! You guessed correctly and earned {COINS_PER_GUESS} coins! 🝮︎︎︎\n"
                                  f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak! 🝮︎︎︎")
            
            # Send a new character immediately after a correct guess
            send_character(chat_id)

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
