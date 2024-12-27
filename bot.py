import os
import random
import logging
import time
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io

# --- Environment and Database Setup ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URI = os.getenv("MONGO_URI")
CHARACTER_CHANNEL_ID = -1002438449944

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]
sudo_users_collection = db["sudo_users"]

# Rarities
RARITIES = [
    ("❖ Common 🌱", 60),
    ("❖ Uncommon 🌿", 20),
    ("❖ Rare 🌟", 10),
    ("❖ Epic 🌠", 5),
    ("❖ Legendary 🏆", 3),
    ("❖ Mythical 🔥", 2),
]

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Game State
character_cache = []
current_character = None
user_message_count = Counter()


# --- Game Logic ---
class Game:
    @staticmethod
    def assign_rarity():
        total_weight = sum(weight for _, weight in RARITIES)
        choice = random.uniform(0, total_weight)
        cumulative = 0
        for rarity, weight in RARITIES:
            cumulative += weight
            if choice <= cumulative:
                return rarity
        return "❖ Common 🌱"

    @staticmethod
    def fetch_random_character():
        global character_cache
        if not character_cache:
            character_cache = list(characters_collection.aggregate([{"$sample": {"size": 10}}]))
        return character_cache.pop() if character_cache else None

    @staticmethod
    def update_user_balance_and_streak(user_id, first_name, last_name, correct_guess):
        user = users_collection.find_one({"user_id": user_id})
        if user:
            if correct_guess:
                new_streak = user.get("streak", 0) + 1
                balance_increment = 10 + (new_streak * 2)
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
        return list(users_collection.find().sort("balance", -1).limit(10))

    @staticmethod
    def is_owner(user_id):
        return user_id == OWNER_ID


# --- Profile Image Generation ---
def generate_profile_image(user_data):
    bg_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new("RGB", (600, 500), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 36)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 22)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    text_color = (255, 255, 255) if sum(bg_color) / 3 < 128 else (0, 0, 0)
    draw.text((230, 20), "❖ *Profile* ❖", font=font_title, fill=text_color)

    profile_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    draw_profile = ImageDraw.Draw(profile_img)
    initials = f"{user_data['first_name'][0]}{user_data['last_name'][0]}"
    draw_profile.text((70, 90), initials, font=font_text, fill=(0, 0, 0))

    mask = Image.new("L", (200, 200), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 200, 200), fill=255)
    profile_img = Image.composite(profile_img, Image.new("RGB", (200, 200)), mask)

    img.paste(profile_img, (200, 100), mask=mask)
    draw.text((150, 320), f"❖ Name: {user_data['first_name']}", font=font_text, fill=text_color)
    draw.text((150, 360), f"❖ Rank: {user_data['rank']}", font=font_text, fill=text_color)
    draw.text((150, 400), f"❖ Balance: ${user_data['balance']}", font=font_text, fill=text_color)
    draw.text((150, 440), f"❖ Streak: {user_data['streak']}", font=font_text, fill=text_color)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# --- Commands ---
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = users_collection.find_one({"user_id": update.effective_user.id})
    buffer = generate_profile_image(user or {"first_name": "User", "rank": "Unranked", "balance": 0, "streak": 0})
    await update.message.reply_photo(photo=buffer, caption="❖ *Your Profile* ❖", parse_mode=ParseMode.MARKDOWN)

# Run Application
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("profile", profile))
    app.run_polling()


if __name__ == "__main__":
    main()
