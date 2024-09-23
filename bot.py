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

# In-memory store for the current redeem code, expiry time, and users who redeemed
current_redeem_code = None
redeem_code_expiry = None
user_last_redeem = {}  # To track the last redeem time of each user
user_last_bonus = {}   # To track the last bonus claim time of each user

# Coins awarded for redeeming and daily bonus
COINS_PER_REDEEM = 50
COINS_PER_BONUS = 100

# Dictionary to track current characters and guess attempts for each user
current_game_state = {
    "image_url": None,
    "character_name": None,
    "user_attempts": {}  # Format: {user_id: attempts}
}

# Coins for correct guess
COINS_PER_GUESS = 10
MAX_INCORRECT_GUESSES = 2

# Function to fetch a random Zerochan image and character name
def fetch_zerochan_image():
    character_names = ["Naruto", "Sasuke", "Sakura", "Luffy", "Goku", "Vegeta", "Zoro", "Nami", "Hinata", "Kakashi"]
    search_url = 'https://www.zerochan.net/?s=random'
    response = requests.get(search_url)

    if response.status_code == 200:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        image = soup.find('img', class_='preview')
        if image:
            image_url = image['src']
            character_name = random.choice(character_names)
            return image_url, character_name
    return None, None

# Function to generate a random 5-character redeem code
def generate_random_code():
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=5))

# Function to generate a new redeem code every hour
def generate_redeem_code():
    global current_redeem_code, redeem_code_expiry
    while True:
        current_redeem_code = generate_random_code()
        redeem_code_expiry = datetime.now() + timedelta(hours=1)

        # Announce the new redeem code
        bot.send_message(chat_id="YOUR_GROUP_ID",  # Replace with your group ID or broadcast to users
                         text=f"🔑 New Redeem Code: {current_redeem_code}\nThis code is valid for 1 hour. Use /redeem <code> to claim coins!")

        # Wait for 1 hour before generating the next code
        time.sleep(3600)

# Function to check if a user can redeem
def can_redeem(user_id):
    now = datetime.now()
    last_redeem = user_last_redeem.get(user_id)

    # If the user has never redeemed or it has been more than 1 hour since last redeem
    if last_redeem is None or (now - last_redeem).total_seconds() >= 3600:
        return True
    return False

# Command to redeem coins with a valid redeem code
@bot.message_handler(commands=['redeem'])
def redeem_coins(message):
    global current_redeem_code, redeem_code_expiry
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Check if a redeem code is active
    if current_redeem_code is None or redeem_code_expiry is None or datetime.now() > redeem_code_expiry:
        bot.reply_to(message, "⏳ There is no active redeem code or it has expired.")
        return

    # Get the redeem code the user is trying to redeem
    redeem_attempt = message.text.strip().split(" ")

    # Check if the redeem command includes the correct code
    if len(redeem_attempt) == 2 and redeem_attempt[1] == current_redeem_code:
        # Check if the user can redeem again (only once per hour)
        if can_redeem(user_id):
            # Award coins
            user_last_redeem[user_id] = datetime.now()  # Record the redeem time
            bot.reply_to(message, f"🎉 You have successfully redeemed the code and earned {COINS_PER_REDEEM} coins!")
        else:
            # Calculate the remaining time until the next redeem is available
            remaining_time = timedelta(hours=1) - (datetime.now() - user_last_redeem[user_id])
            minutes_left = remaining_time.seconds // 60
            bot.reply_to(message, f"⏳ You have already redeemed the code. Please wait {minutes_left} minutes before redeeming again.")
    else:
        bot.reply_to(message, "❌ Invalid redeem code. Please try again.")

# Function to check if a user can claim the daily bonus
def can_claim_bonus(user_id):
    now = datetime.now()
    last_bonus = user_last_bonus.get(user_id)

    # If the user has never claimed the bonus or it has been more than 24 hours since last claim
    if last_bonus is None or (now - last_bonus).days >= 1:
        return True
    return False

# /bonus command - Claim daily reward once every 24 hours
@bot.message_handler(commands=['bonus'])
def claim_bonus(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Check if the user can claim the bonus (once per 24 hours)
    if can_claim_bonus(user_id):
        # Award daily bonus coins
        user_last_bonus[user_id] = datetime.now()  # Record the claim time
        bot.reply_to(message, f"🎁 {username}, you have claimed your daily bonus and received {COINS_PER_BONUS} coins!")
    else:
        # Calculate the remaining time until they can claim again
        remaining_time = timedelta(days=1) - (datetime.now() - user_last_bonus[user_id])
        hours_left = remaining_time.seconds // 3600
        minutes_left = (remaining_time.seconds % 3600) // 60
        bot.reply_to(message, f"⏳ You have already claimed your daily bonus. You can claim again in {hours_left} hours and {minutes_left} minutes.")

# Function to reset the game state and send a new character image
def send_new_character(chat_id):
    global current_game_state
    image_url, character_name = fetch_zerochan_image()

    if image_url and character_name:
        # Reset attempts for each user when a new character is shown
        current_game_state["user_attempts"] = {}
        current_game_state["image_url"] = image_url
        current_game_state["character_name"] = character_name.lower()  # Store character name in lowercase for easy comparison
        
        # Send the new image to the chat
        bot.send_photo(chat_id, image_url, caption="🎨 Guess the name of this anime character!")
    else:
        # Error handling if the image couldn't be fetched
        bot.send_message(chat_id, "⚠️ Sending characters in some time, please wait...")

# Function to handle guesses
@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    global current_game_state
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_guess = message.text.strip().lower()

    # Check if there's an active image for guessing
    if current_game_state["image_url"] and current_game_state["character_name"]:
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

# /help command - Lists all available commands
@bot.message_handler(commands=['help'])
def show_help(message):
    help_message = """
    🤖 Available Commands:
    
    /start - Start the game
    /help - Show this help message
    /redeem <code> - Redeem a valid code for coins
    /bonus - Claim your daily reward (available every 24 hours)
    🎮 Guess the name of anime characters from images!
    """
    bot.reply_to(message, help_message)

# Start Command - Begins by sending the first character image
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Try to guess the character's name.")
    send_new_character(message.chat.id)

# Start the redeem code generation in a separate thread
threading.Thread(target=generate_redeem_code, daemon=True).start()

# Start polling the bot
bot.infinity_polling()
        
