import discord
from discord.ext import commands
import random
import asyncio

# --- CONFIGURATION PATH DETAILS ---
TESTING_BOARD_CHANNEL_ID = 1521006976023400489  
ADVOCACY_LOG_CHANNEL_ID = 1521007129899827302  
JUDICIAL_LOG_CHANNEL_ID = 1521007158823485551   

MOCK_TRIAL_CATEGORY_ID = 1521007475602755655     

ROLE_CHIEF_MAGISTRATE = 1519858689941573794
ROLE_SENIOR_JUDGE = 1519858791275823195
ROLE_BARRISTER = 1519893292765024368

ROLE_ADVOCACY_GRADUATE = 1519893345328173139 
ROLE_JUDICIAL_GRADUATE = 1519858926559039539

# --- DATA POOL ---
QUESTIONS_DATA = {
    "advocacy": {
        "sec1": [
            "Explain the legal definition of procedural hearsay and its key exceptions.",
            "How do you address a witness displaying active non-compliance during cross-examination?",
            "What criteria distinguish admissible digital evidence from unverified data logs?",
            "Detail the foundational steps required to authenticate a physical evidence exhibit.",
            "Describe how to establish an adverse witness foundation under cross-examination.",
            "What elements must be present to successfully object to a leading question on direct?",
            "Explain the difference between presenting character evidence vs. habit evidence.",
            "How do you raise a proper objection regarding a witness speculating on motives?",
            "What constitutes a layout violation sufficient to exclude a text logs exhibit?",
            "Define the legal limits of opening statements regarding unproven assertions."
        ],
        "sec2": [
            "Draft a concise opening claim outlining a severe breach of community rules.",
            "Structure a cross-examination line questioning a witness's spatial awareness.",
            "How do you rehabilitate a client's credibility after a damaging impeachment?",
            "Provide a closing argument summary emphasizing circumstantial evidence weight.",
            "How do you frame an objection when opposing counsel mischaracterizes a statement?",
            "Demonstrate the process of refreshing a witness’s memory using a past statement.",
            "How do you argue against a motion for summary dismissal of your client's claim?",
            "Formulate a foundational question series to qualify an expert code consultant.",
            "Explain how to use a prior inconsistent statement to impeach an eyewitness.",
            "Draft a mitigation statement for a defendant with no prior historical infractions."
        ],
        "sec3": [
            "Explain the ethical boundary lines regarding attorney-client confidentiality rules.",
            "How do you balance aggressive representation with mandatory courtroom decorum?",
            "What actions must you perform if you discover your witness provided false data?",
            "Define ex parte communications and explain why they are barred during trials.",
            "When can an advocate ethically recuse themselves mid-way through an active case?",
            "Describe the duties an advocate owes directly to the preservation of truth.",
            "How do you handle a conflict of interest between joint co-defendants?",
            "What is the ethical recourse if a judge exhibits clear bias against your client?",
            "Under what conditions can an advocate speak directly to an unrepresented opponent?",
            "Define the limits of public commentary an advocate can make regarding a live trial."
        ]
    },
    "judicial": {
        "sec1": [
            "Define the structural differences between civil rule claims and administrative citations.",
            "What legal principles guide a judge when balancing statutory text against past precedent?",
            "Explain the doctrine of judicial notice and when it can be applied to facts.",
            "What constitutes a prima facie showing of structural malice in an account ban appeal?",
            "Describe the standard of proof required to issue an emergency protective injunction.",
            "How does a judge determine if an ambiguous rule should be interpreted narrowly?",
            "What elements are required to establish that a claim is completely ripe for adjudication?",
            "Explain how the doctrine of laches applies to a heavily delayed rules complaint.",
            "What is the standard for declaring a filing completely frivolous on its face?",
            "Define the scope of judicial discretion when modifying standard operational bounds."
        ],
        "sec2": [
            "How do you resolve a direct conflict between an active server policy and an internal rule?",
            "Draft a standard judicial order denying a motion to compel confidential records.",
            "What criteria do you evaluate when deciding to admit heavily disputed digital logs?",
            "Structure a verbal warning to an advocate who continuously disrupts formal arguments.",
            "How do you handle an objection where both sides present valid, conflicting precedents?",
            "Write a sample dynamic ruling addressing a motion for a sudden trial continuance.",
            "How do you evaluate witness credibility when two accounts directly contradict?",
            "What steps must a judge take if a critical evidentiary file is corrupted mid-trial?",
            "Detail the methodology for calculating monetary restitution in a fraud claim.",
            "How do you handle an objection to an expert witness's technical qualifications?"
        ],
        "sec3": [
            "Identify the standard metrics used to declare a total conflict of interest requiring recusal.",
            "Explain the ethical implications of a judge holding financial stakes in a user group.",
            "What boundaries must a judge maintain regarding private discussions with server staff?",
            "How do you maintain absolute systemic neutrality when a personal friend is a litigant?",
            "Describe the judicial duty of confidentiality regarding unreleased bench deliberations.",
            "What is the appropriate response if an administrator attempts to alter your ruling?",
            "When does a judge’s public opinion across external channels cross into structural bias?",
            "Detail the ethical protocol for handling an accidental ex parte submission drop.",
            "How do you balance absolute independence with tracking high-level policy mandates?",
            "Define the limits of a judge's power to sanction bad-faith behavior in court."
        ]
    }
}

