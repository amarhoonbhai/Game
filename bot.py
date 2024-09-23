import os
import telebot
import random
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file (optional if you want to use env for sensitive data)
load_dotenv()

# Retrieve bot API token from environment variables
API_TOKEN = os.getenv('TELEGRAM_BOT_API_TOKEN')

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# Dictionary to track current characters and guess attempts for each user
current_game_state = {
    "character_name": None,
    "user_attempts": {}  # Format: {user_id: attempts}
}

# Coins for correct guess
COINS_PER_GUESS = 10
MAX_INCORRECT_GUESSES = 2

# Function to simulate fetching a random character name
def fetch_random_character():
    character_names = ["Naruto", "Sasuke", "Sakura", "Luffy", "Goku", "Vegeta", "Zoro", "Nami", "Hinata", "Kakashi"]
    return random.choice(character_names)

# Function to reset the game state and send a new character prompt
def send_new_character(chat_id):
    global current_game_state
    character_name = fetch_random_character()

    if character_name:
        # Reset attempts for each user when a new character is shown
        current_game_state["user_attempts"] = {}
        current_game_state["character_name"] = character_name.lower()  # Store character name in lowercase for easy comparison
        
        # Send the new character prompt to the chat (No URL, just character guessing)
        bot.send_message(chat_id, "🎨 Guess the name of this anime character!")
    else:
        # Simulated error message (no image URL)
        bot.send_message(chat_id, "⚠️ Sending characters in some time, please wait...")

# Function to handle guesses
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    global current_game_state
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_guess = message.text.strip().lower()

    # Check if there's an active character for guessing
    if current_game_state["character_name"]:
        # Check if the user is guessing the correct name
        if user_guess == current_game_state["character_name"]:
            # Correct guess
            bot.reply_to(message, f"🎉 Congratulations! You guessed correctly and earned {COINS_PER_GUESS} coins!")
            send_new_character(chat_id)  # Send a new character after the correct guess
        else:
            # Incorrect guess
            if user_id not in current_game_state["user_attempts"]:
                current_game_state["user_attempts"][user_id] = 1
            else:
                current_game_state["user_attempts"][user_id] += 1

            attempts = current_game_state["user_attempts"][user_id]
            
            if attempts >= MAX_INCORRECT_GUESSES:
                # Max incorrect guesses reached, send new character
                bot.reply_to(message, f"❌ You've made {MAX_INCORRECT_GUESSES} incorrect guesses. Here's a new character.")
                send_new_character(chat_id)
            else:
                # Warn the user about the incorrect guess
                bot.reply_to(message, f"❌ Incorrect guess. You have {MAX_INCORRECT_GUESSES - attempts} attempts left.")

# Start Command - Begins by sending the first character prompt
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Try to guess the character's name.")
    send_new_character(message.chat.id)

# Start polling the bot
bot.infinity_polling()
