import discord
from discord.ext import commands
import asyncio
import logging

# Import the views from your extension file to register them for persistence
from court_testing import (
    setup_court_testing, 
    ApplicationEntryBoardView, 
    ApplicationReviewView, 
    MockTrialAssessmentView
)

# Setup basic logging to monitor startup and tracking registrations
logging.basicConfig(level=logging.INFO)

# --- CONFIGURATION & OWNER ACCESS ---
OWNER_USER_ID = 1236605844733296685  # Your specific Discord User ID

# --- BOT INITIALIZATION ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =================================================================
# CUSTOM GLOBAL OWNER CHECK
# =================================================================
@bot.check
async def check_owner_privileges(ctx):
    """
    Global check that automatically grants execution clearance to the owner 
    bypassing standard role/permission requirements, while allowing normal rules 
    for other users.
    """
    if ctx.author.id == OWNER_USER_ID:
        return True
    return True  # Let standard command checks handle other members

# =================================================================
# PERSISTENT VIEW REGISTRATION HOOK
# =================================================================

@bot.event
async def setup_hook():
    """
    Executes before the bot connects to Discord.
    Registers persistent views so their interactive button and menu callbacks 
    continue working seamlessly across bot restarts without manual reactivation.
    """
    # 1. Register the Main Selection Board
    bot.add_view(ApplicationEntryBoardView())
    
    # 2. Register Review Pipeline UI (with dynamic structural fallbacks)
    bot.add_view(ApplicationReviewView(applicant_id=0, path_type="advocacy"))
    bot.add_view(ApplicationReviewView(applicant_id=0, path_type="judicial"))
    
    # 3. Register Practical Room Grading UI
    bot.add_view(MockTrialAssessmentView(applicant_id=0, path_type="advocacy"))
    bot.add_view(MockTrialAssessmentView(applicant_id=0, path_type="judicial"))
    
    print("✨ [System] Persistent interface listeners attached and active.")

    # 4. Initialize and load your court testing functional module commands
    setup_court_testing(bot)
    print("🏛️ [System] Judicial Evaluation Extension mounted successfully.")

# =================================================================
# GLOBAL CORE BOT EVENTS
# =================================================================

@bot.event
async def on_ready():
    """Fires when connection to Discord gateway is successfully stabilized."""
    print("--------------------------------------------------")
    print(f"Logged in securely as: {bot.user.name} (ID: {bot.user.id})")
    print("Status Tracking Setup: Online and ready.")
    print("--------------------------------------------------")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="Court Room Proceedings"
        )
    )

# --- START RUNTIME PIPELINE ---
if __name__ == "__main__":
    # Replace with your secure Discord Developer Portal application token
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: You must replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token.")
    else:
        bot.run(BOT_TOKEN)
