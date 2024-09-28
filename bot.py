import telebot
import random
from collections import defaultdict

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAHqV39mmneAvu2nMnQlJpbSMYS6r1HCjpM"
CHANNEL_ID =  -1002438449944 # Replace with your Telegram channel ID where characters are logged
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for game data
user_coins = defaultdict(int)  # User coin balance
user_profiles = {}  # User profiles (username or first_name)
user_correct_guesses = defaultdict(int)  # Track correct guesses
user_inventory = defaultdict(list)  # Collected characters
characters = []  # List of uploaded characters
current_character = None
message_counter = defaultdict(int)  # Track message count per chat

# Coins and guessing settings
DAILY_REWARD_COINS = 10000
COINS_PER_GUESS = 50
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]

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
/claim - Claim daily reward (10,000 coins)
/profile - View your profile
/inventory - View your collected characters
/guess <name> - Guess the character's name
/leaderboard - Show the leaderboard
/upload <image_url> <character_name> - Upload a new character (Admins only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.id != bot.get_me().id:  # Ensure admin uploads
        bot.reply_to(message, "You do not have permission to upload characters.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "Format: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character = {'image_url': image_url, 'character_name': character_name, 'rarity': rarity}
    characters.append(character)
    bot.send_message(CHANNEL_ID, f"New character uploaded: {character_name} ({RARITY_LEVELS[rarity]} {rarity})")

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
