import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAF3O80rS6UofVBucJcDP1RWb_VnGqjQY_Y"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
client = MongoClient(MONGO_URI)
db = client['philo_grabber']  # Database name
users_collection = db['users']  # Collection for user data
characters_collection = db['characters']  # Collection for character data

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
BOOSTER_PRICE = 1000  # Price for opening a booster pack
BOOSTER_REWARD = 3  # Number of characters in a booster pack
DAILY_CHALLENGE = "Guess a Legendary character today!"  # Example challenge
current_character = None
global_message_count = 0  # Global counter for messages in all chats


# Helper Functions
def get_user_data(user_id):
    """Fetch user data from MongoDB, or create a new entry if it doesn't exist."""
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
    """Update user data in MongoDB."""
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_character_data():
    """Fetch all character data from the characters collection."""
    return list(characters_collection.find())

def add_character(image_url, character_name, rarity):
    """Add a new character to the MongoDB characters collection."""
    character_id = characters_collection.count_documents({}) + 1
    character = {
        'id': character_id,
        'image_url': image_url,
        'character_name': character_name,
        'rarity': rarity
    }
    characters_collection.insert_one(character)
    return character

def assign_rarity():
    """Randomly assign a rarity to a character based on pre-defined weights."""
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    """Fetch a random character from the MongoDB collection."""
    characters = get_character_data()
    if characters:
        return random.choice(characters)
    return None

def send_character(chat_id):
    """Send a character image and details to the chat."""
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

def is_owner_or_sudo(user_id):
    """Check if the user is the bot owner or a sudo user."""
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS


# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.username or message.from_user.first_name
        update_user_data(user_id, {'profile': profile_name})
    
    # Custom welcome message
    welcome_message = """
👋 **Welcome to Philo Game!** 🎮
👑 **Owner**: @TechPiro

🌟 **Game Objective**:
- Guess anime characters, earn coins, and collect rare characters!

🏆 **Leaderboard**:
- Compete with other players and climb to the top!

📜 **Commands**:
/help - Show all available commands
/profile - View your stats and achievements
/inventory - View your collected characters
/leaderboard - See the top 10 players
/bonus - Claim your daily reward
Enjoy the game, and may the best guesser win! 🏅
"""
    bot.reply_to(message, welcome_message, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available Commands:
/bonus - Claim your daily reward (50,000 coins every 24 hours)
/profile - View your profile
/inventory - View your collected characters (grouped by rarity)
/leaderboard - Show the top 10 leaderboard
/upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only)
/delete <character_id> - Delete a character (Owner only)
/booster - Buy a character booster pack (1000 coins)
/trade <user_id> <your_character_id> <their_character_id> - Trade characters with other users
/collectionrewards - View available rewards for character collections
/challenge - See today's challenge
/stats - Show bot statistics (Owner only)
"""
    bot.reply_to(message, help_message)

@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    now = datetime.now()

    if user['last_bonus'] and now - datetime.fromisoformat(user['last_bonus']) < BONUS_INTERVAL:
        next_claim = datetime.fromisoformat(user['last_bonus']) + BONUS_INTERVAL
        remaining_time = next_claim - now
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"You can claim your next bonus in {hours_left} hours and {minutes_left} minutes.")
    else:
        new_coins = user['coins'] + BONUS_COINS
        update_user_data(user_id, {'coins': new_coins, 'last_bonus': now.isoformat()})
        bot.reply_to(message, f"🎉 You have received {BONUS_COINS} coins!")

@bot.message_handler(commands=['booster'])
def buy_booster(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user['coins'] < BOOSTER_PRICE:
        bot.reply_to(message, "❌ You don't have enough coins to buy a booster pack.")
        return

    new_coins = user['coins'] - BOOSTER_PRICE
    characters = []

    for _ in range(BOOSTER_REWARD):
        rarity = assign_rarity()
        new_character = fetch_new_character()
        if new_character:
            characters.append(new_character)
            user['inventory'].append(new_character)
    
    update_user_data(user_id, {'coins': new_coins, 'inventory': user['inventory']})
    booster_message = f"🎁 You've opened a booster pack and received {len(characters)} new characters!"
    bot.reply_to(message, booster_message)

@bot.message_handler(commands=['collectionrewards'])
def show_collection_rewards(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    collection = user['inventory']
    
    if len(collection) >= 50:  # Example threshold for rewards
        reward_message = "🎉 Congratulations! You've unlocked a special reward for collecting 50 characters!"
    else:
        reward_message = "Keep collecting characters to unlock special rewards!"
    
    bot.reply_to(message, reward_message)

@bot.message_handler(commands=['challenge'])
def show_daily_challenge(message):
    bot.reply_to(message, f"🔥 **Today's Challenge**: {DAILY_CHALLENGE}")

@bot.message_handler(commands=['trade'])
def trade_characters(message):
    try:
        _, other_user_id, your_character_id, their_character_id = message.text.split(maxsplit=3)
        other_user_id = int(other_user_id)
        your_character_id = int(your_character_id)
        their_character_id = int(their_character_id)
        
        user_id = message.from_user.id
        your_data = get_user_data(user_id)
        other_data = get_user_data(other_user_id)
        
        your_character = next((char for char in your_data['inventory'] if char['id'] == your_character_id), None)
        their_character = next((char for char in other_data['inventory'] if char['id'] == their_character_id), None)

        if your_character and their_character:
            # Swap characters between users
            your_data['inventory'].remove(your_character)
            their_data['inventory'].remove(their_character)

            your_data['inventory'].append(their_character)
            their_data['inventory'].append(your_character)

            update_user_data(user_id, {'inventory': your_data['inventory']})
            update_user_data(other_user_id, {'inventory': other_data['inventory']})

            bot.reply_to(message, "✅ Trade successful!")
        else:
            bot.reply_to(message, "❌ Trade failed. Invalid character IDs.")
    except ValueError:
        bot.reply_to(message, "Format: /trade <user_id> <your_character_id> <their_character_id>")

# Load all user data and characters on startup, then start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
