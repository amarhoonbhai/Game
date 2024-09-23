import telebot
import requests
import random
import sqlite3
from datetime import datetime, timedelta
import logging
import time
import threading

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAH2xempmcyNJFFDk4KehWpaYDeOJQRk5p0"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Define the bot owner's Telegram ID (replace this with your own Telegram ID)
bot_owner_id = 7222795580  # Replace with your Telegram user ID

# API Endpoints
JIKAN_API_URL = "https://api.jikan.moe/v4/characters?page={}"
KITSU_API_URL = "https://kitsu.io/api/edge/characters"
ANILIST_API_URL = "https://graphql.anilist.co"

# SQLite Database setup
conn = sqlite3.connect('game_data.db', check_same_thread=False)
c = conn.cursor()

# Create tables for storing player and group data if they don't exist
c.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    coins INTEGER DEFAULT 0,
    correct_guesses INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_daily TEXT
)
''')
conn.commit()

c.execute('''
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY
)
''')
conn.commit()

# Helper function to get player data
def get_player_data(user_id, username):
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = c.fetchone()
    if not player:
        # Add a new player if not found
        c.execute('INSERT INTO players (user_id, username, coins, correct_guesses, streak, last_daily) VALUES (?, ?, 0, 0, 0, NULL)', (user_id, username))
        conn.commit()
        return get_player_data(user_id, username)  # Get the data after inserting
    return player

# Update player data
def update_player_data(user_id, coins=None, correct_guesses=None, streak=None, last_daily=None):
    current_data = get_player_data(user_id, "")
    new_coins = coins if coins is not None else current_data[2]
    new_correct_guesses = correct_guesses if correct_guesses is not None else current_data[3]
    new_streak = streak if streak is not None else current_data[4]
    new_last_daily = last_daily if last_daily is not None else current_data[5]
    c.execute('UPDATE players SET coins = ?, correct_guesses = ?, streak = ?, last_daily = ? WHERE user_id = ?',
              (new_coins, new_correct_guesses, new_streak, new_last_daily, user_id))
    conn.commit()

# Add user to database if not already there
def add_user_to_db(user_id, username):
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = c.fetchone()
    if not player:
        c.execute('INSERT INTO players (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()

# Add group to database if not already there
def add_group_to_db(group_id):
    c.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = c.fetchone()
    if not group:
        c.execute('INSERT INTO groups (group_id) VALUES (?)', (group_id,))
        conn.commit()

# Fetch random character from Jikan API (MyAnimeList)
def fetch_random_character_jikan():
    try:
        page = random.randint(1, 50)  # Random page number to fetch more characters
        response = requests.get(JIKAN_API_URL.format(page))
        response.raise_for_status()
        data = response.json()

        if data['data']:
            character = random.choice(data['data'])
            character_name = character['name']
            character_image = character['images']['jpg']['image_url']
            return {'name': character_name, 'image': character_image}
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching character from Jikan API: {e}")
        return None

# Fetch random character from Kitsu API
def fetch_random_character_kitsu():
    try:
        response = requests.get(KITSU_API_URL)
        response.raise_for_status()
        data = response.json()

        if data['data']:
            character = random.choice(data['data'])
            character_name = character['attributes']['name']
            character_image = character['attributes']['image']['original']
            return {'name': character_name, 'image': character_image}
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching character from Kitsu API: {e}")
        return None

# Fetch random character from AniList API (GraphQL)
def fetch_random_character_anilist():
    query = '''
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        characters {
          name {
            full
          }
          image {
            large
          }
        }
      }
    }
    '''
    variables = {'page': random.randint(1, 50), 'perPage': 1}
    
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables})
        response.raise_for_status()
        data = response.json()

        if data['data']['Page']['characters']:
            character = data['data']['Page']['characters'][0]
            character_name = character['name']['full']
            character_image = character['image']['large']
            return {'name': character_name, 'image': character_image}
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching character from AniList API: {e}")
        return None

# Fetch a random character from one of the APIs
def fetch_random_character():
    api_choice = random.choice(['jikan', 'kitsu', 'anilist'])  # Randomly choose an API
    
    if api_choice == 'jikan':
        return fetch_random_character_jikan()
    elif api_choice == 'kitsu':
        return fetch_random_character_kitsu()
    elif api_choice == 'anilist':
        return fetch_random_character_anilist()

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /start_game to begin guessing characters by their image. Use /help to see all available commands.")
    
    # Track unique users and groups
    if message.chat.type == 'private':
        add_user_to_db(message.from_user.id, message.from_user.username or message.from_user.first_name)
    elif message.chat.type in ['group', 'supergroup']:
        add_group_to_db(message.chat.id)

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/start_game - Start a new round of the guessing game
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/hint - Get a hint for the current character
/help - Show this help message
/stats - Show the number of users and groups (Owner only)
"""
    bot.reply_to(message, help_message)

# Stats Command - Only for bot owner
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == bot_owner_id:
        # Count the number of users and groups
        c.execute('SELECT COUNT(*) FROM players')
        user_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM groups')
        group_count = c.fetchone()[0]
        
        bot.reply_to(message, f"📊 Stats:\nTotal users: {user_count}\nTotal groups: {group_count}")
    else:
        bot.reply_to(message, "❌ You are not authorized to view this information.")

# Daily Reward Command - Claim a daily reward
@bot.message_handler(commands=['daily_reward'])
def daily_reward(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Get player data
    player = get_player_data(user_id, username)
    now = datetime.now()
    last_claim = player[5]  # last_daily column
    
    # Check if 24 hours have passed since the last claim
    if last_claim is None or (now - datetime.fromisoformat(last_claim)).days >= 1:
        # Award 50 coins for daily reward
        new_coins = player[2] + 50
        update_player_data(user_id, coins=new_coins, last_daily=now.isoformat())
        bot.reply_to(message, f"🎁 You claimed your daily reward of 50 coins! Total coins: {new_coins}")
    else:
        bot.reply_to(message, "🕒 You have already claimed your daily reward. Come back tomorrow!")

# Start Game Command - Sends a Random Anime Character's Image
@bot.message_handler(commands=['start_game'])
def start_game(message):
    character = fetch_random_character()
    if character is None:
        bot.reply_to(message, "Sorry, I couldn't fetch a character right now. Try again later.")
        return

    # Store the character name for this session
    bot.current_character = character['name'].lower()
    bot.current_user = message.from_user.id  # Track the user who should guess
    bot.incorrect_guess_count = 0  # Track incorrect guesses

    # Send the character image
    bot.send_photo(message.chat.id, character['image'], caption="Guess the name of this anime character!")

# Guess Handler - Detect User Messages for Guesses
@bot.message_handler(func=lambda message: True)
def detect_guess(message):
    guess_text = message.text.lower()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Check if this message is a guess and if the user matches the active game
    if hasattr(bot, 'current_character') and bot.current_character and bot.current_user == user_id:
        # Get player data
        player = get_player_data(user_id, username)

        if guess_text == bot.current_character:
            # Correct guess: Add 10 coins + streak bonus (5 coins per streak)
            streak = player[4] + 1  # Increase streak
            coins_awarded = 10 + (5 * streak)  # Add bonus for streak
            new_coins = player[2] + coins_awarded
            new_correct_guesses = player[3] + 1
            update_player_data(user_id, coins=new_coins, correct_guesses=new_correct_guesses, streak=streak)
            bot.reply_to(message, f"🎉 Correct! The character was {bot.current_character.capitalize()}. You've earned {coins_awarded} coins (with a streak of {streak}). Total coins: {new_coins}. A new character will be fetched in 30 seconds.")
            # Fetch a new character after 30 seconds
            threading.Thread(target=auto_fetch_character, args=(message,)).start()
        else:
            bot.incorrect_guess_count += 1
            bot.reply_to(message, "❌ Wrong! Try again.")
            
            if bot.incorrect_guess_count >= 3:
                # Auto-fetch a new character after 3 incorrect guesses
                bot.reply_to(message, "Too many wrong guesses! Fetching a new character.")
                threading.Thread(target=auto_fetch_character, args=(message,)).start()

# Auto-fetch a new character after 30 seconds
def auto_fetch_character(message):
    time.sleep(30)  # Wait for 30 seconds
    start_game(message)  # Fetch a new character

# Hint Command - Reveals the first letter of the current character's name
@bot.message_handler(commands=['hint'])
def reveal_hint(message):
    if hasattr(bot, 'current_character') and bot.current_character:
        hint = bot.current_character[0].upper()  # First letter of the character's name
        bot.reply_to(message, f"🔍 Hint: The first letter of the character's name is {hint}")
    else:
        bot.reply_to(message, "No character is currently active. Use /start_game to begin a new game.")

# Leaderboard Command - Displays the Top Players by Coins and Correct Guesses
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    c.execute('SELECT username, coins, correct_guesses, streak FROM players ORDER BY coins DESC LIMIT 10')
    leaderboard_data = c.fetchall()
    
    leaderboard_message = "🏆 Leaderboard:\n"
    for rank, (username, coins, correct_guesses, streak) in enumerate(leaderboard_data, start=1):
        leaderboard_message += f"{rank}. {username}: {coins} coins, {correct_guesses} correct guesses, {streak} streak\n"
    
    bot.reply_to(message, leaderboard_message)

# Run the bot
bot.infinity_polling()
