import telebot
import random
import threading
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7579121046:AAE0LRTZmJT5cT_5p94Gwu8t9aYRXzi5NSc"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# Logging setup
logging.basicConfig(filename='logs/bot.log', level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()

# In-memory store for redeem codes, characters, and guessing game
current_redeem_code = None
redeem_code_expiry = None
redeem_code_claims = {}

user_last_bonus = {}  # Track last bonus claim time of each user
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
characters = []  # Store uploaded characters
user_streaks = defaultdict(int)  # Track correct guess streaks
user_achievements = defaultdict(list)  # Track user achievements
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_favorite_characters = defaultdict(list)  # Track user's favorite characters
user_titles = defaultdict(str)  # Track custom titles

# Counter for unique character IDs
character_id_counter = 1

# Constants
INITIAL_COINS = 10000  # Coins awarded when a user starts the bot for the first time
COINS_PER_GUESS = 10
COINS_PER_HINT = 5
COINS_PER_BONUS = 100  # Bonus coins for daily reward
COINS_PER_REDEEM = 50  # Coins per redeem
COINS_FOR_FAVORITING_CHARACTER = 10  # Bonus for favoriting a character

### --- 1. Helper Functions --- ###

# Function to add coins to the user's balance
def add_coins(user_id, coins):
    user_coins[user_id] += coins
    logging.info(f"User {user_id} received {coins} coins. Total: {user_coins[user_id]}")

# Function to check if the user is the bot owner or a sudo admin
def is_admin_or_owner(message):
    if message.from_user.id == BOT_OWNER_ID:
        return True
    try:
        chat_admins = bot.get_chat_administrators(message.chat.id)
        return message.from_user.id in [admin.user.id for admin in chat_admins]
    except Exception as e:
        logger.error(f"Error checking admin rights: {e}")
        return False

# Function to auto-assign rarity
def assign_rarity():
    return random.choice(['Common', 'Rare', 'Epic', 'Legendary'])

# Function to generate a random 4-digit redeem code
def generate_redeem_code():
    return ''.join(random.choices('0123456789', k=4))

# Function to send a character for guessing
def send_character(chat_id):
    global current_character
    if characters:
        current_character = random.choice(characters)
        rarity = current_character['rarity']
        caption = (
            f"🎨 **Guess the Anime Character!**\n\n"
            f"💬 **Name**: ???\n"
            f"⚔️ **Rarity**: {rarity}\n"
            f"🌟 Can you guess this amazing character?"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption, parse_mode='Markdown')
        logging.info(f"Character sent for guessing: {current_character['character_name']}")

### --- 2. Command Handlers --- ###

# /upload command - Allows the owner and admins to upload new characters
@bot.message_handler(commands=['upload'])
def upload_character(message):
    global character_id_counter

    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name>")
        return

    # Assign a random rarity and generate a character ID
    rarity = assign_rarity()
    character_id = character_id_counter
    character_id_counter += 1

    # Save the character details
    character = {
        'id': character_id,
        'image_url': image_url.strip(),
        'character_name': character_name.strip(),
        'rarity': rarity
    }
    characters.append(character)

    # Log the character to the Telegram channel with ID
    bot.send_message(CHANNEL_ID, f"📥 **New Character Uploaded**:\n\n🆔 **ID**: {character_id}\n💬 **Name**: {character_name}\n⚔️ **Rarity**: {rarity}\n🔗 **Image URL**: {image_url}")
    
    bot.reply_to(message, f"✅ Character '{character_name}' with ID **{character_id}** and rarity '{rarity}' has been uploaded successfully!")
    logging.info(f"Character {character_name} uploaded with ID {character_id}")

# /delete command - Allows admins to delete a character by ID
@bot.message_handler(commands=['delete'])
def delete_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, character_id = message.text.split(maxsplit=1)
        character_id = int(character_id)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /delete <character_id>")
        return

    for character in characters:
        if character['id'] == character_id:
            characters.remove(character)
            bot.reply_to(message, f"✅ Character with ID **{character_id}** has been deleted.")
            logger.info(f"Character with ID {character_id} deleted")
            return

    bot.reply_to(message, f"❌ Character with ID **{character_id}** not found.")

# /leaderboard command - Shows the leaderboard with users and their coins
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    if not user_coins:
        bot.reply_to(message, "No leaderboard data available yet.")
        return

    sorted_users = sorted(user_coins.items(), key=lambda x: x[1], reverse=True)

    leaderboard_message = "🏆 **Leaderboard**:\n\n"
    for rank, (user_id, coins) in enumerate(sorted_users, start=1):
        profile_name = user_profiles.get(user_id, "Unknown")
        leaderboard_message += f"{rank}. {profile_name}: {coins} coins\n"

    bot.reply_to(message, leaderboard_message, parse_mode='Markdown')

# /redeem command - Allows users to redeem the code for coins
@bot.message_handler(commands=['redeem'])
def redeem_code(message):
    global current_redeem_code, redeem_code_expiry

    if current_redeem_code is None or datetime.now() > redeem_code_expiry:
        bot.reply_to(message, "⏳ There is no active redeem code or it has expired.")
        return

    user_id = message.from_user.id
    redeem_attempt = message.text.split()

    if len(redeem_attempt) < 2 or redeem_attempt[1] != current_redeem_code:
        bot.reply_to(message, "❌ Invalid redeem code.")
        return

    if user_id in redeem_code_claims:
        bot.reply_to(message, "⏳ You have already redeemed this code.")
        return

    # Award coins for redeeming
    add_coins(user_id, COINS_PER_REDEEM)
    redeem_code_claims[user_id] = True
    bot.reply_to(message, f"🎉 You have successfully redeemed the code and earned **{COINS_PER_REDEEM}** coins!")

# /profile command - Shows the user's profile with stats
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    total_coins = user_coins.get(user_id, 0)
    correct_guesses = user_correct_guesses.get(user_id, 0)
    streak = user_streaks.get(user_id, 0)
    achievements = user_achievements.get(user_id, [])
    favorite_characters = user_favorite_characters.get(user_id, [])
    title = user_titles.get(user_id, "Newbie")

    profile_message = (
        f"👤 **Profile**\n"
        f"💰 **Coins**: {total_coins}\n"
        f"✅ **Correct Guesses**: {correct_guesses}\n"
        f"🔥 **Current Streak**: {streak}\n"
        f"🏅 **Achievements**: {', '.join(achievements) if achievements else 'None'}\n"
        f"💖 **Favorite Characters**: {', '.join(favorite_characters) if favorite_characters else 'None'}\n"
        f"👑 **Title**: {title}"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# /favorite command - Mark a character as a user's favorite
@bot.message_handler(commands=['favorite'])
def favorite_character(message):
    global current_character
    user_id = message.from_user.id

    if not current_character:
        bot.reply_to(message, "❌ There's no character to favorite.")
        return

    if current_character['character_name'] in user_favorite_characters[user_id]:
        bot.reply_to(message, "⚠️ You've already marked this character as a favorite.")
        return

    user_favorite_characters[user_id].append(current_character['character_name'])
    add_coins(user_id, COINS_FOR_FAVORITING_CHARACTER)
    bot.reply_to(message, f"💖 You marked **{current_character['character_name']}** as a favorite and earned **{COINS_FOR_FAVORITING_CHARACTER}** coins!")

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

# Function to automatically fetch new character from the channel after a correct guess
def fetch_new_character():
    global current_character
    if characters:
        current_character = random.choice(characters)
        # Fetch from the stored list of characters
        bot.send_message(CHANNEL_ID, f"🔄 New character fetched from channel!")
        logging.info("Fetched new character from channel.")

### --- 3. Redeem Code Generation --- ###

# Function to automatically generate a new redeem code every 30 minutes and send it to the bot
def auto_generate_redeem_code():
    global current_redeem_code, redeem_code_expiry, redeem_code_claims
    while True:
        current_redeem_code = generate_redeem_code()
        redeem_code_expiry = datetime.now() + timedelta(minutes=30)
        redeem_code_claims.clear()  # Reset the claims for the new code
        redeem_message = f"🔑 **New Redeem Code**: **{current_redeem_code}**\nThis code is valid for 30 minutes. Use /redeem <code> to claim coins!"
        for chat_id in user_chat_ids:
            bot.send_message(chat_id, redeem_message, parse_mode='Markdown')
        time.sleep(1800)  # Wait for 30 minutes before generating the next code

### --- 4. Start Polling the Bot --- ###

# Start the redeem code generation in a separate thread
threading.Thread(target=auto_generate_redeem_code, daemon=True).start()

# Start polling the bot
bot.infinity_polling()
