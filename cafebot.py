import discord
from discord.ext import commands
import asyncio
import logging
import os

# Import the views and the session tracking dictionary from your extension file
from court_testing import (
    setup_court_testing, 
    ApplicationEntryBoardView, 
    ApplicationReviewView, 
    MockTrialAssessmentView,
    ACTIVE_TEST_SESSIONS  # Imported to clear on boot
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
    Global check that automatically grants execution clearance to the owner,
    allowing you to bypass standard command restrictions.
    """
    # NOTE: discord.py checks work sequentially. If you want this to completely 
    # override hardcoded decorators like @commands.has_permissions(administrator=True),
    # you'll need to check for owner inside those specific command blocks instead, 
    # as local command checks run after global ones.
    if ctx.author.id == OWNER_USER_ID:
        return True  
    return True  # Let standard command checks handle filtering normally

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
    # 1. Register the Main Selection Board (Passed the required bot instance)
    bot.add_view(ApplicationEntryBoardView(bot))
    
    # 2. Register Review Pipeline UI (with dynamic structural fallbacks for persistence)
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
    
    # --- GLOBAL CLEAR ON RESTART ---
    # Instantly flushes out old memory tracking states upon deployment reboots
    ACTIVE_TEST_SESSIONS.clear()
    print("🧹 [System Failsafe] Active evaluation cache cleared out for system restart.")
    print("--------------------------------------------------")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="Court Room Proceedings"
        )
    )

# --- START RUNTIME PIPELINE ---
if __name__ == "__main__":
    # Pull token securely from environment variables
    BOT_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: You must replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token or set up a DISCORD_TOKEN Environment Variable.")
    else:
        bot.run(BOT_TOKEN)
