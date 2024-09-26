import telebot
import random
import threading
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7740301929:AAF3SMbXtx3W5Q35aBymIYTvPTLZUal-npY"  # Replace with your Telegram bot API token
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# Logging setup
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(message)s')
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
user_quests = defaultdict(dict)  # Track active quests
active_group_quizzes = defaultdict(lambda: {"active": False, "participants": {}, "character": None})  # Track group quizzes
difficulty_level = defaultdict(lambda: 'normal')  # Track user difficulty level
global_challenge = defaultdict(lambda: {'progress': 0, 'goal': 1000})  # Global guessing challenge

# Counter for unique character IDs
character_id_counter = 1

# Constants
INITIAL_COINS = 10000  # Coins awarded when a user starts the bot for the first time
COINS_PER_GUESS = 10
COINS_PER_HINT = 5
COINS_PER_BONUS = 100  # Bonus coins for daily reward
COINS_PER_STREAK = 20  # Extra coins for streak reward
COINS_PER_REDEEM = 50  # Coins per redeem
HINT_LETTER_COST = 5  # Cost per hint letter
COINS_PER_QUEST = 50  # Coins for completing a quest
MULTIPLAYER_REWARD = 100  # Coins for winning a multiplayer quiz
COINS_FOR_FAVORITING_CHARACTER = 10  # Bonus for favoriting a character

# Rarity levels for characters
RARITY_LEVELS = {
    'Common': 'Common',
    'Rare': 'Rare',
    'Epic': 'Epic',
    'Legendary': 'Legendary'
}

# Current character in play for guessing
current_character = None

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
    return random.choice(list(RARITY_LEVELS.keys()))

# Function to generate a random 4-digit redeem code
def generate_redeem_code():
    return ''.join(random.choices('0123456789', k=4))

# Function to send a character for guessing
def send_character(chat_id):
    global current_character
    if characters:
        current_character = random.choice(characters)
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 **Guess the Anime Character!**\n\n"
            f"💬 **Name**: ???\n"
            f"⚔️ **Rarity**: {rarity}\n"
            f"🌟 Can you guess this amazing character?"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption, parse_mode='Markdown')
        logging.info(f"Character sent for guessing: {current_character['character_name']}")

# Function to award streak rewards
def award_streak_bonus(user_id, streak):
    bonus = COINS_PER_STREAK * streak
    add_coins(user_id, bonus)
    bot.send_message(user_id, f"🔥 **Streak Bonus!** You earned **{bonus} coins** for a streak of {streak} correct guesses!")

# Function to track and award achievements
def check_achievements(user_id):
    total_guesses = user_correct_guesses[user_id]
    achievements = []
    
    if total_guesses >= 50 and "50 Guesses" not in user_achievements[user_id]:
        user_achievements[user_id].append("50 Guesses")
        achievements.append("🏅 50 Guesses Achievement!")
    
    if total_guesses >= 100 and "100 Guesses" not in user_achievements[user_id]:
        user_achievements[user_id].append("100 Guesses")
        achievements.append("🏅 100 Guesses Achievement!")
    
    if achievements:
        bot.send_message(user_id, "🎉 **New Achievements Unlocked**:\n" + "\n".join(achievements))

# Function to update global challenge
def update_global_challenge():
    global_challenge['progress'] += 1
    if global_challenge['progress'] >= global_challenge['goal']:
        bot.send_message(BOT_OWNER_ID, "🎉 Global challenge complete! All users will receive rewards.")
        for user_id in user_profiles.keys():
            add_coins(user_id, 100)  # Reward for completing the global challenge
        global_challenge['progress'] = 0  # Reset the challenge

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
    bot.send_message(CHANNEL_ID, f"📥 **New Character Uploaded**:\n\n🆔 **ID**: {character_id}\n💬 **Name**: {character_name}\n⚔️ **Rarity**: {RARITY_LEVELS[rarity]}\n🔗 **Image URL**: {image_url}")
    
    bot.reply_to(message, f"✅ Character '{character_name}' with ID **{character_id}** and rarity '{RARITY_LEVELS[rarity]}' has been uploaded successfully!")
    logging.info(f"Character {character_name} uploaded with ID {character_id}")

