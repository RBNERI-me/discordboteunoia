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
    # Render dynamically assigns a port via environment variables
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

# --- CONFIGURATION ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MOTION_POST_CHANNEL_ID = 1517108004166828153  # Channel where the initial "File a Motion" button embed lives
JUDGE_REVIEW_CHANNEL_ID = 1519903351557587064   # Private channel where Judges review submitted motions
JUDGE_ROLE_ID = 1517434703991410799        # Role ID allowed to accept/deny hearings
HEARING_CATEGORY_ID = 1380491610428805170       # Category ID where approved case channels are built

# NEW ROLE CONFIGURATION
CHIEF_MAGISTRATE_ROLE_ID = 1517434703991410799  # Replace with your actual Chief Magistrate Role ID if different

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- CONVERSATIONAL MEMORY STORAGE ---
conversation_histories = {}
MAX_MEMORY = 15 

# --- CASE MANAGEMENT COUNTER ---
case_counter = 1


# =================================================================
# PLACE UI COMPONENTS AT THE TOP SO THE BOT CAN SEE THEM IMMEDIATELY
# =================================================================

# -----------------------------------------------------------------
# 1. THE MOTION SUBMISSION MODAL
# -----------------------------------------------------------------
class MotionApplicationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Legal Motion Filing Form")

        self.plaintiff = discord.ui.TextInput(
            label="Plaintiff Username(s) / ID(s)", 
            style=discord.TextStyle.long,
            placeholder="e.g., @JohnDoe. Enter the party initiating the lawsuit.", 
            required=True, max_length=150
        )
        self.defendant = discord.ui.TextInput(
            label="Defendant Username(s) / ID(s)", 
            style=discord.TextStyle.long,
            placeholder="e.g., @JaneSmith. Enter the party being accused.", 
            required=True, max_length=150
        )
        self.lawyers = discord.ui.TextInput(
            label="Assigned Counsel / Legal Representatives", 
            style=discord.TextStyle.long,
            placeholder="e.g., Plaintiff: @LawyerA | Defendant: @LawyerB (or leave blank)", 
            required=False, max_length=200
        )
        self.issue = discord.ui.TextInput(
            label="Statement of Claim / Core Issue", 
            style=discord.TextStyle.long, 
            placeholder="Describe the rule breach, legal grievances, or incident timeline...", 
            required=True, max_length=1000
        )
        self.remedy = discord.ui.TextInput(
            label="Relief / Remedy Demanded", 
            style=discord.TextStyle.long, 
            placeholder="What outcome, fine, or settlement terms are you requesting from the court?", 
            required=True, max_length=400
        )

        self.add_item(self.plaintiff)
        self.add_item(self.defendant)
        self.add_item(self.lawyers)
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

        lawyer_value = self.lawyers.value if self.lawyers.value.strip() else "None Specified"

        embed = discord.Embed(
            title=f"⚖️ New Legal Motion Filed | {docket_number}",
            description=f"**Filer:** {interaction.user.mention}\n**Status:** Awaiting Judicial Assignment",
            color=discord.Color.blue()
        )
        embed.add_field(name="👤 Plaintiff(s)", value=self.plaintiff.value, inline=False)
        embed.add_field(name="🛡️ Defendant(s)", value=self.defendant.value, inline=False)
        embed.add_field(name="👔 Legal Representation", value=lawyer_value, inline=False)
        embed.add_field(name="📜 Claims & Core Legal Grievance", value=self.issue.value, inline=False)
        embed.add_field(name="🏛️ Remedy/Damages Demanded", value=self.remedy.value, inline=False)
        embed.set_footer(text=f"Filer ID: {interaction.user.id} | Judicial System Desk")

        view = JudgeReviewView(
            filer_id=interaction.user.id, 
            docket=docket_number, 
            plaintiff=self.plaintiff.value, 
            defendant=self.defendant.value
        )
        
        await review_channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ **Your motion has been successfully compiled and sent to the Judicial Review panel.**", ephemeral=True)


