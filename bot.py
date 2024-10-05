import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7825167784:AAGgUzso3OLGCeLwF0oWxTtVOi1PO-XRGTI"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats
    print("Connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    exit()  # Exit if connection fails

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)

# Settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
STREAK_BONUS_COINS = 1000  # Additional coins for continuing a streak
MESSAGE_THRESHOLD = 5  # Number of messages before sending a new character
current_character = None
global_message_count = 0  # Global counter for messages in all chats
REMINDER_INTERVAL = 3600  # Reminder interval in seconds (1 hour)

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
            'profile': None,
            'username': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_group_data(group_id):
    group = groups_collection.find_one({'group_id': group_id})
    if group is None:
        new_group = {
            'group_id': group_id,
            'group_name': None,
            'message_count': 0
        }
        groups_collection.insert_one(new_group)
        return new_group
    return group

def update_group_data(group_id, update_data):
    groups_collection.update_one({'group_id': group_id}, {'$set': update_data})

# Add send_character function to send characters
def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = current_character['rarity']
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity}\n"
        )
        try:
            bot.send_photo(chat_id, current_character['image_url'], caption=caption)
        except Exception as e:
            print(f"Error sending character image: {e}")
            bot.send_message(chat_id, "❌ Unable to send character image.")

# Fetch a new character from the database
def fetch_new_character():
    characters = get_character_data()
    if characters:
        return random.choice(characters)
    return None

def get_character_data():
    return list(characters_collection.find())

# /inventory command to show the user's characters grouped by rarity
@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})

    if user is None or not user.get('inventory'):
        bot.reply_to(message, "🚨 <b>Your inventory is empty!</b> Start collecting characters and build your collection.")
        return

    # Group characters by rarity and count occurrences
    inventory_by_rarity = {
        'Common': {},
        'Rare': {},
        'Epic': {},
        'Legendary': {}
    }

    for character in user['inventory']:
        rarity = character.get('rarity', 'Unknown')
        character_name = character['character_name']
        
        # Count the characters
        if character_name in inventory_by_rarity[rarity]:
            inventory_by_rarity[rarity][character_name] += 1
        else:
            inventory_by_rarity[rarity][character_name] = 1

    # Start with a stylish header
    inventory_message = f"""
<b>🌟 {user.get('profile', 'Unknown User')}'s Personal Character Vault 🌟</b>\n
<i>Step into the realm of greatness and witness the power of your collection!</i>\n\n
"""

    # Rarity title with style
    rarity_titles = {
        'Common': '<b>Common</b> — The Foundation of Heroes',
        'Rare': '<b>Rare</b> — The Shining Elite',
        'Epic': '<b>Epic</b> — The Champions of Legends',
        'Legendary': '<b>Legendary</b> — The Immortal Mythics'
    }

    # Construct the message for each rarity
    for rarity, characters in inventory_by_rarity.items():
        if characters:
            inventory_message += f"🔹 {rarity_titles[rarity]}:\n"
            for character_name, count in characters.items():
                inventory_message += f"  • <b>{character_name}</b> ×<b>{count}</b>\n"
            inventory_message += "\n"  # Add space between rarity sections

    # Add a motivational footer
    inventory_message += "<i>🔥 Forge ahead, your legend awaits. Continue collecting and dominate the realms! 🔥</i>"

    bot.reply_to(message, inventory_message, parse_mode='HTML')

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Check if the message is from a group or user chat
    if message.chat.type in ['group', 'supergroup']:
        # Group message, update the group data
        group_data = get_group_data(chat_id)
        new_message_count = group_data['message_count'] + 1
        update_group_data(chat_id, {'message_count': new_message_count})
    
    user_guess = message.text.strip().lower() if message.text else ""

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
            bot.reply_to(message, f"🎉 Congratulations! You guessed correctly and earned {COINS_PER_GUESS} coins!\n"
                                  f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak!")
            send_character(chat_id)
        else:
            update_user_data(user_id, {'streak': 0})

# Start polling the bot
print("Bot is running...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
