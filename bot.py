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
API_TOKEN = "7831268505:AAFoIXdZ3JWqym0GL4wkCFBwa3s60M7KcQo"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# API Endpoints
KITSU_API_URL = "https://kitsu.io/api/edge/characters?filter[name]="  # For character images

# SQLite Database setup
conn = sqlite3.connect('game_data.db', check_same_thread=False)
c = conn.cursor()

# Create table for storing player data if it doesn't exist
c.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    coins INTEGER DEFAULT 0,
    correct_guesses INTEGER DEFAULT 0,
    last_daily TEXT
)
''')
conn.commit()

# Helper function to get player data
def get_player_data(user_id, username):
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = c.fetchone()
    if not player:
        # Add a new player if not found
        c.execute('INSERT INTO players (user_id, username, coins, correct_guesses, last_daily) VALUES (?, ?, 0, 0, NULL)', (user_id, username))
        conn.commit()
        return get_player_data(user_id, username)  # Get the data after inserting
    return player

# Update player data
def update_player_data(user_id, coins=None, correct_guesses=None, last_daily=None):
    current_data = get_player_data(user_id, "")
    new_coins = coins if coins is not None else current_data[2]
    new_correct_guesses = correct_guesses if correct_guesses is not None else current_data[3]
    new_last_daily = last_daily if last_daily is not None else current_data[4]
    c.execute('UPDATE players SET coins = ?, correct_guesses = ?, last_daily = ? WHERE user_id = ?',
              (new_coins, new_correct_guesses, new_last_daily, user_id))
    conn.commit()

# Fetch character image from Kitsu API based on character name
def fetch_character_image(character_name):
    try:
        response = requests.get(f"{KITSU_API_URL}{character_name}")
        response.raise_for_status()
        data = response.json()
        if len(data['data']) > 0:
            # Extract image URL from Kitsu API response
            image_url = data['data'][0]['attributes']['image']['original']
            return image_url
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching character image from Kitsu API: {e}")
        return None

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /start_game to begin guessing characters by their image. Use /help to see all available commands.")

# Help Command - Shows all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
Available commands:
/start - Start the bot and get a welcome message
/start_game - Start a new round of the guessing game
/leaderboard - Show the leaderboard with top players
/daily_reward - Claim your daily coins reward
/help - Show this help message
"""
    bot.reply_to(message, help_message)

# Daily Reward Command - Claim a daily reward
@bot.message_handler(commands=['daily_reward'])
def daily_reward(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Get player data
    player = get_player_data(user_id, username)
    now = datetime.now()
    last_claim = player[4]  # last_daily column
    
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
    # List of sample characters for the game
    characters = ['Naruto Uzumaki', 'Sasuke Uchiha', 'Goku', 'Luffy', 'Zoro', 'Ichigo Kurosaki', 'Edward Elric']

    # Pick a random character from the list
    character_name = random.choice(characters)

    # Try to get the character's image from Kitsu
    character_image = fetch_character_image(character_name)

    # Store the character name for this session
    bot.current_character = character_name.lower()
    bot.current_user = message.from_user.id  # Track the user who should guess

    # Send the image
    if character_image:
        bot.send_photo(message.chat.id, character_image, caption="Guess the name of this anime character!")
    else:
        bot.reply_to(message, "Sorry, I couldn't find the character's image. Guess the name of this anime character!")

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
            # Correct guess: Add 10 coins
            new_coins = player[2] + 10
            new_correct_guesses = player[3] + 1
            update_player_data(user_id, coins=new_coins, correct_guesses=new_correct_guesses)
            bot.reply_to(message, f"🎉 Correct! The character was {bot.current_character.capitalize()}. You've earned 10 coins! Total coins: {new_coins}. A new character will be fetched in 30 seconds.")

            # Fetch a new character after 30 seconds
            threading.Thread(target=auto_fetch_character, args=(message,)).start()
        else:
            bot.reply_to(message, "❌ Wrong! Try again.")

# Auto-fetch a new character after 30 seconds
def auto_fetch_character(message):
    time.sleep(30)  # Wait for 30 seconds
    start_game(message)  # Fetch a new character

# Leaderboard Command - Displays the Top Players by Coins and Correct Guesses
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    c.execute('SELECT username, coins, correct_guesses FROM players ORDER BY coins DESC LIMIT 10')
    leaderboard_data = c.fetchall()
    
    leaderboard_message = "🏆 Leaderboard:\n"
    for rank, (username, coins, correct_guesses) in enumerate(leaderboard_data, start=1):
        leaderboard_message += f"{rank}. {username}: {coins} coins, {correct_guesses} correct guesses\n"
    
    bot.reply_to(message, leaderboard_message)

# Run the bot
bot.infinity_polling()
    
