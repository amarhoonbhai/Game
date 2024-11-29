import os
import random
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB setup
mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["anime_bot"]
users_collection = db["users"]
characters_collection = db["characters"]

# Configuration
OWNER_ID = int(os.getenv("OWNER_ID"))
CHARACTER_CHANNEL_ID = int(os.getenv("CHARACTER_CHANNEL_ID"))
sudo_users = set()  # Sudo users will be stored here

# Rarity Levels
RARITY_LEVELS = ["🌟 Common", "🔥 Elite", "💎 Rare", "🌠 Legendary"]

# Rarity probabilities for auto-assignment
RARITY_PROBABILITIES = {
    "🌟 Common": 0.5,
    "🔥 Elite": 0.3,
    "💎 Rare": 0.15,
    "🌠 Legendary": 0.05
}

# Tags by level
def get_level_and_tag(coins):
    """Calculate level and tag based on coins."""
    level = coins // 10
    if level < 50:
        tag = "🐣 Novice Explorer"
    elif level < 200:
        tag = "💪 Rising Star"
    elif level < 500:
        tag = "🏆 Seasoned Warrior"
    elif level < 999:
        tag = "🌟 Legendary Hero"
    elif level == 999:
        tag = "⚡ Ultimate Champion"
    elif level >= 1000:
        tag = "🔥 Over Power"
    else:
        tag = "❓ Unranked"
    return level, tag

# Helper functions
def get_user_profile(user_id):
    """Fetch or create a user profile in the database."""
    user = users_collection.find_one({"_id": user_id})
    if not user:
        user = {"_id": user_id, "coins": 0, "correct_guesses": 0, "games_played": 0, "profile_name": "Unknown"}
        users_collection.insert_one(user)
    return user

def update_user_stats(user_id, coins, correct_guess=False):
    """Update user stats."""
    update_query = {"$inc": {"coins": coins, "games_played": 1}}
    if correct_guess:
        update_query["$inc"]["correct_guesses"] = 1
    users_collection.update_one({"_id": user_id}, update_query)

def is_owner(user_id):
    return user_id == OWNER_ID

def is_sudo(user_id):
    return user_id in sudo_users

def add_sudo(user_id):
    sudo_users.add(user_id)

# Upload character
def upload_character(user_id, image_url, name, rarity=None):
    """Upload a new character to the database."""
    if not (is_owner(user_id) or is_sudo(user_id)):
        print("❌ You do not have permission to upload characters.")
        return

    if rarity is None:
        rarity = random.choices(
            list(RARITY_PROBABILITIES.keys()), 
            weights=list(RARITY_PROBABILITIES.values()), 
            k=1
        )[0]

    character_data = {
        "image_url": image_url,
        "name": name,
        "rarity": rarity
    }
    characters_collection.insert_one(character_data)

    print(f"✅ **Character Uploaded Successfully!**")
    print(f"🎭 **Name**: {name}")
    print(f"📸 **Image URL**: {image_url}")
    print(f"🌟 **Rarity**: {rarity}")

# Start game
def start_game(user_id, user_name):
    """Start the guessing game."""
    print(f"\n🎮 **Welcome to Philo Guesser, {user_name}! 🌟**")
    print("🎉 Test your knowledge and climb the leaderboard by guessing correctly!")

    while True:
        chosen_anime = random.choice(anime_list)
        print("\n🤔 **I have chosen an anime. Can you guess which one it is?**")
        wrong_attempts = 0

        while wrong_attempts < 3:
            guess = input("🎮 Your guess: ").strip()
            if guess.lower() in chosen_anime.lower():
                print(f"🎉 **Correct!** The anime is **{chosen_anime}**. 🏆 You earned 10 coins!")
                update_user_stats(user_id, coins=10, correct_guess=True)
                return
            else:
                wrong_attempts += 1
                print("❌ **Wrong guess. Try again!** 🚨")

        print("\n🚨 **Too many wrong guesses! Sending a new character...**")
        show_random_character()

# Show random character after wrong guesses
def show_random_character():
    """Display a random character from the database."""
    character = characters_collection.aggregate([{ "$sample": { "size": 1 } }])
    character = list(character)
    if character:
        char = character[0]
        print(f"\n🎭 **Character Spotlight!** 🌟")
        print(f"🎨 **Name**: {char['name']}")
        print(f"🌟 **Rarity**: {char['rarity']}")
        print(f"📸 **Image URL**: {char['image_url']}")
    else:
        print("\n🚨 **No characters available in the database!**")

# Profile command
def profile(user_id):
    """Display the user's profile."""
    user = get_user_profile(user_id)
    coins = user["coins"]
    level, tag = get_level_and_tag(coins)
    if level > 1000:
        tag = "🔥 Over Power"
    print(f"\n📊 **Your Profile**")
    print(f"👤 **User ID**: {user_id}")
    print(f"💰 **Coins**: {coins}")
    print(f"🎮 **Level**: {level} {tag}")
    print(f"✔️ **Correct Guesses**: {user['correct_guesses']}")
    print(f"🎮 **Games Played**: {user['games_played']}")
    print("⭐ Keep playing to level up and earn rewards!")

# Levels command
def levels():
    """Display the leaderboard of top 10 players."""
    top_users = users_collection.find().sort("coins", -1).limit(10)
    print("\n🏆 **Top 10 Players Leaderboard** 🌟\n")
    print("Rank   | Profile Name          | Coins   | Level & Tag           | Correct Guesses | Games Played")
    print("-" * 85)
    for rank, user in enumerate(top_users, 1):
        coins = user["coins"]
        level, tag = get_level_and_tag(coins)
        if level > 1000:
            tag = "🔥 Over Power"
        profile_name = user.get("profile_name", "Unknown")
        print(f"#{rank:<6} | {profile_name:<20} | {coins:<7} | {level} {tag:<18} | {user['correct_guesses']:<15} | {user['games_played']}")

# Stats command
def stats(user_id):
    """Display bot stats (owner only)."""
    if not is_owner(user_id):
        print("❌ You do not have permission to view bot stats.")
        return
    total_users = users_collection.count_documents({})
    total_characters = characters_collection.count_documents({})
    print("\n📊 **Bot Stats**:")
    print(f"👥 **Total Users**: {total_users}")
    print(f"🎭 **Total Characters**: {total_characters}")

# Help command
def help_command():
    """Display the list of commands."""
    print("\n📜 **Available Commands**:")
    print("🎮 `/start` - Start the anime guessing game.")
    print("👤 `/profile` - View your profile stats.")
    print("📊 `/stats` - View bot stats (Owner only).")
    print("🏆 `/levels` - View the top 10 players by coins.")
    print("🎭 `/upload` - Upload a new character (Owner/Sudo only).")
    print("🔧 `/addsudo` - Add a new sudo user (Owner only).")
    print("ℹ️ `/help` - View this help message.")

# Main interaction loop
if __name__ == "__main__":
    print("🎮 Welcome to the Anime Guessing Bot! 🌟")

    while True:
        user_id = int(input("🆔 Enter your User ID: "))
        user_name = input("📝 Enter your Profile Name: ")
        command = input("📥 Enter a command (/start, /profile, /stats, /levels, /upload, /addsudo, /help, /quit): ").strip()

        if command == "/start":
            start_game(user_id, user_name)
        elif command == "/profile":
            profile(user_id)
        elif command == "/levels":
            levels()
        elif command == "/stats":
            stats(user_id)
        elif command == "/help":
            help_command()
        elif command == "/quit":
            print("👋 Goodbye! See you next time! 🌟")
            break
        else:
            print("❌ Invalid command. Type `/help` for a list of available commands.")
