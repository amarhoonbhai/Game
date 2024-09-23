import telebot
import requests
import random
import sqlite3
from datetime import datetime, timedelta
import logging

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAFAwTBSkJrIcC9Aj9eGFzYRnPPQFk4pJmg"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Jikan API URL for fetching characters
JIKAN_API_URL = "https://api.jikan.moe/v4/characters"

# Function to fetch a random anime character from Jikan API
def fetch_random_anime_character():
    try:
        # Get a random page from the Jikan API (there are many characters available)
        page = random.randint(1, 50)
        response = requests.get(f"{JIKAN_API_URL}?page={page}")
        response.raise_for_status()
        data = response.json()

        # Select a random character from the returned list
        characters = data['data']
        if characters:
            character = random.choice(characters)
            character_name = character['name']
            character_image = character['images']['jpg']['image_url']  # Character image
            return {
                'name': character_name,
                'image': character_image
            }
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching character from Jikan API: {e}")
        return None

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /start_game to begin guessing characters by their image.")

# Start Game Command - Sends a Random Anime Character's Image
@bot.message_handler(commands=['start_game'])
def start_game(message):
    character = fetch_random_anime_character()
    if character is None:
        bot.reply_to(message, "Sorry, I couldn't fetch a character right now. Try again later.")
    else:
        character_name = character['name']
        character_image = character['image']

        # Store the character for this session
        bot.current_character = character_name.lower()

        # Send the character image and prompt the user to guess the name
        bot.send_photo(message.chat.id, character_image, caption="Guess the name of this anime character!")

# Guess Command - Validate the Guess and Send the Next Character Automatically
@bot.message_handler(commands=['guess'])
def guess(message):
    guess_text = message.text[len("/guess "):].lower()

    # Check if the guess matches the current character's name
    if guess_text == bot.current_character:
        # Correct guess
        bot.reply_to(message, f"Correct! The character was {bot.current_character.capitalize()}. Here's the next one:")
        
        # Fetch and send a new character automatically
        start_game(message)
    else:
        # Wrong guess
        bot.reply_to(message, "Wrong guess! Try again.")

# Run the bot
bot.infinity_polling()
