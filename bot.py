import random
import requests
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionError
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID"))

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client["philo_guesser"]
    users_collection = db["users"]
    characters_collection = db["characters"]
    sudo_users_collection = db["sudo_users"]
    print("✅ MongoDB connected successfully!")
except ConnectionError as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

# Bot setup
app = Client("philo_guesser_bot", bot_token=BOT_TOKEN)

# Rarity Levels with Bonuses
rarity_levels = {
    "Common": {"emoji": "🌱", "bonus": 10},
    "Uncommon": {"emoji": "🌟", "bonus": 20},
    "Rare": {"emoji": "🔮", "bonus": 30},
    "Legendary": {"emoji": "🐉", "bonus": 50},
}

MESSAGE_THRESHOLD = 5  # Set the message threshold to 5


# Helper Functions
def add_user(user_id, full_name):
    """Add a user to the database if they don't already exist."""
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id, "full_name": full_name, "coins": 0, "level": 1, "messages": 0})


def calculate_level(coins):
    """Calculate user level based on coins."""
    return coins // 100 + 1


def get_level_tag(level):
    """Get a tag for the user's level."""
    if level >= 1000:
        return "🔥 Over Power 🔥"
    elif 500 <= level < 1000:
        return "⚡ Elite ⚡"
    elif 100 <= level < 500:
        return "💎 Pro 💎"
    elif 50 <= level < 100:
        return "🌟 Rising Star 🌟"
    elif 10 <= level < 50:
        return "🌿 Beginner 🌿"
    else:
        return "🌱 Newbie 🌱"


def is_owner_or_sudo(user_id):
    """Check if the user is the owner or a sudo user."""
    return user_id == OWNER_ID or sudo_users_collection.find_one({"_id": user_id}) is not None


@app.on_message(filters.command("start"))
async def start_command(_, message: Message):
    """Handle the /start command."""
    user_full_name = message.from_user.full_name
    add_user(message.from_user.id, user_full_name)
    await message.reply_text(
        f"👋 **Welcome to Philo Guesser, {user_full_name}!**\n\n"
        "🎮 **How to Play:**\n"
        "- Guess anime characters by typing any part of their name.\n"
        "- Earn coins based on the character's rarity.\n\n"
        "⭐ **Commands:**\n"
        "`/help` - View detailed instructions.\n"
        "`/levels` - See the leaderboard.\n"
        "`/profile` - View your profile.\n\n"
        "Start guessing and become the ultimate Philo Guesser!"
    )


@app.on_message(filters.command("help"))
async def help_command(_, message: Message):
    """Handle the /help command."""
    await message.reply_text(
        "📚 **Philo Guesser Help:**\n\n"
        "🎮 **How to Play:**\n"
        "1. A random character will appear every 5 messages or after a correct guess.\n"
        "2. Guess the character's name by typing any part of it.\n"
        "3. Earn coins based on the character's rarity:\n"
        "   - 🌱 Common: 10 coins\n"
        "   - 🌟 Uncommon: 20 coins\n"
        "   - 🔮 Rare: 30 coins\n"
        "   - 🐉 Legendary: 50 coins\n\n"
        "⭐ **Commands:**\n"
        "`/start` - Start the bot and see the welcome message.\n"
        "`/levels` - Check the leaderboard.\n"
        "`/profile` - View your profile with stats.\n"
        "`/upload <image_url> <character_name> <rarity>` - Add a character (Owner/Sudo Only).\n"
        "`/addsudo <user_id>` - Add a sudo user (Owner Only).\n\n"
        "✨ **Tip:** Level up to unlock exclusive tags like '⚡ Elite ⚡' and '🔥 Over Power 🔥'!"
    )


@app.on_message(filters.command("profile"))
async def profile_command(_, message: Message):
    """Handle the /profile command."""
    user_id = message.from_user.id
    user_full_name = message.from_user.full_name
    add_user(user_id, user_full_name)

    user = users_collection.find_one({"_id": user_id})
    level = calculate_level(user["coins"])
    tag = get_level_tag(level)
    next_level = (level * 100) - user["coins"]

    await message.reply_text(
        f"👤 **Profile for {user_full_name}:**\n\n"
        f"💬 **Messages Sent:** {user['messages']}\n"
        f"💰 **Coins:** {user['coins']} 🪙\n"
        f"⭐ **Level:** {level} ({tag})\n"
        f"🎯 **Coins to Next Level:** {next_level} 🪙"
    )


@app.on_message(filters.command("levels"))
async def levels_command(_, message: Message):
    """Handle the /levels command."""
    users = list(users_collection.find().sort("coins", -1))
    leaderboard = []
    for i, user in enumerate(users[:10]):
        badge = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
        tag = get_level_tag(calculate_level(user["coins"]))
        leaderboard.append(
            f"{badge} {user['full_name']} - {user['coins']} 🪙 (Level {calculate_level(user['coins'])}, {tag})"
        )
    await message.reply_text(f"🏆 **Leaderboard:**\n\n" + "\n".join(leaderboard))


@app.on_message(filters.text & ~filters.command)
async def handle_guess(_, message: Message):
    """Handle guesses and messages."""
    user_id = message.from_user.id
    user_full_name = message.from_user.full_name
    add_user(user_id, user_full_name)

    user = users_collection.find_one({"_id": user_id})
    users_collection.update_one({"_id": user_id}, {"$inc": {"messages": 1}})
    messages_sent = user["messages"] + 1

    # Check guess using substring matching
    character = characters_collection.find_one({"name": {"$regex": f"{message.text.strip()}", "$options": "i"}})
    if character:
        rarity = character["rarity"]
        coins_earned = rarity_levels[rarity]["bonus"]
        users_collection.update_one({"_id": user_id}, {"$inc": {"coins": coins_earned}})
        await message.reply_text(
            f"✅ **Correct!** 🎉 You earned {coins_earned} 🪙!\n💰 **Total Coins:** {user['coins'] + coins_earned} 🪙."
        )

        # Fetch and display the next random character
        next_character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
        await message.reply_photo(
            next_character["image_url"],
            caption=f"🧩 **Guess the next character!**\n🎲 **Rarity:** {rarity_levels[next_character['rarity']]['emoji']} {next_character['rarity']}"
        )
        return

    # Display character after MESSAGE_THRESHOLD messages
    if messages_sent % MESSAGE_THRESHOLD == 0:
        random_character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
        await message.reply_photo(
            random_character["image_url"],
            caption=f"🧩 **Can you guess who this is?**\n🎲 **Rarity:** {rarity_levels[random_character['rarity']]['emoji']} {random_character['rarity']}"
        )


if __name__ == "__main__":
    print("Starting Philo Guesser Bot...")
    app.start()
    idle()
    app.stop()
    print("Philo Guesser Bot stopped.")
