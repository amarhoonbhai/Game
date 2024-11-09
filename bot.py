import random
from pymongo import MongoClient
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Replace with your actual MongoDB connection URI
MONGO_URI = "mongodb+srv://PhiloWise:Philo@waifu.yl9tohm.mongodb.net/?retryWrites=true&w=majority&appName=Waifu"
DATABASE_NAME = "anime_game"
CHARACTERS_COLLECTION = "characters"
USERS_COLLECTION = "users"

# Replace with your bot's token, owner ID, and admin user IDs
TOKEN = "6862816736:AAESEgL9fpLJIGwaRo0ACif0NbSZocRoBok"
OWNER_ID = 7222795580  # Updated Bot Owner ID
ADMIN_IDS = [OWNER_ID, 987654321]  # Add additional admin user IDs if necessary

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
characters_collection = db[CHARACTERS_COLLECTION]
users_collection = db[USERS_COLLECTION]

# Rarity mapping with emojis
RARITY_EMOJIS = {
    "bronze": "🥉",
    "silver": "🥈",
    "gold": "🥇",
    "platinum": "💿",
    "diamond": "💎"
}

# Game state variable
current_character = None

# Dynamic celebratory messages
CELEBRATORY_MESSAGES = [
    "🎉 Awesome! You got it right! 🎉",
    "👏 Well done! That's correct! 👏",
    "🔥 You're on fire! That's the correct answer! 🔥",
    "🎊 Brilliant! You nailed it! 🎊",
    "🥳 Great job! You guessed it! 🥳",
]

# Function to post a new character from the database to the chat
def post_random_character(context: CallbackContext):
    global current_character
    chat_id = context.job.context

    # Fetch a random character from the database
    characters = list(characters_collection.find())
    if not characters:
        context.bot.send_message(chat_id=chat_id, text="⚠️ No characters available for guessing. Please add some characters using /upload.")
        return

    current_character = random.choice(characters)

    # Post the character's appearance prompt
    context.bot.send_message(chat_id=chat_id, text="✨ A new character has appeared! Can you guess who it is? 🤔")

# Start the bot with a welcome message
def start(update: Update, context: CallbackContext) -> None:
    welcome_message = "👋 Welcome To Pʜɪʟᴏ 🝮︎︎︎︎︎︎︎ Gʀᴀʙʙᴇʀ!\n" \
                      "Let's play a guessing game! Try to guess the anime character! 🎉"
    update.message.reply_text(welcome_message)
    start_new_round(update)

    # Start the recurring job to post random characters
    job_queue = context.job_queue
    job_queue.run_repeating(post_random_character, interval=300, first=10, context=update.message.chat_id)

# Function to start a new round of guessing
def start_new_round(update: Update):
    global current_character
    characters = list(characters_collection.find())

    if not characters:
        update.message.reply_text("⚠️ No characters available for guessing. Please add some characters using /upload.")
        return

    current_character = random.choice(characters)
    update.message.reply_text("✨ A new character has appeared! Can you guess who it is? 🤔")

# Help command to show instructions
def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
    🆘 *Help Menu* 🆘

    ⍟ Just type your guess to participate in the game! 🧩
    ⍟ If your guess is correct, the bot will automatically give a new character and your level will increase. 📈
    ⍟ /start - Start the bot and begin character posting 🚀
    ⍟ /help - Show this help message 📋
    ⍟ /upload [image_url] [character_name] [rarity (bronze/silver/gold/platinum/diamond)] - Add a new character (admin only) 👤
    ⍟ /stats - (Owner only) View all user levels 📊
    ⍟ /leaderboard - View the top players by level 🏆
    ⍟ /profile - View your current level and rank 🧍‍♂️
    """
    update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Admin-only command to upload a new character
def upload(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 You don't have permission to use this command.")
        return

    if len(context.args) < 3:
        update.message.reply_text("⚙️ Usage: /upload [image_url] [character_name] [rarity (bronze/silver/gold/platinum/diamond)]")
        return

    # Parse character details from the command
    image_url = context.args[0]
    rarity = context.args[-1].lower()
    character_name = " ".join(context.args[1:-1])

    # Validate rarity
    if rarity not in RARITY_EMOJIS:
        update.message.reply_text("❗ Invalid rarity. Rarity must be one of: bronze, silver, gold, platinum, diamond.")
        return

    # Insert new character into MongoDB
    character_data = {
        "name": character_name,
        "image_url": image_url,
        "rarity": rarity
    }
    characters_collection.insert_one(character_data)

    emoji = RARITY_EMOJIS[rarity]
    update.message.reply_text(f"✅ Character '{character_name}' with rarity {emoji} {rarity.capitalize()} has been added successfully.")

# Guess handling function with leveling up for correct guess
def handle_guess(update: Update, context: CallbackContext) -> None:
    global current_character

    if not current_character:
        update.message.reply_text("⚠️ No character is available for guessing. Please wait for new characters.")
        return

    guess = update.message.text.strip()
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Detect if the guess is correct by comparing to the character's name
    if guess.lower() == current_character['name'].lower():
        # Increment user's level
        user = users_collection.find_one({"user_id": user_id})
        if user:
            users_collection.update_one({"user_id": user_id}, {"$inc": {"level": 1}})
            new_level = user["level"] + 1
        else:
            users_collection.insert_one({"user_id": user_id, "username": username, "level": 1})
            new_level = 1

        # Choose a random celebratory message
        celebratory_message = random.choice(CELEBRATORY_MESSAGES)
        emoji = RARITY_EMOJIS[current_character['rarity']]
        update.message.reply_photo(
            current_character['image_url'],
            caption=f"{celebratory_message}\n\nThe character was *{current_character['name']}* - {emoji} {current_character['rarity'].capitalize()}\n⭐️ *Your level is now {new_level}!* ⭐️",
            parse_mode=ParseMode.MARKDOWN
        )
        start_new_round(update)  # Move to the next character

# Profile command to view user's current level and rank with an inline button
def profile(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Fetch user profile information
    user = users_collection.find_one({"user_id": user_id})
    if user:
        # Calculate user's rank based on level
        rank = users_collection.count_documents({"level": {"$gt": user["level"]}}) + 1
        profile_message = f"🧍 *Profile for @{username}*\n\n🏅 *Level:* {user['level']}\n🎖️ *Rank:* #{rank}"
    else:
        profile_message = "🚫 You don't have a profile yet. Start guessing characters to level up!"

    # Inline button linking to developer's profile
    keyboard = [
        [InlineKeyboardButton("Developer - @TechPiro", url="https://t.me/TechPiro")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(profile_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# Leaderboard command to view top players
def leaderboard(update: Update, context: CallbackContext) -> None:
    # Fetch top 5 users by level from the database
    top_users = users_collection.find().sort("level", -1).limit(5)
    leaderboard_message = "🏆 *Leaderboard - Top Players* 🏆\n\n"
    rank = 1
    for user in top_users:
        leaderboard_message += f"{rank}. @{user['username']} - Level {user['level']} 🌟\n"
        rank += 1

    update.message.reply_text(leaderboard_message, parse_mode=ParseMode.MARKDOWN)

# Main function to start the bot
def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("upload", upload))  # Admin-only command for uploading characters
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))  # Command to view leaderboard
    dispatcher.add_handler(CommandHandler("profile", profile))  # Command to view user's profile
    dispatcher.add_handler(CommandHandler("stats", stats))    # Owner-only command for stats

    # Handler for guesses
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_guess))

    # Start polling for updates
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
