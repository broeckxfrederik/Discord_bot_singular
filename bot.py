"""
Belgium War Era - Discord Welcome & Verification Bot

This bot manages server entry through a ticket-based verification system.
New members select their status (Citizen, Foreigner, or Emergency Embassy Request)
and are processed by designated moderators.

Features:
- Automated welcome messages with interactive buttons
- Private ticket channels for verification requests
- Role-based moderation with different handlers per request type
- Government log channel for tracking all decisions
- Automatic role assignment upon approval
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import datetime
from dotenv import load_dotenv



# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG_FILE = "config.json"

# Default configuration - used when config.json doesn't exist or is missing keys
DEFAULT_CONFIG = {
    "welcome_channel_id": None,          # Channel where welcome messages are sent
    "verification_category_id": None,     # Category for ticket channels
    "log_channel_id": None,               # Channel for government decision logs
    "roles": {
        "belgian": None,                  # Role granted to approved citizens
        "foreigner": None,                # Role granted to approved foreigners
        "border_control": None,           # Moderators for citizen/foreigner requests
        "minister_foreign_affairs": None, # Embassy request handler
        "president": None,                # Embassy request handler
        "vice_president": None,           # Embassy request handler
        "government": None                # Can view decision log channel
    },
    "welcome_message": "# Welcome to the Official Belgium War Era Server!\n\n"
                       "Greetings, traveler! You have arrived at the gates of Belgium.\n\n"
                       "Please select your status below to proceed with verification:",
    "ticket_counter": 0  # Increments for each new ticket (used in channel names)
}


def load_config() -> dict:
    """
    Load configuration from JSON file.

    If the file exists, loads it and merges with defaults to ensure
    all required keys exist. If not, returns a copy of defaults.
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Merge with defaults for any missing keys (handles config upgrades)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to JSON file with pretty formatting."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


# =============================================================================
# BOT INITIALIZATION
# =============================================================================

# Required intents for the bot to function
intents = discord.Intents.default()
intents.members = True          # Required: Track member joins
intents.message_content = True  # Required: Read message content
intents.guilds = True           # Required: Access guild information

bot = commands.Bot(command_prefix="!", intents=intents)
config = load_config()


# =============================================================================
# WELCOME BUTTON VIEW
# =============================================================================

class WelcomeView(discord.ui.View):
    """
    Persistent view containing the three verification buttons.

    Using timeout=None and custom_id makes these buttons persist
    across bot restarts - they'll still work after the bot reconnects.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Citizen",
        style=discord.ButtonStyle.success,
        custom_id="welcome_citizen",
        emoji="🇧🇪"
    )
    async def citizen_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle citizen verification request."""
        await create_verification_channel(interaction, "citizen")

    @discord.ui.button(
        label="Foreigner",
        style=discord.ButtonStyle.primary,
        custom_id="welcome_foreigner",
        emoji="🌍"
    )
    async def foreigner_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle foreigner verification request."""
        await create_verification_channel(interaction, "foreigner")

    @discord.ui.button(
        label="Emergency Embassy Request",
        style=discord.ButtonStyle.danger,
        custom_id="welcome_embassy",
        emoji="🚨"
    )
    async def embassy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle emergency embassy request."""
        await create_verification_channel(interaction, "embassy")


# =============================================================================
# TICKET CHANNEL CREATION
# =============================================================================

