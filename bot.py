import os
import random
import logging
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944  # Replace with your channel ID

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
groups_collection = db["groups"]  # New collection to store group chat info
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# Enhanced rarities with probabilities
RARITIES = [
    ("Common 🌱", 60),
    ("Uncommon 🌿", 20),
    ("Rare 🌟", 10),
    ("Epic 🌠", 5),
    ("Legendary 🏆", 3),
    ("Mythical 🔥", 2),
]

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Game state
character_cache = []
current_character = None
user_message_count = Counter()


class Game:
    """Encapsulates game logic and utility methods."""

    @staticmethod
    def assign_rarity():
        """Assign rarity based on predefined probabilities."""
        total_weight = sum(weight for _, weight in RARITIES)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in RARITIES:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "Common 🌱"  # Default fallback

    @staticmethod
    def fetch_random_character():
        """Fetch a random character, using cache if available."""
        global character_cache
        if not character_cache:
            character_cache = list(characters_collection.aggregate([{"$sample": {"size": 10}}]))
        return character_cache.pop() if character_cache else None

    @staticmethod
    def update_user_balance_and_streak(user_id, first_name, last_name, correct_guess):
        """Update user balance and streak in the database."""
        user = users_collection.find_one({"user_id": user_id})
        if user:
            if correct_guess:
                new_streak = user.get("streak", 0) + 1
                balance_increment = 10 + (new_streak * 2)  # Bonus for streak
                users_collection.update_one(
                    {"user_id": user_id},
                    {"$inc": {"balance": balance_increment}, "$set": {"streak": new_streak}},
                )
                return balance_increment, new_streak
            else:
                users_collection.update_one({"user_id": user_id}, {"$set": {"streak": 0}})
                return 0, 0
        else:
            users_collection.insert_one(
                {"user_id": user_id, "first_name": first_name, "last_name": last_name, "balance": 0, "streak": 0}
            )
            return 0, 0

    @staticmethod
    def get_user_currency():
        """Get leaderboard for currency."""
        return list(users_collection.find().sort("balance", -1).limit(10))

    @staticmethod
    def is_owner(user_id):
        """Check if the user is the owner."""
        return user_id == OWNER_ID

    @staticmethod
    def add_sudo_user(user_id):
        """Add a user as sudo."""
        sudo_users_collection.insert_one({"user_id": user_id})

    @staticmethod
    def get_bot_stats():
        """Get bot statistics."""
        total_users = users_collection.count_documents({})
        total_characters = characters_collection.count_documents({})
        return total_users, total_characters

    @staticmethod
    def broadcast_message(bot, message):
        """Broadcast a message to all users."""
        for user in users_collection.find({}, {"user_id": 1}):
            try:
                bot.send_message(chat_id=user["user_id"], text=message, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error broadcasting to {user['user_id']}: {e}")


async def show_random_character(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Display a random character in the chat."""
    global current_character
    current_character = Game.fetch_random_character()
    if not current_character:
        current_character = {"name": "Unknown", "rarity": "Unknown", "image_url": "https://via.placeholder.com/500"}
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=current_character["image_url"],
        caption=(
            f"📢 **Guess the Character!** 📢\n\n"
            f"⦿ **Rarity:** {current_character['rarity']}\n\n"
            "🔥 **Can you guess their name? Type it in the chat!** 🔥"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user guesses and enforce streak/threshold logic."""
    global current_character

    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name or ""
    user_message_count[user_id] += 1

    # Check if character exists
    if not current_character:
        await show_random_character(context, update.effective_chat.id)
        return

    guess = update.message.text.strip().lower()
    character_name = current_character["name"].lower()

    if guess in character_name:
        # Correct guess: Update balance and streak, then show new character
        balance_increment, new_streak = Game.update_user_balance_and_streak(
            user_id, first_name, last_name, correct_guess=True
        )
        await update.message.reply_text(
            f"🎉 **Correct!** You guessed **{current_character['name']}**.\n"
            f"💵 **You earned ${balance_increment}!**\n"
            f"🔥 **Streak: {new_streak}**",
            parse_mode=ParseMode.MARKDOWN,
        )
        user_message_count[user_id] = 0  # Reset message counter on correct guess
        await show_random_character(context, update.effective_chat.id)
    elif user_message_count[user_id] >= 5:
        # Show a new character after 5 messages
        Game.update_user_balance_and_streak(user_id, first_name, last_name, correct_guess=False)  # Reset streak
        user_message_count[user_id] = 0  # Reset message counter after threshold
        await show_random_character(context, update.effective_chat.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🎉 **Welcome to the Anime Guessing Bot!** 🎉\n\n"
        "🕹️ **How to Play:**\n"
        "⦿ A random anime character will be shown.\n"
        "⦿ Guess their name to earn rewards!\n\n"
        "💵 **Rewards:**\n"
        "⦿ Earn $10 for each correct guess.\n"
        "⦿ Get bonus rewards for streaks!\n\n"
        "🔥 **Let's start the game! Good luck!** 🔥",
        parse_mode=ParseMode.MARKDOWN
    )
    await show_random_character(context, update.effective_chat.id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📜 **Commands** 📜\n\n"
        "⦿ **/start** - Start the bot and display a random character.\n"
        "⦿ **/help** - Show this help menu.\n"
        "⦿ **/upload** - Upload a new character (admin only).\n"
        "⦿ **/currency** - View the top players by balance.\n"
        "⦿ **/addsudo** - Add a sudo user (owner only).\n"
        "⦿ **/broadcast** - Send a message to all users (owner only).\n"
        "⦿ **/stats** - View bot statistics (owner only).\n",
        parse_mode=ParseMode.MARKDOWN,
    )


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload a new character with specified name and image URL, rarity auto-assigned."""
    user_id = update.effective_user.id
    if Game.is_owner(user_id) or sudo_users_collection.find_one({"user_id": user_id}):
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "⚠️ Usage: /upload <image_url> <character_name>",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            image_url, character_name = context.args[0], " ".join(context.args[1:])
            rarity = Game.assign_rarity()  # Automatically assign rarity

            # Post character to the Telegram channel
            channel_message = await context.bot.send_photo(
                chat_id=CHARACTER_CHANNEL_ID,
                photo=image_url,
                caption=(
                    f"🌟 **New Character Uploaded!** 🌟\n\n"
                    f"⦿ **Name:** {character_name}\n"
                    f"⦿ **Rarity:** {rarity}\n"
                    f"✨ Available for guessing!"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

            # Save the character in the database with channel message ID
            characters_collection.insert_one({
                "name": character_name,
                "rarity": rarity,
                "image_url": image_url,
                "channel_message_id": channel_message.message_id,
            })

            await update.message.reply_text(
                f"✅ **Character '{character_name}' uploaded successfully!**\n"
                f"⦿ **Rarity:** {rarity}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Error during character upload: {e}")
            await update.message.reply_text("❌ **Failed to upload character.**", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ **You are not authorized to use this command.**", parse_mode=ParseMode.MARKDOWN)


async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the dynamically updated leaderboard with full Telegram profiles."""
    try:
        leaderboard = Game.get_user_currency()
        leaderboard_text = "💰 **Top 10 Players by Balance** 💰\n\n"

        if leaderboard:
            for i, user in enumerate(leaderboard, start=1):
                full_name = f"{user.get('first_name', 'Unknown')} {user.get('last_name', '')}".strip()
                balance = user.get("balance", 0)

                leaderboard_text += f"{i}. **{full_name}**\n   ⦿ **Balance:** ${balance}\n\n"
        else:
            leaderboard_text = "⚠️ No players have earned any balance yet. Be the first to play!"

        await update.message.reply_text(leaderboard_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        await update.message.reply_text("❌ **Failed to fetch leaderboard.**", parse_mode=ParseMode.MARKDOWN)


async def add_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a sudo user (owner only)."""
    user_id = update.effective_user.id
    if Game.is_owner(user_id):
        try:
            target_user_id = int(context.args[0])
            Game.add_sudo_user(target_user_id)
            await update.message.reply_text(
                f"✅ **User {target_user_id} has been added as a sudo user.**",
                parse_mode=ParseMode.MARKDOWN,
            )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "⚠️ **Usage:** /addsudo <user_id>\n\n"
                "⦿ Provide the Telegram user ID of the person to be added as sudo.",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        await update.message.reply_text(
            "❌ **You are not authorized to use this command.**",
            parse_mode=ParseMode.MARKDOWN,
        )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a broadcast message (owner only)."""
    user_id = update.effective_user.id
    if Game.is_owner(user_id):
        try:
            message = " ".join(context.args)
            if not message:
                await update.message.reply_text(
                    "⚠️ **Usage:** /broadcast <message>\n\n"
                    "⦿ Provide the message you want to broadcast to all users.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            Game.broadcast_message(context.bot, message)
            await update.message.reply_text(
                "✅ **Broadcast sent to all users.**",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Error during broadcast: {e}")
            await update.message.reply_text(
                "❌ **Failed to send the broadcast.**",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        await update.message.reply_text(
            "❌ **You are not authorized to use this command.**",
            parse_mode=ParseMode.MARKDOWN,
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (owner only)."""
    user_id = update.effective_user.id
    if Game.is_owner(user_id):
        total_users, total_characters = Game.get_bot_stats()
        await update.message.reply_text(
            f"📊 **Bot Statistics** 📊\n\n"
            f"👤 **Total Users:** {total_users}\n"
            f"🎭 **Total Characters:** {total_characters}\n",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            "❌ **You are not authorized to use this command.**",
            parse_mode=ParseMode.MARKDOWN,
        )


# Main Application
        application = Application.builder().token(BOT_TOKEN).build()
    
        # Command Handlers
    



# --- Chat Tracking Handler ---

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        users_collection.update_one(
            {"user_id": chat.id},
            {"$set": {"first_name": chat.first_name, "last_name": chat.last_name}},
            upsert=True
        )
    elif chat.type in ["group", "supergroup"]:
        groups_collection.update_one(
            {"group_id": chat.id},
            {"$set": {"title": chat.title}},
            upsert=True
        )


# Register the chat tracking handler

# --- Updated Chat Tracking with Group Activity ---

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        users_collection.update_one(
            {"user_id": chat.id},
            {"$set": {"first_name": chat.first_name, "last_name": chat.last_name}},
            upsert=True
        )
    elif chat.type in ["group", "supergroup"]:
        groups_collection.update_one(
            {"group_id": chat.id},
            {
                "$set": {"title": chat.title},
                "$inc": {"message_count": 1}
            },
            upsert=True
        )

# --- /topgroups Command Handler ---


    for idx, group in enumerate(top, start=1):
        title = group.get("title", "Unknown Group")
        count = group.get("message_count", 0)
        message += f"{idx}. {title} — `{count}` messages\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

# --- /topgroups Command Handler ---

async def top_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = groups_collection.find().sort("message_count", -1).limit(10)
    message = "*🏆 Top Groups by Activity:*\n\n"
    for idx, group in enumerate(top, start=1):
        title = group.get("title", "Unknown Group")
        count = group.get("message_count", 0)
        message += f"{idx}. {title} — `{count}` messages\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
if __name__ == "__main__":
    main()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("topgroups", top_groups))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("currency", currency))
    application.add_handler(CommandHandler("addsudo", add_sudo))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess_handler))
    application.add_handler(MessageHandler(filters.ALL, track_chats))
    application.run_polling()

if __name__ == "__main__":
    main()