# /guess command - Allows users to guess the character name and sends a new character after a correct guess
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global current_character

    user_id = message.from_user.id
    group_id = message.chat.id
    user_message_count[user_id] += 1

    # If user guesses the character correctly, reward them with coins
    if current_character and message.text.strip().lower() == current_character['character_name'].lower():
        username = message.from_user.username or message.from_user.first_name
        user_profiles[user_id] = username
        user_correct_guesses[user_id] += 1
        add_coins(user_id, COINS_PER_GUESS)

        # Track streak and reward
        user_streaks[user_id] += 1
        if user_streaks[user_id] % 3 == 0:
            award_streak_bonus(user_id, user_streaks[user_id])

        check_achievements(user_id)
        update_global_challenge()

        bot.reply_to(message, f"🎉 **Congratulations {username}**! You guessed correctly and earned **{COINS_PER_GUESS}** coins!", parse_mode='Markdown')
        send_character(group_id)  # Send a new character immediately after a correct guess
    else:
        user_streaks[user_id] = 0  # Reset streak on incorrect guess

# /hint command - Reveal a hint (first few letters) for the current character
@bot.message_handler(commands=['hint'])
def give_hint(message):
    global current_character
    user_id = message.from_user.id

    if not current_character:
        bot.reply_to(message, "❌ There's no character to give a hint for.")
        return

    if user_coins[user_id] < COINS_PER_HINT:
        bot.reply_to(message, "❌ You don't have enough coins for a hint.")
        return

    # Deduct coins and give a hint (reveal the first few letters)
    add_coins(user_id, -COINS_PER_HINT)
    hint_length = min(3, len(current_character['character_name']))  # Reveal 3 letters
    hint = current_character['character_name'][:hint_length]
    bot.reply_to(message, f"💡 **Hint**: The first {hint_length} letters are: **{hint}**.")

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

# /title command - Set a custom title for the user's profile
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

# /quest command - Shows the user's current quests
@bot.message_handler(commands=['quest'])
def show_quests(message):
    user_id = message.from_user.id
    user_quests[user_id] = {"guess_5_characters": False, "log_in_daily": False}

    quests = user_quests[user_id]
    quests_status = (
        f"🎯 **Daily Quests**:\n"
        f"1. Guess 5 characters: {'✅ Completed' if quests['guess_5_characters'] else '❌ In Progress'}\n"
        f"2. Log in daily: {'✅ Completed' if quests['log_in_daily'] else '❌ In Progress'}\n"
    )
    bot.reply_to(message, quests_status, parse_mode='Markdown')

# /bonus command - Claim daily reward once every 24 hours
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    user_profiles[user_id] = message.from_user.username or message.from_user.first_name

    if can_claim_bonus(user_id):
        user_last_bonus[user_id] = datetime.now()  # Record the claim time
        add_coins(user_id, COINS_PER_BONUS)
        bot.reply_to(message, f"🎁 **{username}**, you have claimed your daily bonus and received **{COINS_PER_BONUS}** coins!", parse_mode='Markdown')
    else:
        remaining_time = timedelta(days=1) - (datetime.now() - user_last_bonus[user_id])
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"⏳ **You can claim your next bonus in {hours_left} hours and {minutes_left} minutes**.", parse_mode='Markdown')

### --- 3. Redeem Code Generation --- ###

def auto_generate_redeem_code():
    global current_redeem_code, redeem_code_expiry, redeem_code_claims
    while True:
        current_redeem_code = generate_redeem_code()
        redeem_code_expiry = datetime.now() + timedelta(minutes=30)
        redeem_code_claims.clear()  # Reset the claims for the new code
        redeem_message = f"🔑 **New Redeem Code**: **{current_redeem_code}**\nThis code is valid for 30 minutes. Use /redeem <code> to claim coins!"
        for chat_id in user_chat_ids:
            bot.send_message(chat_id, redeem_message, parse_mode='Markdown')
        time.sleep(1800)

### --- 4. Start Polling the Bot --- ###

# Start the redeem code generation in a separate thread
threading.Thread(target=auto_generate_redeem_code, daemon=True).start()

# Start polling the bot
bot.infinity_polling()
