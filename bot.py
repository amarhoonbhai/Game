import telebot
import requests
import random
import sqlite3
from datetime import datetime, timedelta
import logging

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Initialize Telegram Bot
API_TOKEN = "7831268505:AAE6x1WHPJ-70AN-U6G4KXjwpe6rCdATJlg"  # Replace with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# Function to fetch random anime characters from AniList API
def fetch_random_anime_character():
    url = 'https://graphql.anilist.co'
    query = '''
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        characters {
          name {
            full
          }
          media {
            nodes {
              title {
                english
                romaji
              }
            }
          }
        }
      }
    }
    '''
    variables = {'page': random.randint(1, 50), 'perPage': 1}  # Fetch random page of characters
    try:
        response = requests.post(url, json={'query': query, 'variables': variables})
        response.raise_for_status()
        data = response.json()
        characters = data['data']['Page']['characters']
        if len(characters) > 0:
            return characters[0]  # Return the first character from the random page
        else:
            raise Exception("No characters found")
    except requests.RequestException as e:
        print(f"Error fetching character from AniList: {e}")
        return None

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the Anime Character Guessing Game! Use /start_game to begin guessing characters.")

# Start Game Command - Sends a Random Anime Character
@bot.message_handler(commands=['start_game'])
def start_game(message):
    character = fetch_random_anime_character()
    if character is None:
        bot.reply_to(message, "Sorry, I couldn't fetch a character right now. Try again later.")
    else:
        character_name = character['name']['full']
        anime_title = character['media'][0]['title']['english'] if 'english' in character['media'][0]['title'] else character['media'][0]['title']['romaji']
        bot.current_character = character_name.lower()
        bot.current_hint = anime_title
        bot.reply_to(message, f"Guess the anime character! Hint: This character is from {bot.current_hint}.")

# Guess Command - Validate the Guess and Send the Next Character Automatically
@bot.message_handler(commands=['guess'])
def guess(message):
    guess_text = message.text[len("/guess "):].lower()
    user_id = message.from_user.id

    if guess_text == bot.current_character:
        # Correct guess, send a new character
        bot.reply_to(message, f"Correct! The character was {bot.current_character.capitalize()}. Here's the next one:")
        
        # Fetch a new character automatically
        character = fetch_random_anime_character()
        if character is None:
            bot.reply_to(message, "Sorry, I couldn't fetch a new character right now. Try again later.")
        else:
            character_name = character['name']['full']
            anime_title = character['media'][0]['title']['english'] if 'english' in character['media'][0]['title'] else character['media'][0]['title']['romaji']
            bot.current_character = character_name.lower()
            bot.current_hint = anime_title
            bot.reply_to(message, f"Guess the anime character! Hint: This character is from {bot.current_hint}.")
    else:
        # Wrong guess
        bot.reply_to(message, f"Wrong guess! Try again.")

# Run the bot
bot.infinity_polling()