ACTIVE_TEST_SESSIONS = {}

# =================================================================
# DM APPLICATION SELECTION & RUNNER VIEWS
# =================================================================

class ApplicationEntryBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="clerk:path_selection",
        placeholder="Choose your specialized courtroom path trajectory...",
        options=[
            discord.SelectOption(label="Advocacy Division Track", value="advocacy", description="Focuses on litigation, client defense, and evidence presentation.", emoji="👔"),
            discord.SelectOption(label="Judicial Magistrate Track", value="judicial", description="Focuses on bench rulings, statutory analysis, and neutral court control.", emoji="⚖️")
        ]
    )
    async def path_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        chosen_path = select.values[0]
        
        if interaction.user.id in ACTIVE_TEST_SESSIONS:
            await interaction.response.send_message("❌ **Active Instance Alert:** You already have an evaluation running.", ephemeral=True)
            return

        pool = QUESTIONS_DATA[chosen_path]
        sec1_chosen = random.sample(pool["sec1"], 3)
        sec2_chosen = random.sample(pool["sec2"], 3)
        sec3_chosen = random.sample(pool["sec3"], 4)
        
        all_questions = sec1_chosen + sec2_chosen + sec3_chosen
        random.shuffle(all_questions)  # Keep full randomized list to present one by one

        try:
            view = DMReadyConfirmationView(interaction.client, chosen_path, all_questions, interaction.guild.id)
            embed = discord.Embed(
                title="🏛️ Application Initialization Portal",
                description=f"You have requested the **{chosen_path.upper()} TRACK** written entrance process.\n\n"
                            "Click **'I am Ready'** below to trigger the 10-question evaluation sequential delivery here in your DMs.",
                color=discord.Color.blue()
            )
            await interaction.user.send(embed=embed, view=view)
            ACTIVE_TEST_SESSIONS[interaction.user.id] = True
            await interaction.response.send_message("📥 **Application Initiated!** Please check your Direct Messages to begin.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ **Error:** Unable to open DM channel with you. Please adjust privacy updates to allow server members to message.", ephemeral=True)


