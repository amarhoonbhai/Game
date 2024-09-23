import telebot
import random
import threading
import time
import requests
from datetime import datetime

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAFdl5CI7fZ4RCfyyUf9_Aj3_GgnFTiloto"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Define bot owner and sudo users
bot_owner_id = "7222795580" # Replace with your Telegram user ID
sudo_users = "6180999156" # Add other sudo user IDs if necessary

# Define the log channel ID
log_channel_id = "-1002438449944"  # Replace with your character/log channel ID

# Track unique users and groups
unique_users = set()
unique_groups = set()

# API URLs for fetching anime images
API_URLS = [
    "https://nekos.life/api/v2/img/neko",  # Nekos API
    "https://waifu.pics/api/sfw/waifu",  # Waifu.it API
    "https://api.waifu.im/sfw/waifu/",  # Waifu.im API
    "https://anime-api.com/api/characters/random",  # NPM Anime API
    "https://api.anime-pictures.net/pictures/get_random",  # Anime Pictures API
]

# Rarity levels
RARITY_LEVELS = {
    'elite': '⚡',
    'epic': '💫',
    'legendary': '🥂',
    'mythical': '🔮'
}

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
    elif "anime-api.com" in api_url:
        return response.json().get("image_url")  # NPM Anime API returns "image_url"
    elif "anime-pictures.net" in api_url:
        return response.json().get("picture")  # Anime Pictures API returns "picture"
    return None

# Get a random rarity level
def get_random_rarity():
    return random.choice(list(RARITY_LEVELS.items()))  # Returns a tuple (rarity, emoji)

# Log to the character database channel
def log_character_to_channel(image_url, rarity):
    # Send character details to the log channel
    bot.send_message(log_channel_id, f"Character displayed:\nRarity: {rarity.capitalize()}\nImage URL: {image_url}")

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
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Characters will appear automatically.")
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
    image_url = fetch_random_image()
    if not image_url:
        bot.send_message(chat_id, "Sorry, couldn't fetch an image. Please try again later.")
        return
    
    # Get random rarity
    rarity, emoji = get_random_rarity()

    # Send the character image with rarity
    bot.send_photo(chat_id, image_url, caption=f"Guess the name of this anime character! Rarity: {rarity.capitalize()} {emoji}")

    # Log this character to the log channel
    log_character_to_channel(image_url, rarity)

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
