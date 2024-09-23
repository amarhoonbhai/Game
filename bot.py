import telebot
import requests
import random
import sqlite3
from datetime import datetime, timedelta

# Initialize Telegram Bot
API_TOKEN = "YOUR_TELEGRAM_BOT_API_TOKEN7831268505:AAF8ZvnYx3RCTpXpRYkLFngUwICIZvYDQjw"  # Replace this with your actual Telegram bot API token
bot = telebot.TeleBot(API_TOKEN)

# SQLite Database setup
conn = sqlite3.connect('game_data.db', check_same_thread=False)
c = conn.cursor()

# Create table for storing player data if it doesn't exist
c.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    last_daily TEXT,
    correct_guesses INTEGER DEFAULT 0
)
''')

# Commit the changes to the database
conn.commit()

# Helper function to fetch player data from the database
def get_player_data(user_id):
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = c.fetchone()
    if not player:
        # Insert a new player record if not found
        c.execute('INSERT INTO players (user_id, coins, last_daily, correct_guesses) VALUES (?, 0, NULL, 0)', (user_id,))
        conn.commit()
        return (user_id, 0, None, 0)
    return player

# Helper function to update player data
def update_player_data(user_id, coins=None, last_daily=None, correct_guesses=None):
    current_data = get_player_data(user_id)
    new_coins = coins if coins is not None else current_data[1]
    new_last_daily = last_daily if last_daily is not None else current_data[2]
    new_correct_guesses = correct_guesses if correct_guesses is not None else current_data[3]
    c.execute('UPDATE players SET coins = ?, last_daily = ?, correct_guesses = ? WHERE user_id = ?',
              (new_coins, new_last_daily, new_correct_guesses, user_id))
    conn.commit()

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
    variables = {'page': 1, 'perPage': 100}
    response = requests.post(url, json={'query': query, 'variables': variables})
    data = response.json()
    characters = data['data']['Page']['characters']
    return random.choice(characters)

# Start Game Command
@bot.message_handler(commands=['start_game'])
def start_game(message):
    character = fetch_random_anime_character()
    bot.current_character = character['name']['full'].lower()
    bot.current_hint = character['media'][0]['title']['english'] if 'english' in character['media'][0]['title'] else character['media'][0]['title']['romaji']
    bot.reply_to(message, f"Guess the anime character! Hint: This character is from {bot.current_hint}.")

# Guess Command
@bot.message_handler(commands=['guess'])
def guess(message):
    guess_text = message.text[len("/guess "):].lower()
    user_id = message.from_user.id
    player = get_player_data(user_id)
    
    if guess_text == bot.current_character:
        new_coins = player[1] + 10  # Add 10 coins for correct guess
        new_correct_guesses = player[3] + 1
        update_player_data(user_id, coins=new_coins, correct_guesses=new_correct_guesses)
        bot.reply_to(message, f"Correct! You've earned 10 coins. You now have {new_coins} coins.")
    else:
        bot.reply_to(message, f"Wrong guess! Try again.")

# Daily Claim Command
@bot.message_handler(commands=['daily_claim'])
def daily_claim(message):
    user_id = message.from_user.id
    player = get_player_data(user_id)
    now = datetime.now()
    
    last_claim = player[2]
    if last_claim is None or now - datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S.%f") > timedelta(days=1):
        new_coins = player[1] + 50  # Add 50 daily reward coins
        update_player_data(user_id, coins=new_coins, last_daily=now)
        bot.reply_to(message, f"Daily reward claimed! You now have {new_coins} coins.")
    else:
        bot.reply_to(message, "You can only claim your daily reward once every 24 hours.")

# Balance Command
@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    player = get_player_data(user_id)
    bot.reply_to(message, f"You have {player[1]} coins.")

# Leaderboard Command
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    c.execute('SELECT user_id, coins FROM players ORDER BY coins DESC LIMIT 10')
    leaderboard_data = c.fetchall()
    
    leaderboard_message = "Leaderboard:\n"
    for rank, player_data in enumerate(leaderboard_data, start=1):
        user_id, coins = player_data
        user = bot.get_chat(user_id)
        leaderboard_message += f"{rank}. {user.username if user.username else user.first_name}: {coins} coins\n"
    
    bot.reply_to(message, leaderboard_message)

# Run the bot
bot.infinity_polling()