# -----------------------------------------------------------------
# 2. START FILING BUTTON VIEW
# -----------------------------------------------------------------
class StartMotionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @discord.ui.button(label="File a Motion", style=discord.ButtonStyle.danger, custom_id="persistent:start_motion", emoji="⚖️")
    async def start_motion_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MotionApplicationModal())


# -----------------------------------------------------------------
# 3. JUDGES INTERACTIVE ACTION BUTTONS
# -----------------------------------------------------------------
class JudgeReviewView(discord.ui.View):
    def __init__(self, filer_id: int, docket: str, plaintiff: str, defendant: str):
        super().__init__(timeout=None)
        self.filer_id = filer_id
        self.docket = docket
        self.plaintiff = plaintiff
        self.defendant = defendant

    @discord.ui.button(label="Accept Hearing", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_hearing(self, interaction: discord.Interaction, button: discord.ui.Button):
        judge_role = interaction.guild.get_role(JUDGE_ROLE_ID)
        chief_magistrate_role = interaction.guild.get_role(CHIEF_MAGISTRATE_ROLE_ID)
        
        if judge_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
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

        p_member = await apply_user_overwrite(self.plaintiff)
        d_member = await apply_user_overwrite(self.defendant)

        # Determine Courtroom Legal Status
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
        edited_embed.color = discord.Color.green()
        edited_embed.description = f"**Filer:** <@{self.filer_id}>\n**Status:** Approved & Assigned\n**Presiding Justice:** {interaction.user.mention}\n**Court Classification:** `{status_text}`\n**Trial Room:** {new_channel.mention}"
        
        await interaction.message.edit(embed=edited_embed, view=None)

        # Generate Intro Court Notice Banner
        court_description = (
            f"This channel has been officially established for litigation proceedings.\n\n"
            f"**Presiding Judge:** {interaction.user.mention}\n"
            f"**Plaintiff Parties:** {self.plaintiff}\n"
            f"**Defense Parties:** {self.defendant}\n\n"
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
        intro_msg = await new_channel.send(content=f"{interaction.user.mention} | Case Active Notification", embed=court_embed)
        await intro_msg.pin()

    @discord.ui.button(label="Deny & Dismiss", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny_hearing(self, interaction: discord.Interaction, button: discord.ui.Button):
        judge_role = interaction.guild.get_role(JUDGE_ROLE_ID)
        if judge_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
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
        edited_embed.color = discord.Color.red()
        edited_embed.description = f"**Filer:** <@{self.filer_id}>\n**Status:** Motion Dismissed / Rejected\n**Reviewed By:** {interaction.user.mention}"
        
        await interaction.message.edit(embed=edited_embed, view=None)


# =================================================================
# EVENTS AND MAIN LOGIC SECTION
# =================================================================

@bot.event
async def on_ready():
    print("--------------------------------------------------")
    print(f"🤖 Connected to Discord as: {bot.user.name}")
    print("☕ Omni-Manager Bot: Server Redesign & Multi-Purpose Engine Active!")
    print("--------------------------------------------------")
    bot.add_view(StartMotionView())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

def clean_ch_name(name: str) -> str:
    return name.lower().replace(" ", "-")

def build_server_snapshot(guild: discord.Guild) -> list:
    channel_tree = []
    for cat in guild.categories:
        cat_info = {"category_id": cat.id, "category_name": cat.name, "channels": []}
        for ch in cat.channels:
            ch_details = {"id": ch.id, "name": ch.name, "type": str(ch.type), "position": ch.position}
            if isinstance(ch, discord.TextChannel):
                ch_details["topic"] = ch.topic or "No topic set"
            elif isinstance(ch, discord.VoiceChannel):
                ch_details["bitrate"] = f"{int(ch.bitrate / 1000)}kbps"
            cat_info["channels"].append(ch_details)
        channel_tree.append(cat_info)
        
    orphan_channels = []
    for ch in guild.channels:
        if ch.category is None and not isinstance(ch, discord.CategoryChannel):
            ch_details = {"id": ch.id, "name": ch.name, "type": str(ch.type), "position": ch.position}
            if isinstance(ch, discord.TextChannel):
                ch_details["topic"] = ch.topic or "No topic set"
            orphan_channels.append(ch_details)
    if orphan_channels:
        channel_tree.append({"category_name": "No Category / Orphans", "channels": orphan_channels})
        
    return channel_tree


# =================================================================
# COMMANDS TIER
# =================================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setupcourt(ctx):
    """Admin Setup Utility: Dispatches the legal portal dashboard card into the system channel."""
    target_channel = ctx.guild.get_channel(MOTION_POST_CHANNEL_ID)
    if not target_channel:
        await ctx.send("❌ Error: Invalid setup target channel path ID configured.")
        return

    embed = discord.Embed(
        title="🏛️ High Court Judicial Filing Desk",
        description="Welcome to the judicial service department board. If you need to initiate formal civil litigation, challenge server citations, or request an administrative ruling, click the button below to draft your legal motion details.\n\n"
                    "⚠️ *Notice: Filings must present direct legal claims or rule breaches to be accepted by our judicial bench.*",
        color=discord.Color.dark_gray()
    )
    
    await target_channel.send(embed=embed, view=StartMotionView())
    await ctx.send(f"✅ Secure courthouse platform channel successfully mounted in {target_channel.mention}!")


@bot.command()
async def askme(ctx, *, user_prompt: str = ""):
    """Multi-Purpose AI Command: Modmail Ticket Router OR Absolute Server Overhaul Suite."""
    attachment_info = "None"
    uploaded_file = None
    if ctx.message.attachments:
        uploaded_file = ctx.message.attachments[0]
        attachment_info = f"File Name: {uploaded_file.filename} | URL: {uploaded_file.url}"
        if not user_prompt:
            user_prompt = f"I uploaded a file: {uploaded_file.filename}. Please handle it."

    if not ctx.author.guild_permissions.administrator:
        await ctx.send("📥 *Sending your message to the Café Staff team...*")
        category = discord.utils.get(ctx.guild.categories, name="Modmail Tickets")
        if not category:
            category = await ctx.guild.create_category("Modmail Tickets")
            
        clean_username = re.sub(r'[^a-zA-Z0-9]', '', ctx.author.name).lower()
        channel_name = f"ticket-{clean_username}"
        target_channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        
        if not target_channel:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            target_channel = await ctx.guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
            await target_channel.send(f"📬 **New Ticket Opened by {ctx.author.mention}**")

        embed = discord.Embed(description=user_prompt, color=discord.Color.orange())
        embed.set_author(name=f"From {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        if uploaded_file:
            embed.add_field(name="Attached File", value=uploaded_file.filename)
            if uploaded_file.content_type and uploaded_file.content_type.startswith("image/"):
                embed.set_image(url=uploaded_file.url)
                
        await target_channel.send(embed=embed)
        await ctx.send("✅ *Your Modmail entry has been delivered successfully!*")
        return

    async with ctx.typing():
        channel_id = ctx.channel.id
        channel_tree = build_server_snapshot(ctx.guild)
        roles_list = [r.name for r in ctx.guild.roles if not r.is_default()]

        if channel_id not in conversation_histories:
            conversation_histories[channel_id] = []

        system_instructions = (
            f"You are the ultimate Multi-Purpose AI Server Director of this server.\n"
            f"You have absolute authority to design, prune, clean, or rewrite layout assets based on user instructions.\n\n"
            f"EXHAUSTIVE SERVER CHANNEL GRAPH:\n{json.dumps(channel_tree, indent=2)}\n\n"
            f"EXISTING ROLES: {roles_list}\n"
            f"INCOMING ATTACHMENT DETAILS: {attachment_info}\n\n"
            f"CRITICAL: Change ONLY parts requested, or update names to fit themes seamlessly.\n"
            f"If the user wants to see, display, show, or get a list of channels or categories, set 'action' to 'list_server_channels'.\n"
            f"You must respond ONLY with a single valid JSON object containing exactly five keys: 'reply', 'action', 'target_name', 'meta', and 'embed_data'.\n\n"
            f"Allowed Multi-Purpose Action Tiers:\n"
            f"1. 'create_channel'  - Create text channel. (meta: category name)\n"
            f"2. 'create_voice'    - Create voice lounge. (meta: category name)\n"
            f"3. 'create_category' - Create a brand new channel category structural block.\n"
            f"4. 'delete_channel'  - Delete channel matching target_name exactly.\n"
            f"5. 'delete_category' - Delete a whole category block.\n"
            f"6. 'rename_channel'  - Rename channel. (target_name: old name, meta: new name)\n"
            f"7. 'move_channel'    - Move channel. (target_name: channel, meta: category name)\n"
            f"8. 'clear_chat'      - Purge text messages from current channel. (meta: number of messages as string e.g. '50')\n"
            f"9. 'send_embed'      - Dispatch an embed notification box using the 'embed_data' map block.\n"
            f"10. 'download_file'  - Pull user attachment file data stream and push it to a targeted text channel.\n"
            f"11. 'kick_member'    - Kick a problem member. (target_name: username or ID)\n"
            f"12. 'ban_member'     - Ban a member. (target_name: username or ID)\n"
            f"13. 'list_server_channels' - Show the user a visual list of all existing channels and categories.\n"
            f"14. 'none'           - Pure talk, answers, or data interpretation summaries.\n\n"
            f"JSON Structure Contract:\n"
            f"{{\n"
            f'  "reply": "Your administrative conversation brief.",\n'
            f'  "action": "one_of_the_fourteen_actions_above",\n'
            f'  "target_name": "target entity name string, or \'none\'",\n'
            f'  "meta": "Context metadata modifier string, or \'none\'",\n'
            f'  "embed_data": {{\n'
            f'     "title": "String or \'none\'",\n'
            f'     "description": "String or \'none\'",\n'
            f'     "color": "Hex value like \'#704214\' or \'none\'",\n'
            f'     "image_url": "URL or \'none\'"\n'
            f'  }}\n'
            f"}}"
        )

        messages_payload = [{"role": "system", "content": system_instructions}]
        for historic_message in conversation_histories[channel_id]:
            messages_payload.append(historic_message)
        messages_payload.append({"role": "user", "content": user_prompt})

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.3-70b-versatile", 
            "messages": messages_payload,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
            response_json = response.json()

            if "error" in response_json:
                await ctx.send(f"❌ Groq API Error: `{response_json['error'].get('message')}`")
                return

            ai_response = response_json['choices'][0]['message']['content'].strip()
            command_data = json.loads(ai_response)
            
            reply_message = command_data.get("reply", "")
            action = command_data.get("action", "none")
            target_name = command_data.get("target_name", "none")
            meta_data = command_data.get("meta", "none")
            embed_data = command_data.get("embed_data", {})

            conversation_histories[channel_id].append({"role": "user", "content": user_prompt})
            conversation_histories[channel_id].append({"role": "assistant", "content": ai_response})

            if reply_message:
                await ctx.send(reply_message)

            if action == "none":
                return

            # --- EXECUTION TIER ---
            if action == "list_server_channels":
                output_lines = [f"Here is the list of categories and channels in our {ctx.guild.name} server:"]
                for index, cat_block in enumerate(channel_tree, start=1):
                    cat_name = cat_block.get("category_name", "No Category / Orphans")
                    channel_names = [channel_item.get("name", "") for channel_item in cat_block.get("channels", [])]
                    channels_string = ", ".join(channel_names) if channel_names else "No channels inside"
                    output_lines.append(f"{index}. {cat_name}: {channels_string}")
                
                final_output = "\n".join(output_lines)
                if len(final_output) > 2000:
                    for chunk in [final_output[i:i+1900] for i in range(0, len(final_output), 1900)]:
                        await ctx.send(chunk)
                else:
                    await ctx.send(final_output)

            elif action == "create_category":
                await ctx.guild.create_category(name=target_name)
                await ctx.send(f"📁 *AI Action: Built server category block `📂 {target_name}`*")

            elif action == "delete_category":
                category = discord.utils.get(ctx.guild.categories, name=target_name)
                if category:
                    await category.delete()
                    await ctx.send(f"🗑️ *AI Action: Removed category group `{target_name}`*")

            elif action == "clear_chat":
                limit_amt = int(meta_data) if meta_data.isdigit() else 10
                purged = await ctx.channel.purge(limit=limit_amt)
                await ctx.send(f"🧹 *AI Action: Purged `{len(purged)}` messages from this channel.*", delete_after=5)

            elif action == "send_embed" and embed_data:
                custom_embed = discord.Embed(
                    title=embed_data.get("title", "Notice"),
                    description=embed_data.get("description", ""),
                    color=discord.Color(int(embed_data.get("color", "#704214").lstrip("#"), 16))
                )
                if embed_data.get("image_url") != "none":
                    custom_embed.set_image(url=embed_data.get("image_url"))
                target_chan = discord.utils.get(ctx.guild.text_channels, name=clean_ch_name(target_name)) or ctx.channel
                await target_chan.send(embed=custom_embed)

            elif action == "download_file" and uploaded_file:
                file_bytes = await uploaded_file.read()
                data_stream = io.BytesIO(file_bytes)
                discord_file = discord.File(data_stream, filename=uploaded_file.filename)
                target_chan = discord.utils.get(ctx.guild.text_channels, name=clean_ch_name(target_name)) or ctx.channel
                await target_chan.send(file=discord_file)

            elif action == "kick_member":
                member = ctx.guild.get_member(int(target_name)) if target_name.isdigit() else discord.utils.get(ctx.guild.members, name=target_name)
                if member:
                    await member.kick(reason="AI Admin Request")
                    await ctx.send(f"👢 *AI Action: Kicked member `{member.display_name}`*")

            elif action == "ban_member":
                member = ctx.guild.get_member(int(target_name)) if target_name.isdigit() else discord.utils.get(ctx.guild.members, name=target_name)
                if member:
                    await member.ban(reason="AI Admin Request")
                    await ctx.send(f"🔨 *AI Action: Permanently banned member `{member.display_name}`*")

            elif action == "create_channel":
                target_cat = discord.utils.get(ctx.guild.categories, name=meta_data)
                await ctx.guild.create_text_channel(name=clean_ch_name(target_name), category=target_cat)
            elif action == "create_voice":
                target_cat = discord.utils.get(ctx.guild.categories, name=meta_data)
                await ctx.guild.create_voice_channel(name=target_name, category=target_cat)
            elif action == "delete_channel":
                channel = discord.utils.get(ctx.guild.channels, name=clean_ch_name(target_name)) or discord.utils.get(ctx.guild.channels, name=target_name)
                if channel: await channel.delete()
            elif action == "rename_channel":
                channel = discord.utils.get(ctx.guild.channels, name=clean_ch_name(target_name)) or discord.utils.get(ctx.guild.channels, name=target_name)
                if channel: await channel.edit(name=clean_ch_name(meta_data) if isinstance(channel, discord.TextChannel) else meta_data)

        except discord.Forbidden:
            await ctx.send("❌ *Hierarchy / Permission Blocked: Make sure my role is at the top of your list.*")
        except json.JSONDecodeError as json_err:
            await ctx.send("❌ *Data Engine Error: Failed to structure raw JSON configurations safely.*")
            print(f"DEBUG - Raw invalid JSON returned was: {ai_response}")
        except Exception as e:
            await ctx.send(f"❌ Execution Core Exception: {e}")

# ... [rest of your code above] ...

        except Exception as e:
            await ctx.send(f"❌ Execution Core Exception: {e}")

# Start the web server right before launching the discord client loop
keep_alive()
bot.run(DISCORD_TOKEN)