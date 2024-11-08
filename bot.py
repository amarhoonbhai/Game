import telebot
from pymongo import MongoClient
import random

# Initialize bot and MongoDB client
API_TOKEN = '6862816736:AAHHRMIYbDJfmp_ocupPy2oAgKu8eg39m2k'
MONGO_URI = 'mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu'
bot = telebot.TeleBot(API_TOKEN)
client = MongoClient(MONGO_URI)
db = client['philo_waifu_db']
users_collection = db['users']
characters_collection = db['characters']
leaderboard_collection = db['leaderboard']

# Define rarity levels with symbols
RARITIES = [
    ("Bronze", "✹"),
    ("Silver", "✠"),
    ("Gold", "☉"),
    ("Platinum", "❀"),
    ("Diamond", "♡")
]

MESSAGE_THRESHOLD = 5  # Threshold for messages before sending a new character

# Command: /start - Welcomes user and begins the game
@bot.message_handler(commands=['start'])
def start_game(message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})
    
    if user is None:
        # Register new user with initial settings
        users_collection.insert_one({
            "user_id": user_id,
            "username": message.from_user.username,
            "coins": 10,
            "level": 1,
            "message_count": 0  # Initialize message count
        })
        bot.send_message(user_id, "❀ Welcome to Philo Waifu ❀\n\n"
                                  "✹ Dive into the world of anime characters! Guess characters, earn coins, gain XP, and level up. ✹\n\n"
                                  "Use the commands to start guessing and explore the game. Let's see how many characters you can guess!\n\n"
                                  "✠ Let the adventure begin! ✠")
    else:
        bot.send_message(user_id, "❀ Welcome back to Philo Waifu! ❀")
    
    # Send the first character for guessing
    send_character(user_id)

# Function to send a character for guessing
def send_character(user_id):
    character = random.choice(list(characters_collection.find()))
    bot.send_photo(user_id, character['img_url'], caption=f"☢ Guess the character: {character['hint']}")
    
    # Reset message count after sending a character
    users_collection.update_one({"user_id": user_id}, {"$set": {"message_count": 0}})
    
    # Register next step for guessing
    bot.register_next_step_handler_by_chat_id(user_id, check_guess, character)

# Function to check user’s guess and handle message threshold
def check_guess(message, character):
    user_id = message.from_user.id
    guess = message.text.strip().lower()
    
    user = users_collection.find_one({"user_id": user_id})
    message_count = user.get("message_count", 0) + 1
    
    if guess == character['name'].lower():
        # Correct guess: Update user's profile and leaderboard
        users_collection.update_one({"user_id": user_id}, {
            "$inc": {"coins": 5, "level": 1},
            "$set": {"message_count": 0}  # Reset message count on correct guess
        })
        bot.send_message(user_id, f"✅ Correct! You've earned 5 coins and leveled up! ✹\n"
                                  f"Rarity: {character['rarity']} {character['emoji']}")
        
        # Update leaderboard score
        leaderboard_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"score": 1}},
            upsert=True
        )
        
        # Send a new character immediately after a correct guess
        send_character(user_id)
    else:
        # Incorrect guess: Increase message count and deduct coins
        users_collection.update_one({"user_id": user_id}, {"$inc": {"coins": -1, "message_count": 1}})
        bot.send_message(user_id, "❌ Incorrect! You've lost 1 coin.")
        
        # Check if message threshold is reached
        if message_count >= MESSAGE_THRESHOLD:
            send_character(user_id)
        else:
            # Update message count and prompt for another guess
            users_collection.update_one({"user_id": user_id}, {"$set": {"message_count": message_count}})
            bot.register_next_step_handler(message, check_guess, character)

# Command: /help - Display available commands and information
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "💡 **Philo Waifu Bot Commands** 💡\n\n"
        "/start - Start the game and receive your first character\n"
        "/profile - View your profile with coins and level\n"
        "/leaderboard - Check the top players\n"
        "/stats - View bot statistics ❀\n"
        "/upload - (Admin only) Upload a new character in format 'img_url name'\n\n"
        "🔧 **Bot Owner**: [Contact Owner](https://t.me/7222795580)\n"
        "📢 **Join Group**: [PhiloMusicSupport](https://t.me/PhiloMusicSupport)"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

# Command: /leaderboard - Show the top players
@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    leaderboard = leaderboard_collection.find().sort("score", -1).limit(10)
    leaderboard_message = "❀ **Leaderboard** ❀\n\n"
    
    for idx, entry in enumerate(leaderboard, start=1):
        user = users_collection.find_one({"user_id": entry['user_id']})
        leaderboard_message += f"{idx}. {user['username']} - {entry['score']} points ✠\n"
        
    bot.send_message(message.chat.id, leaderboard_message, parse_mode="Markdown")

# Command: /upload (Admin only) - Upload a new character with image URL and name
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if message.from_user.username != 'admin_username':
        bot.send_message(message.chat.id, "You do not have permission to upload characters.")
        return
    
    bot.send_message(message.chat.id, "Enter the character image URL and name in the format 'img_url name'")
    bot.register_next_step_handler(message, save_character)

# Function to save character with random rarity assignment
def save_character(message):
    try:
        img_url, name = message.text.split(' ', 1)
        
        # Assign random rarity with symbol
        rarity, emoji = random.choice(RARITIES)
        
        # Save character to MongoDB
        characters_collection.insert_one({
            "name": name.strip(),
            "img_url": img_url.strip(),
            "hint": name[0].upper() + "_" * (len(name) - 2) + name[-1].upper(),  # Generate hint
            "rarity": rarity,
            "emoji": emoji
        })
        bot.send_message(message.chat.id, f"✅ Character {name.strip()} added successfully as {rarity} {emoji}!")
        
    except ValueError:
        bot.send_message(message.chat.id, "Invalid format. Please use 'img_url name'.")

# Command: /profile - Show user's profile details
@bot.message_handler(commands=['profile'])
def view_profile(message):
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})
    
    profile_message = (
        f"❀ **Username**: {user['username']}\n"
        f"☉ **Coins**: {user['coins']}\n"
        f"✹ **Level**: {user['level']}"
    )
    bot.send_message(user_id, profile_message, parse_mode="Markdown")

# Command: /stats - Show bot statistics like total users and characters
@bot.message_handler(commands=['stats'])
def bot_stats(message):
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    total_scores = leaderboard_collection.count_documents({})

    stats_message = (
        f"❀ **Philo Waifu Bot Stats** ❀\n\n"
        f"☉ **Total Users**: {total_users}\n"
        f"✠ **Total Characters**: {total_characters}\n"
        f"✹ **Total Leaderboard Entries**: {total_scores}\n"
    )
    bot.send_message(message.chat.id, stats_message, parse_mode="Markdown")

# Start bot polling to listen for messages
bot.polling()
