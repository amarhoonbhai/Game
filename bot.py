import telebot
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Replace with your actual bot API token, owner ID, and Telegram channel ID
API_TOKEN = "7740301929:AAG5bo2eBKUShTNHze_xngf21bx9u9WiVWk"
BOT_OWNER_ID = 7222795580  # Replace with your Telegram user ID (owner's ID)
CHANNEL_ID = -1001234567890  # Replace with your Telegram channel ID where characters are logged

# Initialize Telegram Bot
bot = telebot.TeleBot(API_TOKEN)

# In-memory store for redeem codes, characters, and game data
user_last_claim = {}  # Track the last time each user claimed daily reward
user_daily_streaks = defaultdict(int)  # Track daily login streaks
user_coins = defaultdict(int)  # Track each user's coin balance
user_profiles = {}  # Store user profiles (username or first_name)
user_chat_ids = set()  # Track user chat IDs for redeem code distribution
user_correct_guesses = defaultdict(int)  # Track total correct guesses
user_streaks = defaultdict(int)  # Track correct guess streaks
user_inventory = defaultdict(list)  # Users' collected characters
characters = []  # List of all uploaded characters
current_character = None
auctions = {}  # Track ongoing character auctions
auction_id_counter = 1  # Track auction IDs
pvp_challenges = {}  # Store active PvP challenges

DAILY_REWARD_COINS = 10000  # Coins given as a daily reward
COINS_PER_GUESS = 50  # Coins awarded for correct guesses
RARITY_LEVELS = {
    'Common': '⭐',
    'Rare': '🌟',
    'Epic': '💫',
    'Legendary': '✨'
}
RARITY_WEIGHTS = [60, 25, 10, 5]  # Probabilities for selecting rarity (in percentage)

### Helper Functions ###
def add_coins(user_id, coins):
    user_coins[user_id] += coins
    print(f"User {user_id} awarded {coins} coins. Total: {user_coins[user_id]}")

def deduct_coins(user_id, coins):
    if user_coins[user_id] >= coins:
        user_coins[user_id] -= coins
        return True
    return False

def is_admin_or_owner(message):
    """ Check if the user is the bot owner or an admin. """
    if message.from_user.id == BOT_OWNER_ID:
        return True
    try:
        chat_admins = bot.get_chat_administrators(message.chat.id)
        return message.from_user.id in [admin.user.id for admin in chat_admins]
    except Exception:
        return False

def assign_rarity():
    """ Automatically assign rarity based on weighted probability. """
    return random.choices(list(RARITY_LEVELS.keys()), weights=RARITY_WEIGHTS, k=1)[0]

### Command Handlers ###

# /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_profiles[user_id] = message.from_user.username or message.from_user.first_name
    user_chat_ids.add(chat_id)

    welcome_message = """
━━━━━━━━━━━━━━━━━━━━━━
**🎉 Welcome to Philo Grabber!**

🔮 **Philo Grabber** is the ultimate Anime Character Guessing Game! Collect, trade, and guess characters to climb the leaderboards.

✨ **Features**:
- Daily rewards & streaks
- Character collection & trading
- PvP challenges, auctions, and much more!

Type /help to see the full list of commands!
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, welcome_message, parse_mode='Markdown')

# /upload command - Allows the owner and admins to upload new characters
@bot.message_handler(commands=['upload'])
def upload_character(message):
    if not is_admin_or_owner(message):
        bot.reply_to(message, "❌ You do not have permission to use this command.")
        return

    try:
        _, image_url, character_name = message.text.split(maxsplit=2)
    except ValueError:
        bot.reply_to(message, "⚠️ Incorrect format. Use: /upload <image_url> <character_name>")
        return

    rarity = assign_rarity()
    character_id = len(characters) + 1
    character = {
        'id': character_id,
        'image_url': image_url.strip(),
        'character_name': character_name.strip(),
        'rarity': rarity
    }
    characters.append(character)

    caption = (f"📥 **New Character Uploaded**:\n\n"
               f"💬 **Name**: {character_name}\n"
               f"⚔️ **Rarity**: {RARITY_LEVELS[rarity]} {rarity}\n"
               f"🔗 **Image URL**: {image_url}\n"
               f"🆔 **ID**: {character_id}")
    bot.send_photo(CHANNEL_ID, image_url, caption=caption, parse_mode='Markdown')
    bot.reply_to(message, f"✅ Character '{character_name}' uploaded successfully!")

### Auctions ###

# /auction command - Start an auction for a character
@bot.message_handler(commands=['auction'])
def start_auction(message):
    global auction_id_counter
    try:
        _, character_id, starting_bid = message.text.split(maxsplit=2)
        character_id = int(character_id)
        starting_bid = int(starting_bid)
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Incorrect format. Use: /auction <character_id> <starting_bid>")
        return

    user_id = message.from_user.id
    character = next((c for c in user_inventory[user_id] if c['id'] == character_id), None)
    if not character:
        bot.reply_to(message, "❌ You don't own a character with that ID.")
        return

    auction_id = auction_id_counter
    auctions[auction_id] = {
        'owner': user_id,
        'character': character,
        'current_bid': starting_bid,
        'highest_bidder': None
    }
    auction_id_counter += 1

    bot.reply_to(message, f"🎉 Auction started for **{character['character_name']}** with a starting bid of **{starting_bid}** coins!\nAuction ID: {auction_id}")

# /bid command - Place a bid on an auction
@bot.message_handler(commands=['bid'])
def place_bid(message):
    try:
        _, auction_id, bid_amount = message.text.split(maxsplit=2)
        auction_id = int(auction_id)
        bid_amount = int(bid_amount)
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Incorrect format. Use: /bid <auction_id> <bid_amount>")
        return

    user_id = message.from_user.id
    auction = auctions.get(auction_id)

    if not auction:
        bot.reply_to(message, "❌ Auction not found.")
        return

    if bid_amount <= auction['current_bid']:
        bot.reply_to(message, f"⚠️ Your bid must be higher than the current bid of **{auction['current_bid']}** coins.")
        return

    if not deduct_coins(user_id, bid_amount):
        bot.reply_to(message, "❌ You don't have enough coins to place this bid.")
        return

    if auction['highest_bidder']:
        add_coins(auction['highest_bidder'], auction['current_bid'])  # Refund the previous highest bidder

    auction['current_bid'] = bid_amount
    auction['highest_bidder'] = user_id

    bot.reply_to(message, f"🎉 You are the highest bidder for **{auction['character']['character_name']}** with **{bid_amount}** coins!")

# /endauction command - Ends an auction and awards the character to the highest bidder
@bot.message_handler(commands=['endauction'])
def end_auction(message):
    try:
        _, auction_id = message.text.split(maxsplit=1)
        auction_id = int(auction_id)
    except (ValueError, IndexError):
        bot.reply_to(message, "⚠️ Incorrect format. Use: /endauction <auction_id>")
        return

    auction = auctions.get(auction_id)
    if not auction:
        bot.reply_to(message, "❌ Auction not found.")
        return

    owner_id = message.from_user.id
    if auction['owner'] != owner_id:
        bot.reply_to(message, "❌ You are not the owner of this auction.")
        return

    if auction['highest_bidder']:
        # Transfer character to highest bidder
        user_inventory[auction['highest_bidder']].append(auction['character'])
        bot.reply_to(message, f"🎉 Auction ended! {auction['character']['character_name']} goes to the highest bidder!")

        # Remove character from the owner's inventory
        user_inventory[owner_id].remove(auction['character'])

        del auctions[auction_id]  # Delete the auction
    else:
        bot.reply_to(message, "⚠️ No bids were placed for this auction.")
