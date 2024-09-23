import telebot
import random
import threading
import time
import requests
from datetime import datetime

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAGJ_2R6ThDTk7C8ZaAfo5FS_CeW2BctVeI"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Define bot owner and sudo users
bot_owner_id = "7831268505" # Replace with your Telegram user ID
sudo_users = "6180999156"  # Add other sudo user IDs if necessary

# Define the log channel ID
log_channel_id =  "-1002438449944" # Replace with your character/log channel ID

# Track unique users and groups
unique_users = set()
unique_groups = set()

# API URLs for fetching anime images (keeping only working APIs)
API_URLS = [
    "https://nekos.life/api/v2/img/neko",  # Nekos API
    "https://waifu.pics/api/sfw/waifu",  # Waifu.it API
    "https://api.waifu.im/sfw/waifu/",  # Waifu.im API
]

# Rarity levels
RARITY_LEVELS = {
    'elite': '⚡',
    'epic': '💫',
    'legendary': '🥂',
    'mythical': '🔮'
}

# Current character being displayed (we'll store its image URL and name)
current_character = {
    "image_url": None,
    "name": "waifu",  # Default name for waifus (can be adjusted if APIs return names)
}

# Player data storage (for storing coins, streaks, and correct guesses)
players_data = {}

# Fetch a random image from one of the APIs
def fetch_random_image():
    api_url = random.choice(API_URLS)
    response = requests.get(api_url)
    
    # Handling responses for different APIs
    if "nekos.life" in api_url:
        return response.json().get("url")  # Nekos API returns image in "url" field
    elif "waifu.pics" in api_url:
        return response.json().get("url")  # Waifu.it API returns image in "url" field
    elif "waifu.im" in api_url:
        return response.json().get("url")  # Waifu.im API returns image in "url" field
    return None

# Get a random rarity level
def get_random_rarity():
    return random.choice(list(RARITY_LEVELS.items()))  # Returns a tuple (rarity, emoji)

# Log to the character database channel
def log_character_to_channel(image_url, rarity):
    # Send character details to the log channel (without the image URL)
    bot.send_message(log_channel_id, f"A character has been displayed!\nRarity: {rarity.capitalize()}")

# Track users and groups
def track_user_and_group(message):
    if message.chat.type == 'private':
        unique_users.add(message.from_user.id)  # Track unique user
    elif message.chat.type in ['group', 'supergroup']:
        unique_groups.add(message.chat.id)  # Track unique group

