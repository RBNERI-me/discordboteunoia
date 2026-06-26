import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import re
import io
import asyncio
from flask import Flask
from threading import Thread
import os

# --- LIGHTWEIGHT WEB SERVER FOR RENDER ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot status: Operational & Online"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

# --- CONFIGURATION ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MOTION_POST_CHANNEL_ID = 1517108004166828153  
JUDGE_REVIEW_CHANNEL_ID = 1519903351557587064   
JUDGE_ROLE_ID = 1517434703991410799        
HEARING_CATEGORY_ID = 1380491610428805170       

CHIEF_MAGISTRATE_ROLE_ID = 1517434703991410799  
COURT_LOGS_CHANNEL_ID = 1519903351557587064  

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

conversation_histories = {}
MAX_MEMORY = 15 
case_counter = 1

# Helper to look for user mentions or IDs and return them clean
def extract_mentions(input_str):
    if not input_str or input_str.strip().lower() == "none":
        return "None"
    matches = re.findall(r'<@!?(\d+)>|\b(\d{17,19})\b', input_str)
    mentions = []
    for match in matches:
        m_id = match[0] if match[0] else match[1]
        mentions.append(f"<@{m_id}>")
    return " ".join(mentions) if mentions else input_str

# =================================================================
# UI COMPONENTS (ORDERED BY DEPENDENCY TO PREVENT NAMEERRORS)
# =================================================================

class CourtroomLogView(discord.ui.View):
    def __init__(self, docket: str = "", plaintiff: str = "", defendant: str = "", judge_id: int = 0):
        # Added a strict custom_id to make this view persistent as well
        super().__init__(timeout=None)
        self.docket = docket
        self.plaintiff = plaintiff
        self.defendant = defendant
        self.judge_id = judge_id

    @discord.ui.button(label="Generate Court Log & Close", style=discord.ButtonStyle.secondary, custom_id="courtroom:archive_log", emoji="📜")
    async def archive_log_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        judge_role = interaction.guild.get_role(JUDGE_ROLE_ID)
        
        if (judge_role and judge_role in interaction.user.roles) or interaction.user.guild_permissions.administrator:
            pass
        else:
            await interaction.response.send_message("❌ **Access Denied:** Only verified judicial officers can execute courtroom logs.", ephemeral=True)
            return

        await interaction.response.defer()
        await interaction.followup.send("⏳ *Compiling transcript files and packaging legal archives...*")

        log_channel = interaction.guild.get_channel(COURT_LOGS_CHANNEL_ID)
        
        transcript_text = f"=== COURTROOM TRANSCRIPT LOG FOR {self.docket} ===\n\n"
        async for msg in interaction.channel.history(limit=1000, oldest_first=True):
            time_stamp = msg.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            transcript_text += f"[{time_stamp}] {msg.author.name} ({msg.author.id}): {msg.clean_content}\n"
            if msg.attachments:
                for attachment in msg.attachments:
                    transcript_text += f" -> [Attachment File]: {attachment.url}\n"
        
        data_stream = io.BytesIO(transcript_text.encode('utf-8'))
        log_file = discord.File(data_stream, filename=f"transcript-{self.docket.lower()}.txt")

        if log_channel:
            log_embed = discord.Embed(
                title=f"📁 Case Closed & Archived | {self.docket}",
                description=f"Court transcript processing complete. Vault file compiled by {interaction.user.mention}.",
                color=discord.Color.dark_teal()
            )
            log_embed.add_field(name="🏛️ Court Trial Room", value=interaction.channel.name, inline=True)
            log_embed.add_field(name="👤 Plaintiff", value=extract_mentions(self.plaintiff), inline=True)
            log_embed.add_field(name="🛡️ Defendant", value=extract_mentions(self.defendant), inline=True)
            log_embed.set_footer(text=f"Presiding Closing Judge ID: {interaction.user.id}")
            
            await log_channel.send(embed=log_embed, file=log_file)

        await interaction.followup.send("✅ Archive file delivered safely. This channel will now self-destruct in 10 seconds.")
        await asyncio.sleep(10)
        await interaction.channel.delete()


