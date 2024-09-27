import telebot
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7740301929:AAH-k7BpCTswVtUKUedOQwRtJHz1TFBAoNg"
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1001234567890  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and game data
user_last_claim = {}  # Track the last time each user claimed daily reward
user_daily_streaks = defaultdict(int)  # Track daily login streaks
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_streaks = defaultdict(int)  # Track correct guess streaks
user_achievements = defaultdict(list)  # Track user achievements
user_titles = defaultdict(str)  # Track custom titles
user_inventory = defaultdict(list)  # Users' collected characters
characters = []  # List of all uploaded characters
trading_offers = {}  # Active trade offers
current_character = None

DAILY_REWARD_COINS = 10000  # Coins given as a daily reward
COINS_PER_GUESS = 50  # Coins awarded for correct guesses
HINT_COST = 100  # Charge 100 coins for each hint
STREAK_BONUS_COINS = 500  # Coins awarded for reaching a streak milestone
DAILY_STREAK_BONUS = 200  # Bonus coins for consecutive daily logins

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

def deduct_coins(user_id, coins):
    if user_coins[user_id] >= coins:
        user_coins[user_id] -= coins
        return True
    return False

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

def award_daily_streak_bonus(user_id):
    streak = user_daily_streaks[user_id]
    bonus = DAILY_STREAK_BONUS * streak
    add_coins(user_id, bonus)
    bot.send_message(user_id, f"🎉 **Daily Streak Bonus!** You've logged in for {streak} consecutive days and earned {bonus} bonus coins!")

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
**🎉 Welcome to Philo Grabber!**
Owner: [@TechPiro](https://t.me/TechPiro)

🔮 **Philo Grabber** is the ultimate Anime Character Guessing Game! Collect, trade, and guess characters to climb the leaderboards.

✨ **Features**:
- Daily rewards & streaks
- Character collection & trading
- PvP challenges, auctions, and much more!

Type /help to see the full list of commands!
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, welcome_message, parse_mode='Markdown')

# /claim command
@bot.message_handler(commands=['claim'])
def claim_daily_reward(message):
    user_id = message.from_user.id
    now = datetime.now()

    # Check if the user has already claimed within the past 24 hours
    if user_id in user_last_claim:
        last_claim_time = user_last_claim[user_id]
        time_since_last_claim = now - last_claim_time
        if time_since_last_claim < timedelta(days=1):
            remaining_time = timedelta(days=1) - time_since_last_claim
            hours_left = remaining_time.seconds // 3600
            minutes_left = (remaining_time.seconds % 3600) // 60
            bot.reply_to(message, f"⏳ You can claim your next reward in **{hours_left} hours and {minutes_left} minutes**.")
            return

    # Award daily reward coins
    add_coins(user_id, DAILY_REWARD_COINS)
    user_last_claim[user_id] = now

    # Track daily streaks
    if user_daily_streaks[user_id] > 0:
        user_daily_streaks[user_id] += 1
        award_daily_streak_bonus(user_id)
    else:
        user_daily_streaks[user_id] = 1
    bot.reply_to(message, f"🎉 You have successfully claimed **{DAILY_REWARD_COINS} coins** as your daily reward!")

# /profile command - Show user profile with stats, streaks, and achievements
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    total_coins = user_coins.get(user_id, 0)
    correct_guesses = user_correct_guesses.get(user_id, 0)
    streak = user_streaks.get(user_id, 0)
    achievements = user_achievements.get(user_id, [])
    title = user_titles.get(user_id, "Newbie")
    inventory = user_inventory.get(user_id, [])

    profile_message = (
        f"👤 **Profile**\n"
        f"💰 **Coins**: {total_coins}\n"
        f"✅ **Correct Guesses**: {correct_guesses}\n"
        f"🔥 **Current Streak**: {streak}\n"
        f"🏅 **Achievements**: {', '.join(achievements) if achievements else 'None'}\n"
        f"🎒 **Inventory**: {len(inventory)} characters collected\n"
        f"👑 **Title**: {title}"
    )
    bot.reply_to(message, profile_message, parse_mode='Markdown')

# /inventory command - Show user inventory (characters collected)
@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    inventory = user_inventory.get(user_id, [])
    if not inventory:
        bot.reply_to(message, "🎒 **Your Inventory is empty.**")
        return

    inventory_message = "🎒 **Your Collected Characters**:\n"
    for character in inventory:
        inventory_message += f"- {character['character_name']} ({RARITY_LEVELS[character['rarity']]})\n"

    bot.reply_to(message, inventory_message, parse_mode='Markdown')

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
        user_inventory[user_id].append(current_character)

        bot.reply_to(message, f"🎉 **Correct!** You earned {COINS_PER_GUESS} coins and collected **{current_character['character_name']}**!")
        
        # Fetch new character after correct guess
        fetch_new_character()
    else:
        bot.reply_to(message, "❌ Wrong guess! Try again.")

# /trade command - Offer a character trade to another user
@bot.message_handler(commands=['trade'])
def trade_character(message):
    try:
        _, username, character_id = message.text.split(maxsplit=2)
        character_id = int(character_id)
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Incorrect format. Use: /trade <username> <character_id>")
        return

    user_id = message.from_user.id
    target_user_id = None

    # Find the target user
    for uid, profile_name in user_profiles.items():
        if profile_name == username:
            target_user_id = uid
            break

    if target_user_id is None:
        bot.reply_to(message, f"❌ User '{username}' not found.")
        return

    # Find the character in user's inventory
    character_to_trade = next((char for char in user_inventory[user_id] if char['id'] == character_id), None)
    if character_to_trade is None:
        bot.reply_to(message, f"❌ You don't own a character with ID {character_id}.")
        return

    # Offer the trade
    trading_offers[target_user_id] = {
        'from_user': user_id,
        'character': character_to_trade
    }
    bot.reply_to(message, f"📤 Trade offer sent to {username} for character '{character_to_trade['character_name']}'.")

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
- /inventory - View your collected characters
- /guess <name> - Guess the current character's name
- /leaderboard - Show the leaderboard with users and their coins
- /topstreaks - Show users with the highest streaks
- /upload <image_url> <character_name> - (Admins only) Upload a new character
- /delete <character_id> - (Admins only) Delete a character by its ID
- /settitle <title> - Set a custom title for your profile
- /trade <username> <character_id> - Offer a character trade to another user
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, help_message, parse_mode='Markdown')

# Start polling the bot
print("Bot is polling...")
bot.infinity_polling()
