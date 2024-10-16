import telebot
import random
from pymongo import MongoClient, errors
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Replace with your actual bot API token and Telegram channel ID
API_TOKEN = "7579121046:AAHXqY_W6nwzgxwAnVL4Fp0JCFmw0_kTZRI"
BOT_OWNER_ID = 7222795580  # Replace with the owner’s Telegram ID
CHANNEL_ID = -1002438449944  # Replace with your Telegram channel ID where characters are logged

# MongoDB Connection
try:
    MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
    client = MongoClient(MONGO_URI)
    db = client['philo_grabber']  # Database name
    users_collection = db['users']  # Collection for user data
    characters_collection = db['characters']  # Collection for character data
    groups_collection = db['groups']  # Collection for group stats (for /stats and /topgroups)
    print("🝮︎︎︎ Connected to MongoDB 🝮︎︎︎")
except errors.ServerSelectionTimeoutError as err:
    print(f"Error: Could not connect to MongoDB: {err}")
    exit()

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
TOP_LEADERBOARD_LIMIT = 10  # Limit for leaderboard to only show top 10 users
ITEMS_PER_PAGE = 20  # Number of characters per page in inventory

# Global variables to track the current character and message count
current_character = None
global_message_count = 0  # Global counter for messages in all chats

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
            'profile': None
        }
        users_collection.insert_one(new_user)
        return new_user
    return user

def update_user_data(user_id, update_data):
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})

def get_user_rank(user_id):
    user = get_user_data(user_id)
    user_coins = user['coins']

    # Count users with more coins than the current user
    higher_ranked_users = users_collection.count_documents({'coins': {'$gt': user_coins}})
    # Total users
    total_users = users_collection.count_documents({})

    # Rank is one more than the number of users with more coins (as rank 1 is the top player)
    rank = higher_ranked_users + 1

    # Find the user directly above the current user in rank (for "next rank" calculation)
    next_user = users_collection.find_one({'coins': {'$gt': user_coins}}, sort=[('coins', 1)])
    if next_user:
        coins_to_next_rank = next_user['coins'] - user_coins
    else:
        coins_to_next_rank = None  # User is already at the highest rank

    return rank, total_users, coins_to_next_rank

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

def delete_character(character_id):
    return characters_collection.delete_one({'id': character_id})

def assign_rarity():
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

def fetch_new_character():
    characters = list(characters_collection.find())
    if characters:
        return random.choice(characters)
    return None

# Track Group Activity
def track_group_activity(chat_id, chat_name):
    group = groups_collection.find_one({'group_id': chat_id})
    if group:
        groups_collection.update_one({'group_id': chat_id}, {'$inc': {'message_count': 1}})
    else:
        groups_collection.insert_one({
            'group_id': chat_id,
            'message_count': 1,
            'group_name': chat_name
        })

# Sending a character to chat
def send_character(chat_id):
    global current_character
    current_character = fetch_new_character()
    if current_character:
        rarity = RARITY_LEVELS[current_character['rarity']]
        caption = (
            f"🎨 Guess the Anime Character!\n\n"
            f"💬 Name: ???\n"
            f"⚔️ Rarity: {rarity} {current_character['rarity']}\n"
        )
        try:
            bot.send_photo(chat_id, current_character['image_url'], caption=caption)
        except Exception as e:
            print(f"Error sending character image: {e}")
            bot.send_message(chat_id, "❌ Unable to send character image.")

def is_owner_or_sudo(user_id):
    return user_id == BOT_OWNER_ID or user_id in SUDO_USERS

# Command Handlers

# Welcome Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if not user['profile']:
        profile_name = message.from_user.full_name
        update_user_data(user_id, {'profile': profile_name})

    welcome_message = """
<b>🝮︎︎︎ Welcome to Pʜɪʟᴏ 🝮︎︎︎ Gᴀᴍᴇ 🝮︎︎︎</b>

🎮 Ready to dive into the world of anime characters? Let’s start collecting and guessing!

🝮︎︎︎ Use the commands below to explore all the features!
"""
    markup = InlineKeyboardMarkup()
    developer_button = InlineKeyboardButton(text="Developer - @TechPiro", url="https://t.me/TechPiro")
    markup.add(developer_button)

    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML', reply_markup=markup)

