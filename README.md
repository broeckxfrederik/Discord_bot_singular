# Belgium War Era - Welcome & Verification Bot

A Discord bot for managing server entry through a ticket-based verification system. New members select their status (Citizen, Foreigner, or Emergency Embassy Request) and are processed by designated moderators.

## Features

- **Automated Welcome System** - Greets new members with an embedded message and interactive buttons
- **Ticket-Based Verification** - Creates private channels for each verification request
- **Role-Based Moderation** - Different roles handle different request types
- **Hidden Reasoning** - Moderators can approve/deny with internal notes not visible to users
- **Government Decision Log** - All approvals/denials are logged to a private channel visible only to the Government role
- **Automatic Role Assignment** - Approved citizens get "Belgian" role, foreigners get "Foreigner" role

## Requirements

- Python 3.8+
- discord.py 2.3.0+

## Installation

1. **Clone/Download the project**

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**
   ```bash
   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Discord Bot Setup

### Create the Bot Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and name it
3. Navigate to **Bot** tab and click **Add Bot**
4. Enable these **Privileged Gateway Intents**:
   - Server Members Intent
   - Message Content Intent
5. Click **Reset Token** and save your token securely

### Generate Invite Link

1. Go to **OAuth2 > URL Generator**
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select permissions:
   - Manage Channels
   - Manage Roles
   - Send Messages
   - Embed Links
   - Mention Everyone
   - Read Message History
4. Use the generated URL to invite the bot

### Role Hierarchy (Important!)

After inviting the bot, you **must** configure the role hierarchy:

1. Go to **Server Settings > Roles**
2. Drag the bot's role **above** the Belgian and Foreigner roles
3. Discord prevents bots from assigning roles equal to or higher than their own

```
Role Hierarchy (top = highest):
─────────────────────────────
  Admin
  Bot Role        ← Must be here
  Government
  Border Control
  Belgian         ← Bot assigns this
  Foreigner       ← Bot assigns this
  @everyone
```

## Running the Bot

```bash
# Option 1: Pass token as argument
python bot.py YOUR_BOT_TOKEN

# Option 2: Use environment variable
# Windows
set DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN
python bot.py

# Linux/Mac
export DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN
python bot.py
```

### Successful Startup

When the bot starts correctly, you should see:
```
✅ BotName#1234 is now online!
📊 Connected to 1 guild(s)
🔄 Synced 7 command(s)
```

## Commands

### Setup Commands (Administrator Only)

| Command | Description |
|---------|-------------|
| `/setup-roles` | Configure verification system roles (including Government) |
| `/setup-channel` | Set welcome channel, ticket category, and log channel |
| `/setup-message` | Customize the welcome message |
| `/test-welcome` | Preview the welcome message |
| `/view-config` | Display current configuration |

### Moderation Commands

| Command | Description |
|---------|-------------|
| `/approve [reason]` | Approve a verification request |
| `/deny [reason]` | Deny a verification request |

The `reason` parameter is logged to the Government log channel but **never** shown to the requesting user.

## Configuration

### Roles to Configure

| Role | Purpose |
|------|---------|
| Belgian | Assigned to approved citizens |
| Foreigner | Assigned to approved foreigners |
| Border Control | Handles Citizen and Foreigner requests |
| Minister of Foreign Affairs | Handles Emergency Embassy requests |
| President | Handles Emergency Embassy requests |
| Vice President | Handles Emergency Embassy requests |
| Government | Can view the decision log channel |

### Channels to Configure

| Channel | Purpose |
|---------|---------|
| Welcome Channel | Where welcome messages are sent to new members |
| Verification Category | Category where ticket channels are created |
| Log Channel | Private channel for logging all approval/denial decisions (visible to Government role) |

### Example Setup

```
/setup-channel welcome_channel:#verification verification_category:Tickets log_channel:#verification-logs
/setup-roles belgian:@Belgian foreigner:@Foreigner border_control:@Border Control government:@Government
/setup-roles minister:@Minister of Foreign Affairs president:@President vice_president:@Vice President
```

## Verification Flow

```
┌─────────────────┐
│  User Joins     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Welcome Message │ (with 3 buttons)
└────────┬────────┘
         ▼
