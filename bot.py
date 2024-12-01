import os
import random
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging

# Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID"))
MESSAGE_THRESHOLD = int(os.getenv("MESSAGE_THRESHOLD", 5))
CHARACTER_CHANNEL_ID = os.getenv("CHARACTER_CHANNEL_ID")

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client["telegram_bot"]
    characters_collection = db["characters"]
    users_collection = db["users"]
    sudo_users_collection = db["sudo_users"]
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    exit()

# Globals
message_count = {}
current_characters = {}

# Define rarity with emojis
RARITY_EMOJIS = {
    "Common": "◈ 🌱 Common",
    "Elite": "◈ ✨ Elite",
    "Rare": "◈ 🌟 Rare",
    "Legendary": "◈ 🔥 Legendary",
}


# Check if the user is authorized (owner or sudo)
def is_authorized(user_id):
    """Check if the user is the owner or a sudo user."""
    return user_id == OWNER_ID or sudo_users_collection.find_one({"user_id": user_id})


# Fetch a random character
def fetch_random_character():
    """Fetch a random character from MongoDB."""
    character = characters_collection.aggregate([{"$sample": {"size": 1}}]).next()
    return character


# Send a character to the chat
async def send_character(update: Update, user_id: int):
    """Send a random character from the database to the chat."""
    character = fetch_random_character()
    rarity_emoji = RARITY_EMOJIS.get(character["rarity"], "❓")
    current_characters[user_id] = character["name"].lower()

    await update.message.reply_photo(
        photo=character["image_url"],
        caption=(
            f"🎉 **Time for a Challenge!**\n\n"
            f"🌟 **Character Rarity:** {rarity_emoji}\n"
            f"🧩 **Clue:** The name begins with **'{character['name'][0].upper()}'**.\n\n"
            f"🤔 **Can you guess who it is?**\n\n"
            f"🎯 Guess correctly and earn **1000 coins!**"
        ),
    )
    logging.info(f"Character '{character['name']}' sent to user {user_id}.")


# /upload Command
async def upload(update: Update, context: CallbackContext):
    """Handle the /upload command."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 3:
        await update.message.reply_text("⚠️ Usage: /upload <image_url> <character_name> <rarity>")
        return

    image_url = context.args[0]
    character_name = context.args[1]
    rarity = context.args[2].capitalize()

    if rarity not in RARITY_EMOJIS:
        await update.message.reply_text(
            "❌ Invalid rarity. Valid options are: Common, Elite, Rare, Legendary."
        )
        return

    if not characters_collection.find_one({"name": character_name.lower()}):
        characters_collection.insert_one({
            "name": character_name.lower(),
            "rarity": rarity,
            "image_url": image_url,
        })
        await update.message.reply_text(
            f"✅ **Character Uploaded!**\n"
            f"🧩 **Name:** {character_name}\n"
            f"🌟 **Rarity:** {RARITY_EMOJIS[rarity]}"
        )
        logging.info(f"Character '{character_name}' uploaded by user {user_id}.")
    else:
        await update.message.reply_text("⚠️ This character already exists in the database.")


# /addsudo Command
async def addsudo(update: Update, context: CallbackContext):
    """Add a sudo user."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: /addsudo <user_id>")
        return

    sudo_user_id = int(context.args[0])
    if sudo_users_collection.find_one({"user_id": sudo_user_id}):
        await update.message.reply_text("⚠️ This user is already a sudo user.")
    else:
        sudo_users_collection.insert_one({"user_id": sudo_user_id})
        await update.message.reply_text(f"✅ User {sudo_user_id} has been added as a sudo user.")


# /rmsudo Command
async def rmsudo(update: Update, context: CallbackContext):
    """Remove a sudo user."""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: /rmsudo <user_id>")
        return

    sudo_user_id = int(context.args[0])
    if sudo_users_collection.delete_one({"user_id": sudo_user_id}).deleted_count > 0:
        await update.message.reply_text(f"✅ User {sudo_user_id} has been removed as a sudo user.")
    else:
        await update.message.reply_text("⚠️ This user is not a sudo user.")


# /stats Command
async def stats(update: Update, context: CallbackContext):
    """Show bot statistics."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    common_characters = characters_collection.count_documents({"rarity": "Common"})
    elite_characters = characters_collection.count_documents({"rarity": "Elite"})
    rare_characters = characters_collection.count_documents({"rarity": "Rare"})
    legendary_characters = characters_collection.count_documents({"rarity": "Legendary"})

    await update.message.reply_text(
        f"📊 **Bot Statistics:**\n"
        f"👥 **Total Users:** {total_users}\n"
        f"🧩 **Total Characters:** {total_characters}\n"
        f"🌱 **Common Characters:** {common_characters}\n"
        f"✨ **Elite Characters:** {elite_characters}\n"
        f"🌟 **Rare Characters:** {rare_characters}\n"
        f"🔥 **Legendary Characters:** {legendary_characters}"
    )


# Main function to run the bot
async def main():
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("upload", upload))
    application.add_handler(CommandHandler("addsudo", addsudo))
    application.add_handler(CommandHandler("rmsudo", rmsudo))
    application.add_handler(CommandHandler("stats", stats))

    await application.run_polling()


# Keep the bot running indefinitely
if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            logging.error(f"Error occurred: {e}. Restarting bot...")
            
