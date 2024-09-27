import telebot
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7579121046:AAHIqrG0MscgQLXgHs4k1-RnXvdhq_eTCoo"
BOT_OWNER_ID = 7140556192  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and guessing game
user_last_claim = {}  # Track the last time each user claimed daily reward
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_streaks = defaultdict(int)  # Track correct guess streaks
user_achievements = defaultdict(list)  # Track user achievements
user_titles = defaultdict(str)  # Track custom titles
characters = []  # List of all uploaded characters
current_character = None

DAILY_REWARD_COINS = 10000  # Coins given as a daily reward
COINS_PER_GUESS = 50  # Coins awarded for correct guesses
HINT_COST = 100  # Charge 100 coins for each hint
STREAK_BONUS_COINS = 500  # Coins awarded for reaching a streak milestone

# Rarity levels with weighted probability
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

### Command Handlers ###

# /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)

    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Welcome to the Anime Character Guessing Game!**
🎮 **Commands:**
- /claim - Claim your daily reward of 10,000 coins
- /profile - View your profile with stats and achievements
- /guess <name> - Guess the current character's name
- /leaderboard - Show the leaderboard with users and their coins
- /topstreaks - Show users with the highest streaks
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by its ID
- /settitle <title> - Set a custom title for your profile
- /help - Show this help message
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# /upload command - Allows the owner and admins to upload new characters
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    # Expecting the format: /upload <image_url> <character_name>
    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name>")
        return

    # Automatically assign rarity
    rarity = assign_rarity()

    # Save the character with an ID
    character_id = len(characters) + 1
    character = {
        'id': character_id,
        'image_url': image_url.strip(),
        'character_name': character_name.strip(),
        'rarity': rarity
    }
    characters.append(character)

    # Log the character to the Telegram channel
    caption = (f"📥 **New Character Uploaded**:\n\n"
               f"💬 **Name**: {character_name}\n"
               f"⚔️ **Rarity**: {RARITY_LEVELS[rarity]} {rarity}\n"
               f"🔗 **Image URL**: {image_url}\n"
               f"🆔 **ID**: {character_id}")
    bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='Markdown')

    bot.reply_to(message, f"✅ Character '{character_name}' with rarity '{RARITY_LEVELS[rarity]} {rarity}' has been uploaded successfully!")

# /delete command - Allows the owner and admins to delete a character by ID
@bot.message_handler(commands=['delete'])
def delete_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    # Expecting the format: /delete <character_id>
    try:
        _, character_id_str = message.text.split(maxsplit=1)
        character_id = int(character_id_str)
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Incorrect format. Use: /delete <character_id>")
        return

    # Find and delete the character
    character_to_delete = next((char for char in characters if char['id'] == character_id), None)
    if character_to_delete:
        characters.remove(character_to_delete)
        bot.reply_to(message, f"🗑️ Character '{character_to_delete['character_name']}' (ID: {character_id}) has been deleted.")
        bot.send_message(CHANNEL_ID, f"🗑️ **Character Deleted**: {character_to_delete['character_name']} (ID: {character_id})", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"❌ Character with ID {character_id} not found.")

# /profile command - Show user profile with stats, streaks, and achievements
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    total_coins = user_coins.get(user_id, 0)
    correct_guesses = user_correct_guesses.get(user_id, 0)
    streak = user_streaks.get(user_id, 0)
    achievements = user_achievements.get(user_id, [])
    title = user_titles.get(user_id, "Newbie")

    profile_message = (
        f"👤 **Profile**\n"
        f"💰 **Coins**: {total_coins}\n"
        f"✅ **Correct Guesses**: {correct_guesses}\n"
        f"🔥 **Current Streak**: {streak}\n"
        f"🏅 **Achievements**: {', '.join(achievements) if achievements else 'None'}\n"
        f"👑 **Title**: {title}"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# /guess command - Guess the name of the current character
@bot.message_handler(commands=['guess'])
def guess_character(message):
    global current_character
    user_id = message.from_user.id
    user_guess = message.text.split(maxsplit=1)[1].strip().lower()

    if not current_character:
        bot.reply_to(message, "❌ There's no character to guess!")
        return

    if user_guess == current_character['character_name'].lower():
        add_coins(user_id, COINS_PER_GUESS)
        user_correct_guesses[user_id] += 1

        bot.reply_to(message, f"🎉 **Correct!** You earned {COINS_PER_GUESS} coins!")
        
        # Fetch new character after correct guess
        fetch_new_character()
    else:
        bot.reply_to(message, "❌ Wrong guess! Try again.")

# /settitle command - Set a custom title for the user's profile
@bot.message_handler(commands=['settitle'])
def set_title(message):
    user_id = message.from_user.id
    try:
        _, new_title = message.text.split(maxsplit=1)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /settitle <title>")
        return

    user_titles[user_id] = new_title.strip()
    bot.reply_to(message, f"👑 Your title has been set to **{new_title}**!")

# /help command - Lists all available commands if requested separately
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
━━━━━━━━━━━━━━━━━━━━━━
🤖 **Available Commands:**
- /claim - Claim your daily reward of 10,000 coins
- /profile - View your profile with stats and achievements
- /guess <name> - Guess the current character's name
- /leaderboard - Show the leaderboard with users and their coins
- /topstreaks - Show users with the highest streaks
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by its ID
- /settitle <title> - Set a custom title for your profile
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# Start polling the bot
print("Bot is polling...")
bot.infinity_polling()