┌─────────────────┐
│ User Clicks     │ Citizen / Foreigner / Embassy
│ Button          │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Ticket Channel  │ (private, visible to user + mods)
│ Created         │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Moderators      │ Border Control or Embassy handlers
│ Pinged          │
└────────┬────────┘
         ▼
┌─────────────────┐
│ /approve or     │ (with optional reason)
│ /deny           │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Decision Logged │ → Government log channel
└────────┬────────┘
         ▼
┌─────────────────┐
│ User Notified   │ + Role assigned (if approved)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Channel Deleted │ (after 30 seconds)
└─────────────────┘
```

### Button Types

| Button | Channel Prefix | Roles Notified | Role Granted |
|--------|---------------|----------------|--------------|
| Citizen | `citizen-` | Border Control | Belgian |
| Foreigner | `foreigner-` | Border Control | Foreigner |
| Emergency Embassy | `embassy-` | Minister, President, VP | None |

## Server Structure Recommendation

```
Server
├── Public (Category)
│   └── #information (read-only)
├── Verification (Category)
│   └── #verification (welcome channel)
├── Government (Category) - visible only to @Government
│   └── #verification-logs (decision log channel)
└── Tickets (Category)
    └── [Auto-created ticket channels]
```

### Permissions Setup

| Role | Permissions |
|------|-------------|
| `@everyone` | Can only see #information |
| `@Belgian` / `@Foreigner` | Can see additional server channels |
| `@Government` | Can see #verification-logs with all decisions and reasons |
| Ticket channels | Only visible to the requester and assigned moderators |

## File Structure

```
discord_bot_v2/
├── bot.py           # Main bot code
├── config.json      # Auto-generated configuration (created on first run)
├── requirements.txt # Python dependencies
└── README.md        # This file
```

## Troubleshooting

### Bot doesn't respond to commands
- Check the console for "Synced X command(s)" message
- Ensure the bot has proper permissions in the channel
- Try kicking and re-inviting the bot with correct permissions
- Wait a few minutes - Discord can take time to sync slash commands

### Welcome message not sent
- Configure the welcome channel with `/setup-channel`
- Ensure bot has permission to send messages in that channel
- Verify the Server Members Intent is enabled in Discord Developer Portal

### Cannot assign roles (403 Forbidden)
This is the most common issue. Discord requires the bot's role to be **higher** than roles it assigns:

1. Go to **Server Settings > Roles**
2. Find the bot's role (usually named after your bot)
3. **Drag it above** the Belgian and Foreigner roles
4. Save changes

### Channel not deleted after 30 seconds
- Bot needs **Manage Channels** permission
- Check console for error messages
- Ensure bot has permissions in the ticket category

### Log channel not receiving messages
- Verify log channel is configured: `/view-config`
- Ensure bot can **Send Messages** and **Embed Links** in that channel
- Check console for "Cannot post to log channel" messages

### Buttons stop working after restart
- This shouldn't happen as views are persistent
- If it does, send a new test message with `/test-welcome`
- The custom_id on buttons allows them to work after restart

### "Application did not respond" error
- The bot may have crashed - check the console
- Restart the bot
- This can happen if Discord's API is slow

## Console Debug Messages

The bot prints helpful debug info to the console:

| Message | Meaning |
|---------|---------|
| `Cannot post to log channel - missing permissions` | Bot can't send to log channel |
| `Log channel not found: <id>` | Configured channel was deleted |
| `Could not delete channel: <error>` | Missing Manage Channels permission |
| `Failed to sync commands: <error>` | Issue syncing slash commands |

## License

MIT License
