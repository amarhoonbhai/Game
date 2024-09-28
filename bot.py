import telebot
import random
from collections import defaultdict
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAH9h-xJhNXHnTLUJEOJhhj4osGFkNk3zZM"
BOT_OWNER_ID = 7140556192  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

bot = telebot.TeleBot(API_TOKEN)

# In-memory store for game data
user_coins = defaultdict(int)  # User coin balance
user_profiles = {}  # User profiles (username or first_name)
user_correct_guesses = defaultdict(int)  # Track correct guesses
user_inventory = defaultdict(list)  # Collected characters
user_last_bonus = {}  # Track last bonus claim time
characters = []  # List of uploaded characters (with ID)
current_character = None
message_counter = defaultdict(int)  # Track message count per chat

# Bonus and guessing settings
BONUS_COINS = 50000  # Bonus amount for daily claim
BONUS_INTERVAL = timedelta(days=1)  # Bonus claim interval (24 hours)
COINS_PER_GUESS = 50  # Coins for correct guesses
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]
character_id_counter = 1  # Counter for character IDs

# Helper Functions
def add_coins(user_id, coins):
    user_coins[user_id] += coins

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    if characters:
        return random.choice(characters)
    return None

def send_character(chat_id):
    character = fetch_new_character()
    if character:
        rarity = RARITY_LEVELS[character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {character['rarity']}\n"
        )
        bot.send_photo(chat_id, character['image_url'], caption=caption)
    else:
        bot.send_message(chat_id, "No characters available to guess.")

def find_character_by_id(char_id):
    for character in characters:
        if character['id'] == char_id:
            return character
    return None

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Type /help for commands.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available Commands:
/bonus - Claim your daily reward (50,000 coins every 24 hours)
/profile - View your profile
/inventory - View your collected characters
/guess <name> - Guess the character's name
/leaderboard - Show the leaderboard
/upload <image_url> <character_name> - Upload a new character (Owner only)
/delete <character_id> - Delete a character (Owner only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    now = datetime.now()

    # Check if the user can claim the bonus
    if user_id in user_last_bonus and now - user_last_bonus[user_id] < BONUS_INTERVAL:
        next_claim = user_last_bonus[user_id] + BONUS_INTERVAL
        remaining_time = next_claim - now
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"You can claim your next bonus in {hours_left} hours and {minutes_left} minutes.")
    else:
        add_coins(user_id, BONUS_COINS)
        user_last_bonus[user_id] = now
        bot.reply_to(message, f"🎉 You have received {BONUS_COINS} coins!")

@bot.message_handler(commands=['upload'])
def upload_character(message):
    global character_id_counter

    # Only the owner (BOT_OWNER_ID) can upload characters
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "You do not have permission to upload characters.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "Format: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character = {'id': character_id_counter, 'image_url': image_url, 'character_name': character_name, 'rarity': rarity}
    characters.append(character)
    bot.send_message(CHANNEL_ID, f"New character uploaded: {character_name} (ID: {character_id_counter}, {RARITY_LEVELS[rarity]} {rarity})")
    bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully with ID {character_id_counter}!")

    character_id_counter += 1

@bot.message_handler(commands=['delete'])
def delete_character(message):
    # Only the owner (BOT_OWNER_ID) can delete characters
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "You do not have permission to delete characters.")
        return

    try:
        _, char_id_str = message.text.split(maxsplit=1)
        char_id = int(char_id_str)
    except (ValueError, IndexError):
        bot.reply_to(message, "Format: /delete <character_id>")
        return

    character = find_character_by_id(char_id)
    if character:
        characters.remove(character)
        bot.reply_to(message, f"✅ Character with ID {char_id} ('{character['character_name']}') has been deleted.")
    else:
        bot.reply_to(message, f"❌ Character with ID {char_id} not found.")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    coins = user_coins[user_id]
    correct_guesses = user_correct_guesses[user_id]
    inventory_count = len(user_inventory[user_id])

    profile_message = (
        f"Profile\nCoins: {coins}\nCorrect Guesses: {correct_guesses}\nInventory: {inventory_count} characters"
    )
    bot.reply_to(message, profile_message)

@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    inventory = user_inventory[user_id]

    if not inventory:
        bot.reply_to(message, "Your inventory is empty. Start guessing characters to collect them!")
    else:
        inventory_message = "🎒 Your Character Collection:\n"
        for i, character in enumerate(inventory, 1):
            inventory_message += f"{i}. {character['character_name']} ({character['rarity']})\n"
        bot.reply_to(message, inventory_message)

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    sorted_users = sorted(user_coins.items(), key=lambda x: x[1], reverse=True)
    leaderboard_message = "🏆 Leaderboard:\n"
    for rank, (user_id, coins) in enumerate(sorted_users, start=1):
        profile_name = user_profiles.get(user_id, "Unknown")
        leaderboard_message += f"{rank}. {profile_name}: {coins} coins\n"
    bot.reply_to(message, leaderboard_message)

@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document'])
def count_messages(message):
    chat_id = message.chat.id
    message_counter[chat_id] += 1

    if message_counter[chat_id] >= 5:  # After 5 messages, send a new character
        send_character(chat_id)
        message_counter[chat_id] = 0

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