class JudgeReviewView(discord.ui.View):
    def __init__(self, filer_id: int = 0, docket: str = "", plaintiff: str = "", defendant: str = "", issue: str = "", remedy: str = "", plaintiff_lawyers: str = "", defendant_lawyers: str = ""):
        super().__init__(timeout=None)
        self.filer_id = filer_id
        self.docket = docket
        self.plaintiff = plaintiff
        self.defendant = defendant
        self.issue = issue
        self.remedy = remedy
        self.plaintiff_lawyers = plaintiff_lawyers
        self.defendant_lawyers = defendant_lawyers

    @discord.ui.button(label="Accept Hearing", style=discord.ButtonStyle.success, custom_id="judge:accept_hearing", emoji="✅")
    async def accept_hearing(self, interaction: discord.Interaction, button: discord.ui.Button):
        judge_role = interaction.guild.get_role(JUDGE_ROLE_ID)
        chief_magistrate_role = interaction.guild.get_role(CHIEF_MAGISTRATE_ROLE_ID)
        
        if (judge_role and judge_role in interaction.user.roles) or interaction.user.guild_permissions.administrator:
            pass
        else:
            await interaction.response.send_message("❌ **Access Denied:** Only verified judicial officers can accept this request.", ephemeral=True)
            return

        await interaction.response.defer()
        category = interaction.guild.get_channel(HEARING_CATEGORY_ID)
        
        clean_docket = self.docket.lower()
        channel_name = f"🏛️-{clean_docket}-hearing"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
            judge_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        async def apply_user_overwrite(username_str):
            if not username_str or username_str.strip().lower() == "none":
                return None
            clean_name = username_str.replace("@", "").replace("<", "").replace(">", "").replace("!", "").strip().split()[0]
            if clean_name.isdigit():
                try:
                    member = await interaction.guild.fetch_member(int(clean_name))
                    if member:
                        overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                        return member
                except discord.HTTPException:
                    pass
            
            member = discord.utils.get(interaction.guild.members, name=clean_name) or discord.utils.get(interaction.guild.members, display_name=clean_name)
            if member:
                overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                return member
            return None

        await apply_user_overwrite(self.plaintiff)
        await apply_user_overwrite(self.defendant)
        await apply_user_overwrite(self.plaintiff_lawyers)
        await apply_user_overwrite(self.defendant_lawyers)

        is_official = False
        if interaction.user.guild_permissions.administrator or (chief_magistrate_role and chief_magistrate_role in interaction.user.roles):
            is_official = True

        status_text = "OFFICIAL PROCEEDING" if is_official else "PURELY ROLEPLAY (Unverified Status)"
        embed_color = discord.Color.gold() if is_official else discord.Color.light_gray()

        new_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"[{status_text}] Trial Room for Case Docket {self.docket}."
        )

        edited_embed = interaction.message.embeds[0]
        edited_embed.title = f"⚖️ Legal Motion [ACCEPTED] | {self.docket}"
        edited_embed.color = discord.Color.green()
        edited_embed.description = f"**Filer:** <@{self.filer_id}>\n**Status:** ✅ Approved & Assigned\n**Presiding Justice:** {interaction.user.mention}\n**Court Classification:** `{status_text}`\n**Trial Room:** {new_channel.mention}"
        await interaction.message.edit(embed=edited_embed, view=None)

        p_mentions = extract_mentions(self.plaintiff)
        d_mentions = extract_mentions(self.defendant)
        pl_mentions = extract_mentions(self.plaintiff_lawyers)
        dl_mentions = extract_mentions(self.defendant_lawyers)

        mention_broadcast = f"🔔 **Case Notification Drop** | Plaintiff: {p_mentions} | Defendant: {d_mentions} | Plaintiff Legal Counsel: {pl_mentions} | Defendant Legal Counsel: {dl_mentions}"
        await new_channel.send(content=mention_broadcast)

        court_description = (
            f"This channel has been officially established for litigation proceedings.\n\n"
            f"⚖️ **Presiding Judge:** {interaction.user.mention}\n"
            f"👤 **Plaintiff:** {p_mentions}\n"
            f"🛡️ **Defendant:** {d_mentions}\n"
            f"👔 **Plaintiff Legal Reps:** {pl_mentions}\n"
            f"💼 **Defendant Legal Reps:** {dl_mentions}\n\n"
        )

        if is_official:
            court_description += "⚖️ **Official Status:** Granted. This case is authorized as an official administrative hearing by a Chief Magistrate/Administrator."
        else:
            court_description += "🎭 **Roleplay Status:** Active. This trial is classified as **Roleplay Only**. Sentences, verdicts, or restrictions generated here hold no structural server authority unless formally authorized by the Chief Magistrate."

        court_embed = discord.Embed(
            title=f"🏛️ Court of Law | Case Entry {self.docket}",
            description=court_description,
            color=embed_color
        )
        court_embed.add_field(name="📜 State of Claim / Core Issues", value=self.issue, inline=False)
        court_embed.add_field(name="⚖️ Relief / Remedy Demanded", value=self.remedy, inline=False)
        
        log_button_view = CourtroomLogView(
            docket=self.docket, 
            plaintiff=self.plaintiff, 
            defendant=self.defendant, 
            judge_id=interaction.user.id
        )
        
        intro_msg = await new_channel.send(embed=court_embed, view=log_button_view)
        await intro_msg.pin()

    @discord.ui.button(label="Deny & Dismiss", style=discord.ButtonStyle.danger, custom_id="judge:deny_hearing", emoji="❌")
    async def deny_hearing(self, interaction: discord.Interaction, button: discord.ui.Button):
        judge_role = interaction.guild.get_role(JUDGE_ROLE_ID)
        if (judge_role and judge_role in interaction.user.roles) or interaction.user.guild_permissions.administrator:
            pass
        else:
            await interaction.response.send_message("❌ **Access Denied:** Only verified judicial officers can reject this request.", ephemeral=True)
            return

        await interaction.response.defer()

        filer = interaction.guild.get_member(self.filer_id)
        if filer:
            try:
                dm_embed = discord.Embed(
                    title="⚖️ Legal Motion Status: Dismissed",
                    description=f"Your motion associated with Docket **{self.docket}** has been formally reviewed and denied by the Court.",
                    color=discord.Color.red()
                )
                await filer.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        edited_embed = interaction.message.embeds[0]
        edited_embed.title = f"⚖️ Legal Motion [REJECTED] | {self.docket}"
        edited_embed.color = discord.Color.red()
        edited_embed.description = f"**Filer:** <@{self.filer_id}>\n**Status:** ❌ Motion Dismissed / Rejected\n**Reviewed By:** {interaction.user.mention}"
        await interaction.message.edit(embed=edited_embed, view=None)


class MotionApplicationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Legal Motion Filing Form")

        self.plaintiff = discord.ui.TextInput(
            label="Plaintiff User ID", 
            style=discord.TextStyle.short,
            placeholder="e.g. 151710800416682815", 
            required=True, max_length=100
        )
        self.defendant = discord.ui.TextInput(
            label="Defendant User ID", 
            style=discord.TextStyle.short,
            placeholder="e.g. 151990335155758706", 
            required=True, max_length=100
        )
        self.legal_representatives = discord.ui.TextInput(
            label="Legal Rep IDs (Plaintiff | Defendant)", 
            style=discord.TextStyle.short,
            placeholder="e.g. 138049161042880517 | 151743470399141079", 
            required=False, max_length=200
        )
        self.issue = discord.ui.TextInput(
            label="State of Claim / Core Issues", 
            style=discord.TextStyle.long, 
            placeholder="Describe the rule breach, legal grievances, or incident timeline...", 
            required=True, max_length=800
        )
        self.remedy = discord.ui.TextInput(
            label="Relief / Remedy Demanded", 
            style=discord.TextStyle.long, 
            placeholder="Specify legal remedies, structural retributions, or payout settlements...", 
            required=True, max_length=400
        )

        self.add_item(self.plaintiff)
        self.add_item(self.defendant)
        self.add_item(self.legal_representatives)
        self.add_item(self.issue)
        self.add_item(self.remedy)

    async def on_submit(self, interaction: discord.Interaction):
        global case_counter
        await interaction.response.defer(ephemeral=True)
        
        review_channel = interaction.guild.get_channel(JUDGE_REVIEW_CHANNEL_ID)
        if not review_channel:
            await interaction.followup.send("❌ Setup Error: The judicial review channel could not be located.", ephemeral=True)
            return

        docket_number = f"CASE-2026-{case_counter:03d}"
        case_counter += 1

        raw_reps = self.legal_representatives.value if self.legal_representatives.value.strip() else "None | None"
        if "|" in raw_reps:
            p_lawyers, d_lawyers = [part.strip() for part in raw_reps.split("|", 1)]
        else:
            p_lawyers = raw_reps
            d_lawyers = "None"

        embed = discord.Embed(
            title=f"⚖️ New Legal Motion Filed | {docket_number}",
            description=f"**Filer:** {interaction.user.mention}\n**Status:** 🟡 Awaiting Judicial Assignment",
            color=discord.Color.blue()
        )
        embed.add_field(name="👤 Plaintiff ID", value=self.plaintiff.value, inline=True)
        embed.add_field(name="🛡️ Defendant ID", value=self.defendant.value, inline=True)
        embed.add_field(name="👔 Plaintiff Legal Rep ID", value=p_lawyers, inline=False)
        embed.add_field(name="💼 Defendant Legal Rep ID", value=d_lawyers, inline=False)
        embed.add_field(name="📜 Claims & Core Legal Grievance", value=self.issue.value, inline=False)
        embed.add_field(name="🏛️ Relief / Remedy Demanded", value=self.remedy.value, inline=False)
        embed.set_footer(text=f"Filer ID: {interaction.user.id} | Judicial System Desk")

        view = JudgeReviewView(
            filer_id=interaction.user.id, 
            docket=docket_number, 
            plaintiff=self.plaintiff.value, 
            defendant=self.defendant.value,
            issue=self.issue.value,
            remedy=self.remedy.value,
            plaintiff_lawyers=p_lawyers,
            defendant_lawyers=d_lawyers
        )
        
        await review_channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ **Your motion has been successfully compiled and sent to the Judicial Review panel.**", ephemeral=True)


class StartMotionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @discord.ui.button(label="File a Motion", style=discord.ButtonStyle.danger, custom_id="persistent:start_motion", emoji="⚖️")
    async def start_motion_click(self, interaction: discord.Interaction, button:
