# bot.py

import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_TOKEN, MONGO_URI, BONUS_COINS, STREAK_BONUS_COINS, BONUS_INTERVAL, \
                   RARITY_LEVELS, RARITY_WEIGHTS, MESSAGE_THRESHOLD, BOT_OWNER_ID, CHARACTER_CHANNEL_ID

# Initialize bot and MongoDB client
bot = telebot.TeleBot(API_TOKEN)
client = MongoClient(MONGO_URI)
db = client['philo_game']
users_collection = db['users']
characters_collection = db['characters']
groups_collection = db['groups']
sudo_users_collection = db['sudo_users']  # Collection for storing sudo users

# Initialize sudo users
SUDO_USERS = {BOT_OWNER_ID}  # Start with the bot owner as a sudo user

# Load sudo users from the database
def load_sudo_users():
    sudo_users = sudo_users_collection.find()
    for user in sudo_users:
        SUDO_USERS.add(user['user_id'])

load_sudo_users()

### Database Functions ###
def get_user_data(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        new_user = {
            'user_id': user_id,
            'coins': 0,
            'correct_guesses': 0,
            'streak': 0,
            'profile': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

### Game Functions ###
def fetch_random_character():
    try:
        # Fetch all characters from MongoDB
        characters = list(characters_collection.find())
        if not characters:
            print("No characters available in the database.")
            return None

        # Select a random character from the database
        random_character = random.choice(characters)
        return random_character
    except Exception as e:
        print(f"Error fetching characters from MongoDB: {e}")
        return None

def send_character(chat_id):
    character = fetch_random_character()
    if character:
        rarity_symbol = RARITY_LEVELS[character['rarity']]
        caption = (
            f"✿︎ <b>Guess the Anime Character!</b>\n\n"
            f"💬 Name: ???\n"
            f"✴️ Rarity: {rarity_symbol} {character['rarity']}\n"
        )
        bot.send_photo(chat_id, character['image_url'], caption=caption, parse_mode='HTML')
    else:
        bot.send_message(chat_id, "🚫 No characters available. Please add character messages to the channel.")

### Command Handlers ###
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    get_user_data(user_id)

    welcome_message = """
✿︎ <b>Wᴇʟᴄᴏᴍᴇ ᴛᴏ Pʜɪʟᴏ Gᴀᴍᴇ</b> ✿︎

ꜱᴛᴀʀᴛ ᴄᴏʟʟᴇᴄᴛɪɴɢ ᴀɴᴅ ɢᴜᴇꜱꜱɪɴɢ ᴀɴɪᴍᴇ ᴄʜᴀʀᴀᴄᴛᴇʀꜱ!

ᴜꜱᴇ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅꜱ ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴀʟʟ ᴛʜᴇ ꜰᴇᴀᴛᴜʀᴇꜱ!
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="Developer", url="https://t.me/TechPiro")
    markup.add(developer_button)
    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
<b>✿︎ Pʜɪʟᴏ Gᴀᴍᴇ Cᴏᴍᴍᴀɴᴅꜱ ✿︎</b>

<b>General Commands:</b>
/start - Start the bot and get a welcome message
/bonus - Claim your daily bonus
/profile - View your profile and stats
/topcoins - Show the top 10 users by coins

<b>Owner and Sudo Commands:</b>
/stats - View bot statistics (Owner only)
/add - Add a sudo user by ID (Owner only)
/upload - Upload a new character to the database and post it to the channel (Sudo only)
"""
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['topcoins'])
def topcoins_command(message):
    top_users = users_collection.find().sort('coins', -1).limit(10)
    leaderboard = "🏆 <b>Top 10 Users by Coins:</b>\n\n"
    for i, user in enumerate(top_users, start=1):
        profile_link = f"<a href='tg://user?id={user['user_id']}'>{user['profile'] if user['profile'] else 'User'}</a>"
        leaderboard += f"{i}. {profile_link} - {user['coins']} coins\n"

    bot.send_message(message.chat.id, leaderboard, parse_mode='HTML')

@bot.message_handler(commands=['upload'])
def upload_command(message):
    if message.from_user.id not in SUDO_USERS:
        bot.reply_to(message, "🚫 You are not authorized to use this command.")
        return

    try:
        # Extract image URL and character name from the message text
        args = message.text.split(maxsplit=2)
        image_url, character_name = args[1], args[2]
        rarity = assign_rarity()  # Automatically assign rarity

        # Save the character to the MongoDB database
        character_id = characters_collection.count_documents({}) + 1
        new_character = {
            'id': character_id,
            'image_url': image_url,
            'character_name': character_name,
            'rarity': rarity
        }
        characters_collection.insert_one(new_character)
        
        # Post the character to the specified channel
        caption = f"✿︎ <b>{character_name}</b>\n" \
                  f"✴️ Rarity: {RARITY_LEVELS[rarity]} {rarity}"
        bot.send_photo(CHARACTER_CHANNEL_ID, image_url, caption=caption, parse_mode='HTML')
        
        bot.reply_to(message, f"✅ Character '{character_name}' added successfully with {RARITY_LEVELS[rarity]} rarity and posted to the channel.")
    except (IndexError, ValueError):
        bot.reply_to(message, "🚫 Incorrect format. Use: /upload <image_url> <character_name>")
    except Exception as e:
        bot.reply_to(message, f"🚫 Failed to upload character: {e}")

# Handle all messages to manage game logic
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global global_message_count

    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(message.chat.id)
        global_message_count = 0

# Start polling
if __name__ == "__main__":
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