# Help Command
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
<b>📜 🝮︎︎︎ Available Commands 🝮︎︎︎ 📜</b>

🎮 <b>Character Commands:</b>
/bonus - Claim your daily bonus 🝮︎︎︎
/inventory - View your character inventory 🝮︎︎︎
/gift - Gift coins to another user by tagging them 🝮︎︎︎
/profile - Show your personal stats (rank, coins, guesses, etc.) 🝮︎︎︎

🏆 <b>Leaderboards:</b>
/leaderboard - Show the top 10 users by coins 🝮︎︎︎
/topcoins - Show the top 10 users by coins earned today 🝮︎︎︎
/topgroups - Show the top 10 most active groups by messages 🝮︎︎︎

📊 <b>Bot Stats:</b>
/stats - Show the bot's stats (total users, characters, groups) 🝮︎︎︎

ℹ️ <b>Miscellaneous:</b>
/upload - Upload a new character (Sudo only) 🝮︎︎︎
/delete - Delete a character by ID (Sudo only) 🝮︎︎︎
/help - Show this help message 🝮︎︎︎

🝮︎︎︎ Have fun and start collecting! 🝮︎︎︎
"""
    bot.reply_to(message, help_message, parse_mode='HTML')

# Bonus Command
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    last_bonus_time = user.get('last_bonus')

    if last_bonus_time:
        last_bonus = datetime.strptime(last_bonus_time, '%Y-%m-%d %H:%M:%S.%f')
    else:
        last_bonus = None

    now = datetime.utcnow()

    if last_bonus and now - last_bonus < BONUS_INTERVAL:
        remaining_time = BONUS_INTERVAL - (now - last_bonus)
        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        bot.reply_to(message, f"🕑 You have already claimed your bonus. Please try again in {hours} hours and {minutes} minutes.")
    else:
        new_coins = user['coins'] + BONUS_COINS
        update_user_data(user_id, {'coins': new_coins, 'last_bonus': now.strftime('%Y-%m-%d %H:%M:%S.%f')})
        bot.reply_to(message, f"🎁 You claimed your daily bonus of {BONUS_COINS} coins! 🝮︎︎︎")

# /topcoins Command - Top 10 users with most coins today
@bot.message_handler(commands=['topcoins'])
def show_top_coins(message):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    top_users = list(users_collection.find({"last_bonus": {"$gte": today}})
                     .sort("coins", -1)
                     .limit(10))
    
    if not top_users:
        bot.reply_to(message, "No users have earned coins today.")
        return

    leaderboard_message = "<b>🏆 Top 10 Users by Coins Earned Today 🝮︎︎︎</b>\n\n"
    for i, user in enumerate(top_users):
        username = user.get('profile', 'Unknown')
        coins = user['coins']
        leaderboard_message += f"{i+1}. {username}: {coins} coins\n"

    bot.reply_to(message, leaderboard_message, parse_mode='HTML')

# /topgroups Command - Top 10 most active groups by messages (use group names)
@bot.message_handler(commands=['topgroups'])
def show_top_groups(message):
    top_groups = list(groups_collection.find().sort("message_count", -1).limit(TOP_LEADERBOARD_LIMIT))
    
    if not top_groups:
        bot.reply_to(message, "No active groups found.")
        return

    leaderboard_message = "<b>🏆 Top 10 Most Active Groups by Messages 🝮︎︎︎</b>\n\n"
    for i, group in enumerate(top_groups):
        group_name = group.get('group_name', 'Unnamed Group')
        message_count = group.get('message_count', 0)
        leaderboard_message += f"{i+1}. {group_name}: {message_count} messages\n"

    bot.reply_to(message, leaderboard_message, parse_mode='HTML')

# Track group activity on each message
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def handle_group_message(message):
    chat_id = message.chat.id
    chat_name = message.chat.title if message.chat.title else 'Unnamed Group'
    track_group_activity(chat_id, chat_name)

    # Call the original message handler (if necessary)
    handle_all_messages(message)

# Handle all types of messages and increment the message counter
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_character
    global global_message_count
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_guess = message.text.strip().lower() if message.text else ""

    # Increment the global message count for group chats
    if message.chat.type in ['group', 'supergroup']:
        global_message_count += 1

    if global_message_count >= MESSAGE_THRESHOLD:
        send_character(chat_id)
        global_message_count = 0  # Reset message count after sending character

    if current_character and user_guess:
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

            bot.reply_to(message, f"🎉 Congratulations! You guessed correctly and earned {COINS_PER_GUESS} coins! 🝮︎︎︎\n"
                                  f"🔥 Streak Bonus: {streak_bonus} coins for a {user['streak']}-guess streak! 🝮︎︎︎")
            
            send_character(chat_id)

# Handle /leaderboard Command - Show top 10 users by total coins
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    top_users = list(users_collection.find().sort("coins", -1).limit(TOP_LEADERBOARD_LIMIT))
    
    if not top_users:
        bot.reply_to(message, "No users found in the leaderboard.")
        return

    leaderboard_message = "<b>🏆 Top 10 Users 🝮︎︎︎</b>\n\n"
    for i, user in enumerate(top_users):
        username = user.get('profile', 'Unknown')
        coins = user['coins']
        leaderboard_message += f"{i+1}. {username}: {coins} coins\n"

    bot.reply_to(message, leaderboard_message, parse_mode='HTML')

# /inventory Command with pagination and rarity-based character grouping
def paginate_inventory(user_id, page=1):
    user = get_user_data(user_id)
    inventory = user.get('inventory', [])

    rarity_groups = {
        'Common': {},
        'Rare': {},
        'Epic': {},
        'Legendary': {}
    }

    for character in inventory:
        if isinstance(character, dict):
            rarity = character['rarity']
            name = character['character_name']
            if name in rarity_groups[rarity]:
                rarity_groups[rarity][name] += 1
            else:
                rarity_groups[rarity][name] = 1

    all_characters = []
    for rarity in ['Legendary', 'Epic', 'Rare', 'Common']:
        for name, count in rarity_groups[rarity].items():
            all_characters.append((name, rarity, count))

    total_items = len(all_characters)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    inventory_page = all_characters[start:end]

    message = f"🎒 **Your Character Inventory (Page {page}/{total_pages}) 🝮︎︎︎:**\n"
    
    current_rarity = None
    for name, rarity, count in inventory_page:
        if current_rarity != rarity:
            current_rarity = rarity
            message += f"\n<b>🝮︎︎︎ {RARITY_LEVELS[current_rarity]} {current_rarity} 🝮︎︎︎</b>\n"
        message += f"🝮︎︎︎ {name} ×{count}\n"

    return message, total_pages

@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    page = 1
    inventory_message, total_pages = paginate_inventory(user_id, page)

    markup = InlineKeyboardMarkup()
    if total_pages > 1:
        markup.add(InlineKeyboardButton('Next 🝮︎︎︎', callback_data=f'inventory_{page+1}'))

    bot.send_message(message.chat.id, inventory_message, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('inventory_'))
def paginate_inventory_callback(call):
    user_id = call.from_user.id
    page = int(call.data.split('_')[1])

    inventory_message, total_pages = paginate_inventory(user_id, page)

    markup = InlineKeyboardMarkup()
    if page > 1:
        markup.add(InlineKeyboardButton('Previous 🝮︎︎︎', callback_data=f'inventory_{page-1}'))
    if page < total_pages:
        markup.add(InlineKeyboardButton('Next 🝮︎︎︎', callback_data=f'inventory_{page+1}'))

    bot.edit_message_text(inventory_message, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

# /profile Command
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    # Fetch user's rank
    rank, total_users, coins_to_next_rank = get_user_rank(user_id)
    
    # User information
    profile_name = user.get('profile', 'Unknown')
    coins = user.get('coins', 0)
    correct_guesses = user.get('correct_guesses', 0)
    streak = user.get('streak', 0)
    
    profile_message = (
        f"<b>🝮︎︎︎ {profile_name}'s Profile 🝮︎︎︎</b>\n"
        f"🏅 Rank: {rank}/{total_users}\n"
        f"💰 Coins: {coins}\n"
        f"🎯 Correct Guesses: {correct_guesses}\n"
        f"🔥 Streak: {streak}\n"
    )

    if coins_to_next_rank:
        profile_message += f"Next rank in {coins_to_next_rank} coins.\n"

    bot.reply_to(message, profile_message, parse_mode='HTML')

# /gift Command - Gift coins to another user
@bot.message_handler(commands=['gift'])
def gift_coins(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ You must reply to a user's message to gift coins.")
        return
    
    user_id = message.from_user.id
    target_user_id = message.reply_to_message.from_user.id
    user = get_user_data(user_id)
    target_user = get_user_data(target_user_id)

    try:
        # Extract the amount of coins from the message
        amount = int(message.text.split()[1])
        
        if amount <= 0:
            bot.reply_to(message, "❌ You can only gift a positive amount of coins.")
            return

        if user['coins'] < amount:
            bot.reply_to(message, "❌ You don't have enough coins to gift.")
            return

        # Update both users' data
        update_user_data(user_id, {'coins': user['coins'] - amount})
        update_user_data(target_user_id, {'coins': target_user['coins'] + amount})

        bot.reply_to(message, f"🎁 You successfully gifted {amount} coins to {message.reply_to_message.from_user.full_name}!")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Please provide a valid amount of coins to gift.")

# /upload Command - Sudo only command to add a new character
@bot.message_handler(commands=['upload'])
def upload_character(message):
    user_id = message.from_user.id
    if not is_owner_or_sudo(user_id):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return
    
    bot.send_message(message.chat.id, "Please send the character name, image URL, and rarity separated by commas (e.g., 'Character Name, https://image.url, Epic')")

    @bot.message_handler(func=lambda m: True)
    def handle_upload(message):
        try:
            # Extract the character details
            character_data = message.text.split(',')
            character_name = character_data[0].strip()
            image_url = character_data[1].strip()
            rarity = character_data[2].strip()
            
            if rarity not in RARITY_LEVELS:
                bot.reply_to(message, "❌ Invalid rarity. Use one of the following: Common, Rare, Epic, Legendary.")
                return

            # Insert into the MongoDB collection
            new_character = add_character(image_url, character_name, rarity)
            
            bot.reply_to(message, f"✅ Character '{character_name}' added successfully!")
        except Exception as e:
            bot.reply_to(message, f"❌ Error adding character: {e}")

# /delete Command - Sudo only command to delete a character
@bot.message_handler(commands=['delete'])
def delete_character_command(message):
    user_id = message.from_user.id
    if not is_owner_or_sudo(user_id):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return
    
    try:
        character_id = int(message.text.split()[1])
        result = delete_character(character_id)
        if result.deleted_count > 0:
            bot.reply_to(message, f"✅ Character with ID {character_id} has been deleted.")
        else:
            bot.reply_to(message, f"❌ No character found with ID {character_id}.")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Please provide a valid character ID to delete.")

# /stats Command - Shows global statistics about the bot
@bot.message_handler(commands=['stats'])
def show_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_groups = groups_collection.count_documents({})

    stats_message = (
        f"📊 <b>Bot Stats 🝮︎︎︎</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🎨 Total Characters: {total_characters}\n"
        f"🏠 Total Groups: {total_groups}\n"
    )
    bot.reply_to(message, stats_message, parse_mode='HTML')

# Start polling the bot
bot.infinity_polling(timeout=60, long_polling_timeout=60)
