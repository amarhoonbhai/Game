import telebot
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7825167784:AAFn6puDuKoZjJvxwfCmRyT8FATcrIwtFaE"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
try:
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
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

def get_character_data():
    return list(characters_collection.find())

def add_character(image_url, character_name, rarity):
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
    return random.choices(['Common', 'Rare', 'Epic', 'Legendary'], weights=[60, 25, 10, 5], k=1)[0]

def fetch_new_character():
    characters = get_character_data()
    if characters:
        return random.choice(characters)
    return None

def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = current_character['rarity']
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        bot.send_photo(chat_id, current_character['image_url'], caption=caption)

# Bonus reminder system
def send_bonus_reminder():
    now = datetime.now()
    users = users_collection.find()
    for user in users:
        if user['last_bonus']:
            last_bonus_time = datetime.fromisoformat(user['last_bonus'])
            if now - last_bonus_time >= BONUS_INTERVAL:
                try:
                    bot.send_message(user['user_id'], "⏰ Don't forget to claim your daily bonus using /bonus!")
                except:
                    continue  # In case the user blocks the bot or there is an error
    Timer(REMINDER_INTERVAL, send_bonus_reminder).start()

# Start the bonus reminder loop
send_bonus_reminder()

# Command Handlers

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user['profile']:
        profile_name = message.from_user.full_name
        username = message.from_user.username  # Capture username
        update_user_data(user_id, {'profile': profile_name, 'username': username})

    welcome_message = """
🎮 **Welcome to Philo Game!**
🛠️ Bot developed by [@TechPiro](https://t.me/TechPiro)

**Start playing now!** Here are some commands to help you get started:
- /bonus - Claim your daily reward of coins every 24 hours.
- /profile - View your profile including your stats.
- /inventory - Check out the characters you've collected, grouped by rarity.
- /leaderboard - See the top players with the most correct guesses.
- /topcoins - See the top players with the most coins.
- /gift - Gift coins to another user by tagging them.
- /upload <image_url> <character_name> - Upload a new character (Owner and Sudo users only).
- /delete <character_id> - Delete a character (Owner only).
- /stats - View bot statistics (Owner only).

**Join the fun!** Guess anime characters to earn coins and collect unique characters!
"""
    bot.send_message(message.chat.id, welcome_message, parse_mode="Markdown")

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})
    
    if user is None:
        bot.reply_to(message, "You don't have a profile yet. Please interact with the bot to create one.")
        return

    profile_message = (
        f"👤 **Profile**\n"
        f"👤 Name: {user.get('profile', 'Unknown User')}\n"
        f"💰 Coins: {user.get('coins', 0)}\n"
        f"✅ Correct Guesses: {user.get('correct_guesses', 0)}\n"
        f"🔥 Streak: {user.get('streak', 0)}\n"
        f"🎒 Inventory Size: {len(user.get('inventory', []))} characters\n"
    )
    
    bot.reply_to(message, profile_message, parse_mode='Markdown')

@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})

    if user is None or not user.get('inventory'):
        bot.reply_to(message, "Your inventory is empty. Start guessing characters to collect them!")
        return

    inventory_by_rarity = {
        'Common': [],
        'Rare': [],
        'Epic': [],
        'Legendary': []
    }

    # Group characters by rarity
    for character in user['inventory']:
        rarity = character.get('rarity', 'Unknown')
        inventory_by_rarity[rarity].append(character['character_name'])

    inventory_message = f"🎒 **{user.get('profile', 'Unknown User')}**'s Character Collection:\n\n"
    
    # Display characters by rarity
    for rarity, characters in inventory_by_rarity.items():
        if characters:
            inventory_message += f"🔹 **{rarity}** ({len(characters)} characters):\n"
            inventory_message += "\n".join([f"- {char}" for char in characters]) + "\n\n"
    
    bot.reply_to(message, inventory_message, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != BOT_OWNER_ID:
        bot.reply_to(message, "❌ You are not authorized to view this information.")
        return

    total_users = users_collection.count_documents({})
    total_coins_distributed = sum(user['coins'] for user in users_collection.find())
    total_correct_guesses = sum(user['correct_guesses'] for user in users_collection.find())

    stats_message = (
        f"📊 **Bot Stats**:\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💰 Total Coins Distributed: {total_coins_distributed}\n"
        f"✅ Total Correct Guesses: {total_correct_guesses}"
    )
    
    bot.reply_to(message, stats_message)

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

@bot.message_handler(commands=['gift'])
def gift_coins(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if not message.reply_to_message or not message.reply_to_message.from_user:
        bot.reply_to(message, "❌ Please reply to the user you want to gift coins to.")
        return

    try:
        recipient_id = message.reply_to_message.from_user.id
        amount = int(message.text.split()[1])  # Expecting: /gift <amount>
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Format: /gift <amount> (tag the user)")
        return

    if user['coins'] < amount:
        bot.reply_to(message, "❌ You don't have enough coins to gift!")
        return

    recipient = get_user_data(recipient_id)
    if recipient is None:
        bot.reply_to(message, "❌ Recipient not found!")
        return

    new_sender_coins = user['coins'] - amount
    new_recipient_coins = recipient['coins'] + amount
    update_user_data(user_id, {'coins': new_sender_coins})
    update_user_data(recipient_id, {'coins': new_recipient_coins})

    bot.reply_to(message, f"🎁 You gifted {amount} coins to {message.reply_to_message.from_user.first_name}!")
    try:
        bot.send_message(recipient_id, f"🎉 You received {amount} coins from {message.from_user.first_name}!")
    except:
        pass  # In case the recipient blocks the bot or there is an error

# Leaderboard command
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    users = users_collection.find().sort('correct_guesses', -1).limit(10)
    leaderboard_message = "🏆 **Top 10 Leaderboard (Correct Guesses)**:\n\n"
    
    for rank, user in enumerate(users, start=1):
        first_name = user.get('profile', 'Unknown User')
        username = user.get('username', None)
        inventory = user.get('inventory', [])
        most_collected_character = max({character['character_name']: inventory.count(character['character_name']) for character in inventory}, default="No characters collected")

        if username:
            user_link = f'<a href="https://t.me/{username}"><b>{first_name}</b></a>'
        else:
            user_link = f'<b>{first_name}</b>'

        leaderboard_message += f"{rank}. {user_link}: {user['correct_guesses']} correct guesses, Most Collected Character: {most_collected_character}\n"
    
    bot.send_message(message.chat.id, leaderboard_message, parse_mode="HTML")

# Top coins command
@bot.message_handler(commands=['topcoins'])
def show_topcoins(message):
    users = users_collection.find().sort('coins', -1).limit(10)
    topcoins_message = "💰 **Top 10 Users by Coins**:\n\n"
    
    for rank, user in enumerate(users, start=1):
        first_name = user.get('profile', 'Unknown User')
        username = user.get('username', None)
        inventory_count = len(user.get('inventory', []))

        if username:
            user_link = f'<a href="https://t.me/{username}"><b>{first_name}</b></a>'
        else:
            user_link = f'<b>{first_name}</b>'

        topcoins_message += f'{rank}. {user_link} ➾ <b>{user["coins"]}</b> coins, {inventory_count} characters collected\n'
    
    bot.send_message(message.chat.id, topcoins_message, parse_mode="HTML")

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0

    if current_character:
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