class DMReadyConfirmationView(discord.ui.View):
    def __init__(self, bot, path_type, questions, guild_id):
        super().__init__(timeout=600)
        self.bot = bot
        self.path_type = path_type
        self.questions = questions
        self.guild_id = guild_id

    @discord.ui.button(label="I am Ready", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_ready(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        button.disabled = True
        await interaction.message.edit(view=self.view)
        
        applicant_answers = []
        
        for idx, question in enumerate(self.questions, start=1):
            q_embed = discord.Embed(
                title=f"📝 Assessment Question {idx} of 10",
                description=f"**{question}**\n\n*Please send your written response as a standard message below.*",
                color=discord.Color.orange()
            )
            await interaction.user.send(embed=q_embed)
            
            def check(m):
                return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)
                
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=1200)
                applicant_answers.append((question, msg.content))
            except asyncio.TimeoutError:
                await interaction.user.send("⏱️ **Session Timed Out:** You exceeded the 20-minute target limit on a single question entry.")
                if interaction.user.id in ACTIVE_TEST_SESSIONS:
                    del ACTIVE_TEST_SESSIONS[interaction.user.id]
                return
                
        # Compilation Stage Completed
        await interaction.user.send("✨ **Processing Complete:** Your profile has been formatted and submitted for high-ranking judicial review.")
        
        guild = self.bot.get_guild(self.guild_id)
        chan_id = ADVOCACY_LOG_CHANNEL_ID if self.path_type == "advocacy" else JUDICIAL_LOG_CHANNEL_ID
        log_channel = guild.get_channel(chan_id) if guild else None
        
        if log_channel:
            embed = discord.Embed(
                title=f"📋 New Court Clerk Application | {self.path_type.upper()} PATH",
                description=f"**Applicant:** {interaction.user.mention} ({interaction.user.id})\n**Status:** 🟡 Pending Department Grading",
                color=discord.Color.orange()
            )
            for idx, (q, a) in enumerate(applicant_answers, start=1):
                embed.add_field(name=f"Q{idx}: {q[:240]}", value=f"*{a[:1000]}*" if a else "*No answer*", inline=False)
                
            ping_content = f"⚖️ <@&{ROLE_BARRISTER}>" if self.path_type == "advocacy" else f"⚖️ <@&{ROLE_SENIOR_JUDGE}>"
            review_view = ApplicationReviewView(applicant_id=interaction.user.id, path_type=self.path_type)
            await log_channel.send(content=ping_content, embed=embed, view=review_view)
            
        if interaction.user.id in ACTIVE_TEST_SESSIONS:
            del ACTIVE_TEST_SESSIONS[interaction.user.id]

# =================================================================
# POST-ACCEPTANCE PROGRESSION & TRIAL MANAGEMENT
# =================================================================