async def create_verification_channel(interaction: discord.Interaction, request_type: str) -> None:
    """
    Create a private verification ticket channel for the user.

    Args:
        interaction: The button interaction from the user
        request_type: One of "citizen", "foreigner", or "embassy"

    The channel is only visible to:
    - The requesting user
    - The bot itself
    - The relevant moderator roles (Border Control or Embassy handlers)
    """
    global config
    config = load_config()

    guild = interaction.guild
    user = interaction.user

    # Generate unique ticket ID
    config["ticket_counter"] += 1
    ticket_id = config["ticket_counter"]
    save_config(config)

    # Configure channel properties based on request type
    if request_type == "citizen":
        channel_name = f"citizen-{ticket_id}-{user.name}"
        role_ids = [config["roles"]["border_control"]]
        embed_color = discord.Color.green()
        request_title = "Citizenship Verification Request"
    elif request_type == "foreigner":
        channel_name = f"foreigner-{ticket_id}-{user.name}"
        role_ids = [config["roles"]["border_control"]]
        embed_color = discord.Color.blue()
        request_title = "Foreigner Verification Request"
    else:  # embassy
        channel_name = f"embassy-{ticket_id}-{user.name}"
        # Embassy requests notify multiple high-level roles
        role_ids = [
            config["roles"]["minister_foreign_affairs"],
            config["roles"]["president"],
            config["roles"]["vice_president"]
        ]
        embed_color = discord.Color.red()
        request_title = "Emergency Embassy Request"

    # Sanitize channel name (Discord requires lowercase, no spaces, max 100 chars)
    channel_name = channel_name.lower().replace(" ", "-")[:100]

    # Get the category to create the channel in (if configured)
    category = None
    if config["verification_category_id"]:
        category = guild.get_channel(config["verification_category_id"])

    # Set up channel permissions
    # By default, hide from everyone, then explicitly allow specific users/roles
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,   # Required to delete the channel later
            manage_messages=True,
            embed_links=True
        )
    }

    # Grant access to the relevant moderator roles
    for role_id in role_ids:
        if role_id:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

    # Check if bot has permission to create channels in the category
    if category:
        bot_permissions = category.permissions_for(guild.me)
        if not bot_permissions.manage_channels:
            await interaction.response.send_message(
                f"I don't have permission to create channels in the **{category.name}** category.\n\n"
                "**Fix:** Go to the category settings > Permissions > Add the bot role with 'Manage Channels' enabled.",
                ephemeral=True
            )
            return

    # Create the ticket channel
    try:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            # Store metadata in topic for later retrieval by /approve and /deny
            topic=f"Verification request by {user.name} | Type: {request_type} | ID: {ticket_id} | User ID: {user.id}"
        )
    except discord.Forbidden as e:
        error_msg = (
            "I don't have permission to create channels.\n\n"
            "**Possible fixes:**\n"
            "• Ensure the bot has 'Manage Channels' permission server-wide\n"
        )
        if category:
            error_msg += f"• Add the bot to the **{category.name}** category with 'Manage Channels' permission\n"
        error_msg += f"\n**Error:** {e}"
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    # Build list of role mentions to ping
    role_mentions = []
    for role_id in role_ids:
        if role_id:
            role = guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)

    # Create the ticket embed with request details
    embed = discord.Embed(
        title=f"📋 {request_title}",
        description=f"**User:** {user.mention}\n**Request Type:** {request_type.title()}\n**Ticket ID:** #{ticket_id}",
        color=embed_color,
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="Instructions for Moderators",
        value="Use `/approve` to approve this request\nUse `/deny` to deny this request",
        inline=False
    )
    embed.set_footer(text=f"User ID: {user.id}")

    # Send the ticket message, pinging relevant moderators
    mention_text = " ".join(role_mentions) if role_mentions else ""
    await channel.send(content=mention_text, embed=embed)

    # Confirm to the user (only they can see this response)
    await interaction.response.send_message(
        f"Your verification channel has been created: {channel.mention}\n"
        "Please wait for a moderator to review your request.",
        ephemeral=True
    )


# =============================================================================
# BOT EVENTS
# =============================================================================

