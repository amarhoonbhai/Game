import telebot
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7740301929:AAGvwp3gtrOER1rbUrN-l4jMuMan-GrI0PQ"
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID =-1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for game data
user_last_claim = {}  # Track the last time each user claimed daily reward
user_daily_streaks = defaultdict(int)  # Track daily login streaks
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_streaks = defaultdict(int)  # Track correct guess streaks
user_inventory = defaultdict(list)  # Users' collected characters
characters = []  # List of all uploaded characters
current_character = None
auctions = {}  # Track ongoing character auctions
auction_id_counter = 1  # Track auction IDs
message_counter = defaultdict(int)  # Track the number of messages per chat

DAILY_REWARD_COINS = 10000  # Coins given as a daily reward
COINS_PER_GUESS = 50  # Coins awarded for correct guesses
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]  # Probabilities for selecting rarity (in percentage)

### Helper Functions ###
def add_coins(user_id, coins):
    user_coins[user_id] += coins
    print(f"User {user_id} awarded {coins} coins. Total: {user_coins[user_id]}")

def is_admin_or_owner(message):
    """ Check if the user is the bot owner or an admin. """
    if message.from_user.id == BOT_OWNER_ID:
        return True
    try:
        chat_admins = bot.get_chat_administrators(message.chat.id)
        return message.from_user.id in [admin.user.id for admin in chat_admins]
    except Exception:
        return False

def assign_rarity():
    """ Automatically assign rarity based on weighted probability. """
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    """Fetch a new character from the character database."""
    global current_character
    if characters:
        current_character = random.choice(characters)
        print(f"New character fetched: {current_character['character_name']}")
        return current_character
    return None

def send_character(chat_id):
    """Send the current character to the group chat for guessing."""
    character = fetch_new_character()
    if character:
        rarity = RARITY_LEVELS[character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {character['rarity']}\n"
            f"🌟 Can you guess this amazing character?"
        )
        bot.send_photo(chat_id, character['image_url'], caption=caption)
    else:
        bot.send_message(chat_id, "❌ No characters available to guess at the moment.")

### Command Handlers ###

# /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)

    welcome_message = """
━━━━━━━━━━━━━━━━━━━━━━
🎉 Welcome to Philo Grabber!

🔮 Philo Grabber is the ultimate Anime Character Guessing Game! Collect, trade, and guess characters to climb the leaderboards.

✨ Features:
- Daily rewards & streaks
- Character collection & trading
- PvP challenges, auctions, and much more!

Type /help to see the full list of commands!
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, welcome_message)

# /help command - Displays available commands without Markdown
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 Available Commands:

- /claim - Claim your daily reward of 10,000 coins
- /profile - View your profile with stats and achievements
- /inventory - View your collected characters
- /guess <name> - Guess the current character's name
- /leaderboard - Show the leaderboard with users and their coins
- /auction <character_id> <starting_bid> - Start an auction for a character
- /bid <auction_id> <bid_amount> - Place a bid on an ongoing auction
- /endauction <auction_id> - End an auction and transfer the character
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /settitle <title> - Set a custom title for your profile
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message)

# Message handler for all text, stickers, and media messages
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document'])
def count_messages(message):
    chat_id = message.chat.id

    # Increment message counter for the chat
    message_counter[chat_id] += 1

    # If the counter reaches 5, send a new character and reset the counter
    if message_counter[chat_id] >= 5:
        send_character(chat_id)
        message_counter[chat_id] = 0  # Reset counter

# /upload command - Allows the owner and admins to upload new characters
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character_id = len(characters) + 1
    character = {
        'id': character_id,
        'image_url': image_url.strip(),
        'character_name': character_name.strip(),
        'rarity': rarity
    }
    characters.append(character)

    caption = (f"📥 New Character Uploaded:\n\n"
               f"💬 Name: {character_name}\n"
               f"⚔️ Rarity: {RARITY_LEVELS[rarity]} {rarity}\n"
               f"🔗 Image URL: {image_url}\n"
               f"🆔 ID: {character_id}")
    
    # Send the character to the channel
    try:
        bot.send_photo(CHANNEL_ID, image_url, caption=caption)
        bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully!")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to send the character to the channel. Error: {e}")

# /profile command - Show user profile with stats, streaks, and achievements
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    total_coins = user_coins.get(user_id, 0)
    correct_guesses = user_correct_guesses.get(user_id, 0)
    streak = user_streaks.get(user_id, 0)
    inventory = user_inventory.get(user_id, [])

    profile_message = (
        f"👤 Profile\n"
        f"💰 Coins: {total_coins}\n"
        f"✅ Correct Guesses: {correct_guesses}\n"
        f"🔥 Current Streak: {streak}\n"
        f"🎒 Inventory: {len(inventory)} characters collected\n"
    )
    bot.reply_to(message, profile_message)

# /leaderboard command - Shows the top users based on their coin balance
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    if not user_coins:
        bot.reply_to(message, "No leaderboard data available yet.")
        return

    # Sort the users by the number of coins in descending order
    sorted_users = sorted(user_coins.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = "🏆 Leaderboard:\n\n"
    for rank, (user_id, coins) in enumerate(sorted_users, start=1):
        profile_name = user_profiles.get(user_id, "Unknown")
        leaderboard_message += f"{rank}. {profile_name}: {coins} coins\n"

    bot.reply_to(message, leaderboard_message)

# Start polling the bot
print("Bot is polling...")
bot.infinity_polling()