class DMApplicantMockReadyView(discord.ui.View):
    def __init__(self, bot, reviewer_id, guild_id, path_type):
        super().__init__(timeout=86400)
        self.bot = bot
        self.reviewer_id = reviewer_id
        self.guild_id = guild_id
        self.path_type = path_type

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success, emoji="🚀")
    async def applicant_ready(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return
            
        applicant = guild.get_member(interaction.user.id)
        reviewer = guild.get_member(self.reviewer_id)
        
        category = guild.get_channel(MOCK_TRIAL_CATEGORY_ID)
        room_name = f"🏛️-mock-{applicant.name.lower()}" if applicant else f"🏛️-mock-{interaction.user.id}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            reviewer: discord.PermissionOverwrite(read_messages=True, send_messages=True) if reviewer else None,
            applicant: discord.PermissionOverwrite(read_messages=True, send_messages=True) if applicant else None
        }
        # Filter out empty overwrites safely
        overwrites = {k: v for k, v in overwrites.items() if k is not None}

        mock_channel = await guild.create_text_channel(name=room_name, category=category, overwrites=overwrites)
        
        embed = discord.Embed(
            title=f"🏛️ Practical Litigation Mock Trial | Room Online",
            description=f"This channel has been isolated to grade clinical skill targets.\n\n"
                        f"⚖️ **Presiding Assessor:** {reviewer.mention if reviewer else 'Staff'}\n"
                        f"🎓 **Applicant Under Profiling:** {applicant.mention if applicant else interaction.user.mention}\n"
                        f"📋 **Division Path Assignment:** `{self.path_type.upper()}`",
            color=discord.Color.gold()
        )
        
        mentions = f"{reviewer.mention if reviewer else ''} {applicant.mention if applicant else interaction.user.mention}"
        await mock_channel.send(content=mentions, embed=embed)
        await interaction.user.send(f"✅ **Room Created:** Your live practical mock simulation room has been mounted here: {mock_channel.mention}")

    @discord.ui.button(label="Not Ready", style=discord.ButtonStyle.danger, emoji="🛑")
    async def applicant_not_ready(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📌 Staged. Please alert department reviewers via server channels when you are ready to construct the trial space.", ephemeral=True)
        self.stop()


class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int, path_type: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.path_type = path_type

    def check_hierarchy_clearance(self, user: discord.Member, guild: discord.Guild) -> bool:
        chief_role = guild.get_role(ROLE_CHIEF_MAGISTRATE)
        sr_judge_role = guild.get_role(ROLE_SENIOR_JUDGE)
        
        if chief_role in user.roles or user.guild_permissions.administrator:
            return True
        if sr_judge_role in user.roles:
            return True
        return False

    @discord.ui.button(label="Accept Application", style=discord.ButtonStyle.success, custom_id="clerk_review:accept", emoji="✅")
    async def accept_app(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_hierarchy_clearance(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ **Access Denied:** Your clearance rating cannot sign off on applicant evaluations.", ephemeral=True)
            return

        await interaction.response.defer()
        applicant = interaction.guild.get_member(self.applicant_id)
        if not applicant:
            await interaction.followup.send("❌ Error: Applicant could not be located in this server map.", ephemeral=True)
            return

        edited_embed = interaction.message.embeds[0]
        edited_embed.title = f"⚖️ Application Approved | Entry Finalized"
        edited_embed.color = discord.Color.green()
        edited_embed.description = f"**Applicant:** {applicant.mention}\n**Authorized Verdict:** ✅ Accepted into Mock Trial Stage\n**Reviewing Officer:** {interaction.user.mention}"
        await interaction.message.edit(embed=edited_embed, view=None)

        try:
            dm_embed = discord.Embed(
                title="⚖️ Court Clerk Assessment Passed!",
                description=f"Congratulations, your written evaluation for the **{self.path_type.upper()}** division has been accepted.\n"
                            f"Are you ready to advance directly to your active live practical mock trial?",
                color=discord.Color.green()
            )
            view = DMApplicantMockReadyView(interaction.client, interaction.user.id, interaction.guild.id, self.path_type)
            await applicant.send(embed=dm_embed, view=view)
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Deny & Reject", style=discord.ButtonStyle.danger, custom_id="clerk_review:deny", emoji="❌")
    async def reject_app(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.check_hierarchy_clearance(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ **Access Denied:** Your clearance rating cannot sign off on applicant evaluations.", ephemeral=True)
            return

        await interaction.response.defer()
        applicant = interaction.guild.get_member(self.applicant_id)
        
        edited_embed = interaction.message.embeds[0]
        edited_embed.title = f"⚖️ Application Rejected & Shelved"
        edited_embed.color = discord.Color.red()
        edited_embed.description = f"**Applicant:** <@{self.applicant_id}>\n**Authorized Verdict:** ❌ Assessment Failed / Dismissed\n**Reviewing Officer:** {interaction.user.mention}"
        await interaction.message.edit(embed=edited_embed, view=None)

        if applicant:
            try:
                dm_embed = discord.Embed(
                    title="⚖️ Department Notification Desk",
                    description=f"We regret to inform you that your evaluation profile for the {self.path_type.title()} division was rejected at this time.",
                    color=discord.Color.red()
                )
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                pass


class MockTrialAssessmentView(discord.ui.View):
    def __init__(self, applicant_id: int, path_type: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.path_type = path_type

    @discord.ui.button(label="Perform Well", style=discord.ButtonStyle.success, custom_id="mock_assessment:pass", emoji="⭐")
    async def choice_well(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)

        target_role_id = ROLE_ADVOCACY_GRADUATE if self.path_type == "advocacy" else ROLE_JUDICIAL_GRADUATE
        target_role = guild.get_role(target_role_id)

        if applicant and target_role:
            try:
                await applicant.add_roles(target_role)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ Notice: Bot lacks administrative hierarchy clearance to apply that role.", ephemeral=True)

        edited_embed = interaction.message.embeds[0]
        edited_embed.title = "✨ Practical Trial Closed: Outstanding Merit"
        edited_embed.color = discord.Color.green()
        edited_embed.description = f"**Assessed Member:** <@{self.applicant_id}>\n**Verdict:** 🎉 Performance Met Exceptional Standard. Role deployed.\n**Presiding Assessor:** {interaction.user.mention}\n\n*🧹 This room will self-destruct in 5 seconds...*"
        await interaction.message.edit(embed=edited_embed, view=None)

        if applicant:
            try:
                msg = discord.Embed(
                    title="⚖️ High Court Graduation Notification",
                    description="Your performance during the mock litigation room simulation was deemed exemplary. Your legal authorization roles are officially active!",
                    color=discord.Color.green()
                )
                await applicant.send(embed=msg)
            except discord.Forbidden:
                pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Mock trial completed successfully.")
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Unsatisfactory Performance", style=discord.ButtonStyle.danger, custom_id="mock_assessment:fail", emoji="⚠️")
    async def choice_poor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        applicant = interaction.guild.get_member(self.applicant_id)

        edited_embed = interaction.message.embeds[0]
        edited_embed.title = "🚫 Practical Trial Closed: Revision Required"
        edited_embed.color = discord.Color.red()
        edited_embed.description = f"**Assessed Member:** <@{self.applicant_id}>\n**Verdict:** ❌ Target metrics were missed. Remedial training assigned.\n**Presiding Assessor:** {interaction.user.mention}\n\n*🧹 This room will self-destruct in 5 seconds...*"
        await interaction.message.edit(embed=edited_embed, view=None)

        if applicant:
            try:
                msg = discord.Embed(
                    title="⚖️ Court Room Performance Debriefing",
                    description="Your practical courtroom simulation handling missed necessary structural benchmarks. Review procedures and coordinate with your department senior for rescheduled profiling.",
                    color=discord.Color.red()
                )
                await applicant.send(embed=msg)
            except discord.Forbidden:
                pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Mock trial completed - performance unsatisfactory.")
        except discord.Forbidden:
            pass

# =================================================================
# FIXED COMMAND REGISTRATION PIPELINE
# =================================================================

def setup_court_testing(bot: commands.Bot):

    @bot.command(name="trialcourt")
    @commands.has_permissions(administrator=True)
    async def deploy_trial_board(ctx):
        """Spawns the singular persistent path examination entry point."""
        target_chan = ctx.guild.get_channel(TESTING_BOARD_CHANNEL_ID)
        if not target_chan:
            await ctx.send("❌ Setup Path Error: Invalid testing core channel configured.")
            return

        embed = discord.Embed(
            title="🏛️ Court Clerk Assessment Academy Board",
            description="Welcome to the judicial verification terminal. Selected court clerks testing for practical advancement or litigation credentials must pick their structural route below.\n\n"
                        "⚠️ **Rules & Guidelines:**\n"
                        "* Selecting a path instantly constructs a unique, highly randomized 10-question text profile tracking three distinct sections.\n"
                        "* Forms will automatically cascade to your direct messages upon path tracking updates selection.",
            color=discord.Color.dark_blue()
        )
        embed.set_footer(text="System Monitoring Active | Chief Magistrate Overseer Network")
        
        await target_chan.send(embed=embed, view=ApplicationEntryBoardView())
        await ctx.send(f"✅ Master Evaluation Terminal mounted securely in {target_chan.mention}!")

    @bot.command(name="mocktrial")
    async def start_mock_trial(ctx, applicant: discord.Member, path_type: str):
        """Deploys a localized text courtroom isolating the assessor and applicant manually."""
        chief_role = ctx.guild.get_role(ROLE_CHIEF_MAGISTRATE)
        sr_judge = ctx.guild.get_role(ROLE_SENIOR_JUDGE)
        
        if not (chief_role in ctx.author.roles or sr_judge in ctx.author.roles or ctx.author.guild_permissions.administrator):
            await ctx.send("❌ **Clearance Denied:** Only verified judicial officers can initiate active live trial simulations.")
            return

        clean_path = path_type.lower().strip()
        if clean_path not in ["advocacy", "judicial"]:
            await ctx.send("❌ Invalid assignment path choice. Specify matching value: `advocacy` or `judicial`.")
            return

        category = ctx.guild.get_channel(MOCK_TRIAL_CATEGORY_ID)
        room_name = f"🏛️-mock-{applicant.name.lower()}"

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            applicant: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        mock_channel = await ctx.guild.create_text_channel(name=room_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title=f"🏛️ Practical Litigation Mock Trial | Room Online",
            description=f"This channel has been isolated to grade clinical skill targets.\n\n"
                        f"⚖️ **Presiding Assessor:** {ctx.author.mention}\n"
                        f"🎓 **Applicant Under Profiling:** {applicant.mention}\n"
                        f"📋 **Division Path Assignment:** `{clean_path.upper()}`",
            color=discord.Color.gold()
        )
        await mock_channel.send(content=f"{ctx.author.mention} {applicant.mention}", embed=embed)
        await ctx.send(f"✅ Practical simulation room constructed successfully: {mock_channel.mention}")

    @bot.command(name="callwitness")
    async def call_witness_to_mock(ctx, member: discord.Member):
        """Allows an active assessor to dynamically bring a witness or assistant into the channel."""
        chief_role = ctx.guild.get_role(ROLE_CHIEF_MAGISTRATE)
        sr_judge = ctx.guild.get_role(ROLE_SENIOR_JUDGE)
        
        if not (chief_role in ctx.author.roles or sr_judge in ctx.author.roles or ctx.author.guild_permissions.administrator):
            await ctx.send("❌ Command locked to running judicial simulation officers.")
            return

        if "mock-" not in ctx.channel.name:
            await ctx.send("❌ System Protection: Witness pings are locked strictly within active mock trial channels.")
            return

        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        embed = discord.Embed(
            title="🔔 Subpoena Issued",
            description=f"{member.mention} has been authorized to enter this trial room and is clear to speak by order of the Court.",
            color=discord.Color.blue()
        )
        await ctx.channel.send(content=member.mention, embed=embed)

    @bot.command(name="endtrial")
    async def complete_mock_trial(ctx, applicant: discord.Member, path_type: str):
        """Closes the practical trial and drops the final decision card for the assessor."""
        chief_role = ctx.guild.get_role(ROLE_CHIEF_MAGISTRATE)
        sr_judge = ctx.guild.get_role(ROLE_SENIOR_JUDGE)
        
        if not (chief_role in ctx.author.roles or sr_judge in ctx.author.roles or ctx.author.guild_permissions.administrator):
            await ctx.send("❌ Verification error: Assessors only.")
            return

        clean_path = path_type.lower().strip()

        embed = discord.Embed(
            title="⚖️ Practical Simulation Room Evaluation Card",
            description=f"Assess the applicant's courtroom management workflow, confidence, rule mastery, and clarity below.\n\n"
                        f"**Applicant:** {applicant.mention}\n"
                        f"**Path Track:** `{clean_path.upper()}`",
            color=discord.Color.purple()
        )
        
        grading_view = MockTrialAssessmentView(applicant_id=applicant.id, path_type=clean_path)
        await ctx.send(embed=embed, view=grading_view)