@bot.event
async def on_ready():
    """
    Called when the bot successfully connects to Discord.

    This registers the persistent button view and syncs slash commands.
    """
    print(f"✅ {bot.user} is now online!")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")

    # Register the persistent view so buttons work after restart
    bot.add_view(WelcomeView())

    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_member_join(member: discord.Member):
    """
    Send a welcome message when a new member joins the server.

    The message includes the configured welcome text and the
    three verification buttons (Citizen, Foreigner, Embassy).
    """
    global config
    config = load_config()

    # Skip if no welcome channel is configured
    if not config["welcome_channel_id"]:
        return

    channel = member.guild.get_channel(config["welcome_channel_id"])
    if not channel:
        return

    # Create the welcome embed
    embed = discord.Embed(
        title="🇧🇪 Welcome to Belgium!",
        description=config["welcome_message"],
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{member.guild.member_count}")

    # Send welcome message with verification buttons
    await channel.send(content=member.mention, embed=embed, view=WelcomeView())


# =============================================================================
# SETUP COMMANDS (Administrator Only)
# =============================================================================

@bot.tree.command(name="setup-roles", description="Configure the roles for the verification system")
@app_commands.describe(
    belgian="The role given to approved citizens",
    foreigner="The role given to approved foreigners",
    border_control="The role that handles citizen/foreigner requests",
    minister="The Minister of Foreign Affairs role",
    president="The President role",
    vice_president="The Vice President role",
    government="The role that can see the decision log channel"
)
@app_commands.default_permissions(administrator=True)
async def setup_roles(
    interaction: discord.Interaction,
    belgian: discord.Role = None,
    foreigner: discord.Role = None,
    border_control: discord.Role = None,
    minister: discord.Role = None,
    president: discord.Role = None,
    vice_president: discord.Role = None,
    government: discord.Role = None
):
    """
    Configure which roles are used by the verification system.

    All parameters are optional - only provided roles will be updated.
    """
    global config
    config = load_config()

    updated = []

    # Update each role if provided
    if belgian:
        config["roles"]["belgian"] = belgian.id
        updated.append(f"Belgian: {belgian.mention}")
    if foreigner:
        config["roles"]["foreigner"] = foreigner.id
        updated.append(f"Foreigner: {foreigner.mention}")
    if border_control:
        config["roles"]["border_control"] = border_control.id
        updated.append(f"Border Control: {border_control.mention}")
    if minister:
        config["roles"]["minister_foreign_affairs"] = minister.id
        updated.append(f"Minister of Foreign Affairs: {minister.mention}")
    if president:
        config["roles"]["president"] = president.id
        updated.append(f"President: {president.mention}")
    if vice_president:
        config["roles"]["vice_president"] = vice_president.id
        updated.append(f"Vice President: {vice_president.mention}")
    if government:
        config["roles"]["government"] = government.id
        updated.append(f"Government: {government.mention}")

    save_config(config)

    # Send confirmation
    if updated:
        embed = discord.Embed(
            title="✅ Roles Updated",
            description="\n".join(updated),
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="ℹ️ No Changes",
            description="No roles were provided to update.",
            color=discord.Color.orange()
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="setup-channel", description="Configure the welcome and verification channels")
@app_commands.describe(
    welcome_channel="The channel where welcome messages are sent",
    verification_category="The category where verification tickets are created",
    log_channel="The channel where approval/denial decisions are logged (visible to Government role)"
)
@app_commands.default_permissions(administrator=True)
async def setup_channels(
    interaction: discord.Interaction,
    welcome_channel: discord.TextChannel = None,
    verification_category: discord.CategoryChannel = None,
    log_channel: discord.TextChannel = None
):
    """
    Configure which channels are used by the verification system.

    All parameters are optional - only provided channels will be updated.
    """
    global config
    config = load_config()

    updated = []

    if welcome_channel:
        config["welcome_channel_id"] = welcome_channel.id
        updated.append(f"Welcome Channel: {welcome_channel.mention}")
    if verification_category:
        config["verification_category_id"] = verification_category.id
        updated.append(f"Verification Category: {verification_category.name}")
    if log_channel:
        config["log_channel_id"] = log_channel.id
        updated.append(f"Log Channel: {log_channel.mention}")

    save_config(config)

    if updated:
        embed = discord.Embed(
            title="✅ Channels Updated",
            description="\n".join(updated),
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="ℹ️ No Changes",
            description="No channels were provided to update.",
            color=discord.Color.orange()
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="setup-message", description="Set the welcome message")
@app_commands.describe(message="The welcome message (supports markdown)")
@app_commands.default_permissions(administrator=True)
async def setup_message(interaction: discord.Interaction, message: str):
    """Set the custom welcome message displayed to new members."""
    global config
    config = load_config()

    config["welcome_message"] = message
    save_config(config)

    embed = discord.Embed(
        title="✅ Welcome Message Updated",
        description=f"New message:\n\n{message}",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="test-welcome", description="Test the welcome message")
@app_commands.default_permissions(administrator=True)
async def test_welcome(interaction: discord.Interaction):
    """Preview the welcome message without actually welcoming anyone."""
    global config
    config = load_config()

    embed = discord.Embed(
        title="🏰 Welcome to Belgium!",
        description=config["welcome_message"],
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text="This is a test message")

    await interaction.response.send_message(
        content="**Test Welcome Message:**",
        embed=embed,
        view=WelcomeView(),
        ephemeral=True
    )


@bot.tree.command(name="view-config", description="View the current bot configuration")
@app_commands.default_permissions(administrator=True)
async def view_config(interaction: discord.Interaction):
    """Display all current configuration settings."""
    global config
    config = load_config()

    guild = interaction.guild

    # Format role configuration
    role_info = []
    for role_name, role_id in config["roles"].items():
        display_name = role_name.replace('_', ' ').title()
        if role_id:
            role = guild.get_role(role_id)
            role_info.append(f"**{display_name}:** {role.mention if role else 'Not found'}")
        else:
            role_info.append(f"**{display_name}:** Not set")

    # Format channel configuration
    channel_info = []

    if config["welcome_channel_id"]:
        ch = guild.get_channel(config["welcome_channel_id"])
        channel_info.append(f"**Welcome Channel:** {ch.mention if ch else 'Not found'}")
    else:
        channel_info.append("**Welcome Channel:** Not set")

    if config["verification_category_id"]:
        cat = guild.get_channel(config["verification_category_id"])
        channel_info.append(f"**Verification Category:** {cat.name if cat else 'Not found'}")
    else:
        channel_info.append("**Verification Category:** Not set")

    if config.get("log_channel_id"):
        log_ch = guild.get_channel(config["log_channel_id"])
        channel_info.append(f"**Log Channel:** {log_ch.mention if log_ch else 'Not found'}")
    else:
        channel_info.append("**Log Channel:** Not set")

    embed = discord.Embed(
        title="⚙️ Bot Configuration",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Roles", value="\n".join(role_info), inline=False)
    embed.add_field(name="Channels", value="\n".join(channel_info), inline=False)
    embed.add_field(name="Ticket Counter", value=f"#{config['ticket_counter']}", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# =============================================================================
# MODERATION COMMANDS
# =============================================================================

@bot.tree.command(name="approve", description="Approve a verification request")
@app_commands.describe(reason="Internal reason for approval (not shown to user)")
async def approve(interaction: discord.Interaction, reason: str = "No reason provided"):
    """
    Approve a verification request in the current ticket channel.

    This will:
    1. Assign the appropriate role to the user (Belgian/Foreigner)
    2. Notify the user of approval
    3. Log the decision to the government log channel
    4. Delete the ticket channel after 30 seconds

    The reason is only visible in the log channel, not to the user.
    """
    global config
    config = load_config()

    channel = interaction.channel

    # Verify this is a ticket channel
    if not channel.name.startswith(("citizen-", "foreigner-", "embassy-")):
        await interaction.response.send_message(
            "This command can only be used in verification channels.",
            ephemeral=True
        )
        return

    # Check if the user has permission to moderate
    mod_roles = [
        config["roles"]["border_control"],
        config["roles"]["minister_foreign_affairs"],
        config["roles"]["president"],
        config["roles"]["vice_president"]
    ]

    user_role_ids = [role.id for role in interaction.user.roles]
    has_permission = any(role_id in user_role_ids for role_id in mod_roles if role_id)

    if not has_permission and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You don't have permission to use this command.",
            ephemeral=True
        )
        return

    # Extract user ID from channel topic (set during channel creation)
    topic = channel.topic or ""
    user_id = None
    for part in topic.split("|"):
        if "User ID:" in part:
            try:
                user_id = int(part.split(":")[-1].strip())
            except ValueError:
                pass

    if not user_id:
        await interaction.response.send_message(
            "Could not find the user for this request. Please check manually.",
            ephemeral=True
        )
        return

    member = interaction.guild.get_member(user_id)
    if not member:
        await interaction.response.send_message(
            "The user is no longer in the server.",
            ephemeral=True
        )
        return

    # Determine which role to grant based on request type
    request_type = channel.name.split("-")[0]
    role_to_give = None

    if request_type == "citizen":
        role_to_give = interaction.guild.get_role(config["roles"]["belgian"])
    elif request_type == "foreigner":
        role_to_give = interaction.guild.get_role(config["roles"]["foreigner"])
    # Embassy requests don't grant a role

    # Attempt to assign the role
    if role_to_give:
        try:
            await member.add_roles(role_to_give)
        except discord.Forbidden:
            # This usually means the bot's role is lower than the target role
            await interaction.response.send_message(
                f"I don't have permission to assign the {role_to_give.name} role. "
                "Make sure my bot role is **higher** than this role in Server Settings > Roles.",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to assign role: {e}",
                ephemeral=True
            )
            return

    # Notify the user of approval (reason is NOT included)
    user_embed = discord.Embed(
        title="✅ Request Approved!",
        description=f"Your {request_type} verification request has been approved!",
        color=discord.Color.green()
    )
    if role_to_give:
        user_embed.add_field(name="Role Granted", value=role_to_give.mention, inline=False)
    user_embed.set_footer(text="This channel will be deleted in 30 seconds.")

    await channel.send(content=member.mention, embed=user_embed)

    # Log to the government log channel (includes reason)
    log_posted = False
    if config.get("log_channel_id"):
        log_channel = interaction.guild.get_channel(config["log_channel_id"])
        if log_channel:
            try:
                log_embed = discord.Embed(
                    title="✅ Verification Approved",
                    description=f"**User:** {member.mention} ({member.name})\n"
                               f"**Type:** {request_type.title()}\n"
                               f"**Reason:** {reason}",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.set_footer(
                    text=f"Approved by {interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url
                )
                if role_to_give:
                    log_embed.add_field(name="Role Granted", value=role_to_give.mention, inline=True)
                await log_channel.send(embed=log_embed)
                log_posted = True
            except discord.Forbidden:
                print("Cannot post to log channel - missing permissions")
            except discord.HTTPException as e:
                print(f"Failed to post to log channel: {e}")
        else:
            print(f"Log channel not found: {config['log_channel_id']}")

    # Confirm to the moderator (ephemeral)
    mod_embed = discord.Embed(
        title="📝 Approval Logged",
        description=f"**User:** {member.mention}\n**Type:** {request_type}\n**Reason:** {reason}",
        color=discord.Color.green()
    )
    mod_embed.set_footer(text=f"Approved by {interaction.user.name}")

    # Warn if log posting failed
    if not log_posted and config.get("log_channel_id"):
        mod_embed.add_field(name="⚠️ Warning", value="Could not post to log channel", inline=False)

    await interaction.response.send_message(embed=mod_embed, ephemeral=True)

    # Delete the ticket channel after a delay
    await asyncio.sleep(30)
    try:
        await channel.delete(reason=f"Verification approved by {interaction.user.name}")
    except (discord.NotFound, discord.Forbidden) as e:
        print(f"Could not delete channel: {e}")


@bot.tree.command(name="deny", description="Deny a verification request")
@app_commands.describe(reason="Internal reason for denial (not shown to user)")
async def deny(interaction: discord.Interaction, reason: str = "No reason provided"):
    """
    Deny a verification request in the current ticket channel.

    This will:
    1. Notify the user of denial (without showing reason)
    2. Log the decision with reason to the government log channel
    3. Delete the ticket channel after 30 seconds
    """
    global config
    config = load_config()

    channel = interaction.channel

    # Verify this is a ticket channel
    if not channel.name.startswith(("citizen-", "foreigner-", "embassy-")):
        await interaction.response.send_message(
            "This command can only be used in verification channels.",
            ephemeral=True
        )
        return

    # Check if the user has permission to moderate
    mod_roles = [
        config["roles"]["border_control"],
        config["roles"]["minister_foreign_affairs"],
        config["roles"]["president"],
        config["roles"]["vice_president"]
    ]

    user_role_ids = [role.id for role in interaction.user.roles]
    has_permission = any(role_id in user_role_ids for role_id in mod_roles if role_id)

    if not has_permission and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You don't have permission to use this command.",
            ephemeral=True
        )
        return

    # Extract user ID from channel topic
    topic = channel.topic or ""
    user_id = None
    for part in topic.split("|"):
        if "User ID:" in part:
            try:
                user_id = int(part.split(":")[-1].strip())
            except ValueError:
                pass

    member = interaction.guild.get_member(user_id) if user_id else None
    request_type = channel.name.split("-")[0]

    # Notify the user of denial (reason is NOT included)
    user_embed = discord.Embed(
        title="❌ Request Denied",
        description=f"Your {request_type} verification request has been denied.",
        color=discord.Color.red()
    )
    user_embed.set_footer(text="This channel will be deleted in 30 seconds.")

    if member:
        await channel.send(content=member.mention, embed=user_embed)
    else:
        await channel.send(embed=user_embed)

    # Log to the government log channel (includes reason)
    log_posted = False
    if config.get("log_channel_id"):
        log_channel = interaction.guild.get_channel(config["log_channel_id"])
        if log_channel:
            try:
                log_embed = discord.Embed(
                    title="❌ Verification Denied",
                    description=f"**User:** {member.mention if member else 'Unknown'} "
                               f"({member.name if member else 'Unknown'})\n"
                               f"**Type:** {request_type.title()}\n"
                               f"**Reason:** {reason}",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                if member:
                    log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.set_footer(
                    text=f"Denied by {interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url
                )
                await log_channel.send(embed=log_embed)
                log_posted = True
            except discord.Forbidden:
                print("Cannot post to log channel - missing permissions")
            except discord.HTTPException as e:
                print(f"Failed to post to log channel: {e}")
        else:
            print(f"Log channel not found: {config['log_channel_id']}")

    # Confirm to the moderator (ephemeral)
    mod_embed = discord.Embed(
        title="📝 Denial Logged",
        description=f"**User:** {member.mention if member else 'Unknown'}\n"
                   f"**Type:** {request_type}\n"
                   f"**Reason:** {reason}",
        color=discord.Color.red()
    )
    mod_embed.set_footer(text=f"Denied by {interaction.user.name}")

    # Warn if log posting failed
    if not log_posted and config.get("log_channel_id"):
        mod_embed.add_field(name="⚠️ Warning", value="Could not post to log channel", inline=False)

    await interaction.response.send_message(embed=mod_embed, ephemeral=True)

    # Delete the ticket channel after a delay
    await asyncio.sleep(30)
    try:
        await channel.delete(reason=f"Verification denied by {interaction.user.name}")
    except (discord.NotFound, discord.Forbidden) as e:
        print(f"Could not delete channel: {e}")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys
    load_dotenv()

    # Get bot token from environment variable or command line argument
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token and len(sys.argv) > 1:
        token = sys.argv[1]

    if not token:
        print("❌ No bot token provided!")
        print("Set the DISCORD_BOT_TOKEN environment variable or pass it as an argument:")
        print("  python bot.py YOUR_BOT_TOKEN")
        sys.exit(1)

    bot.run(token)