# Start Command - Automatically begins sending characters after 10 seconds
@bot.message_handler(commands=['start'])
def send_welcome(message):
    track_user_and_group(message)
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Beautiful characters are about to appear!")
    # Automatically start sending images after 10 seconds
    threading.Thread(target=automatic_image_sending, args=(message.chat.id,)).start()

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    track_user_and_group(message)
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/stats - Show stats (owner only)
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/help - Show this help message
"""
    bot.reply_to(message, help_message)

# Automatically send random images every 10 seconds
def automatic_image_sending(chat_id):
    while True:
        send_random_character(chat_id)
        time.sleep(10)

# Send a random character to the chat and log it to the log channel
def send_random_character(chat_id):
    global current_character

    image_url = fetch_random_image()
    if not image_url:
        bot.send_message(chat_id, "Sorry, couldn't fetch an image. Please try again later.")
        return
    
    # Get random rarity
    rarity, emoji = get_random_rarity()

    # Store the current character for future guessing
    current_character["image_url"] = image_url
    current_character["name"] = "waifu"  # Setting "waifu" as the character's name since the APIs do not return names.

    # Send the character image with an attractive caption and rarity
    attractive_captions = [
        f"✨ Behold! An {rarity.capitalize()} waifu has appeared! {emoji}",
        f"💖 Feast your eyes on this beautiful {rarity.capitalize()} waifu! {emoji}",
        f"🌟 A rare gem just for you! Here's an {rarity.capitalize()} waifu! {emoji}",
        f"🔥 You’re lucky! An {rarity.capitalize()} character is here to charm you! {emoji}"
    ]
    caption = random.choice(attractive_captions)

    # Send the image with the attractive caption
    bot.send_photo(chat_id, image_url, caption=caption)

    # Log this character to the log channel (without the URL)
    log_character_to_channel(image_url, rarity)

# Award coins and streak bonus for a correct guess
def award_coins(user_id, username):
    player = players_data.get(user_id, {"coins": 0, "correct_guesses": 0, "streak": 0})
    
    # Base coins for a correct guess
    base_coins = 10
    # Bonus coins for streak (5 coins per streak level)
    streak_bonus = 5 * player["streak"]

    # Update player's streak, coins, and correct guesses
    player["streak"] += 1  # Increase streak
    player["correct_guesses"] += 1  # Increase correct guesses
    player["coins"] += base_coins + streak_bonus  # Add coins with bonus

    # Save updated player data
    players_data[user_id] = player

    # Notify the user of their reward
    bot.reply_to(message, f"🎉 Congratulations {username}! You guessed correctly and earned {base_coins + streak_bonus} coins (Base: {base_coins} + Streak Bonus: {streak_bonus}). Total coins: {player['coins']} (Streak: {player['streak']})")

# Reset streak on an incorrect guess
def reset_streak(user_id):
    if user_id in players_data:
        players_data[user_id]["streak"] = 0  # Reset the streak

# Handle guesses from users without requiring /guess
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    global current_character

    # Normalize guess text and check if it matches the character's name
    guess_text = message.text.strip().lower()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if guess_text == current_character["name"]:
        # Award coins and streak bonus for a correct guess
        award_coins(user_id, username)
        # Fetch and send a new character immediately after a correct guess
        send_random_character(message.chat.id)
    else:
        bot.reply_to(message, "❌ Incorrect guess, try again!")
        # Reset the player's streak on incorrect guess
        reset_streak(user_id)

# Stats Command - Only for bot owner and sudo users to see the number of users and groups
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == bot_owner_id or message.from_user.id in sudo_users:
        bot.reply_to(message, f"📊 Stats:\nTotal unique users: {len(unique_users)}\nTotal unique groups: {len(unique_groups)}")
    else:
        bot.reply_to(message, "❌ You are not authorized to view this information.")

# Daily Reward Command - Claim a daily reward
@bot.message_handler(commands=['daily_reward'])
def daily_reward(message):
    track_user_and_group(message)
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Simulated player data storage for daily rewards and streaks
    if user_id not in players_data:
        players_data[user_id] = {"coins": 0, "correct_guesses": 0, "streak": 0, "last_daily": None}
    player = players_data[user_id]
    
    now = datetime.now()
    last_claim = player["last_daily"]

    # Check if 24 hours have passed since the last claim
    if last_claim is None or (now - last_claim).days >= 1:
        player["coins"] += 50
        player["last_daily"] = now
        bot.reply_to(message, f"🎁 You claimed your daily reward of 50 coins! Total coins: {player['coins']}")
    else:
        bot.reply_to(message, "🕒 You have already claimed your daily reward. Come back tomorrow!")

# Leaderboard Command - Displays the Top Players by Coins and Correct Guesses
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    track_user_and_group(message)
    sorted_players = sorted(players_data.items(), key=lambda p: p[1]['coins'], reverse=True)[:10]

    leaderboard_message = "🏆 Leaderboard:\n"
    for rank, (user_id, player_data) in enumerate(sorted_players, start=1):
        leaderboard_message += f"{rank}. {players_data[user_id]['username']}: {player_data['coins']} coins, {player_data['correct_guesses']} correct guesses, {player_data['streak']} streak\n"

    bot.reply_to(message, leaderboard_message)

# Run the bot
bot.infinity_polling()
