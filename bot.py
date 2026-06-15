#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         👑 GHOST VR'S ULTIMATE DISCORD BOT v2.0 👑        ║
║      Full Slash Commands — The Best Bot Ever Built        ║
╚══════════════════════════════════════════════════════════╝
SLASH COMMANDS:
  /help /ping /uptime /serverinfo /userinfo
  /ban /kick /mute /unmute /warn /warnings /clearwarnings /purge /lockdown /unlock
  /announce /embed
  /setwelcome /setleave /setlog /setstreamchannel
  /addstreamer /removestreamer
  /rank /leaderboard
  /giveaway /endgiveaway
  /poll
  /ticket /closeticket
  /afk /back
  /remind
  /8ball /coinflip /roast /ship /roll
  /ask
  /addword /removeword /automod
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import aiohttp
import os
import json
import random
import datetime
import sys
import time
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
BOT_VERSION = "2.0.0 — Ghost VR Slash Edition"
START_TIME = time.time()
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")

# ─────────────────────────────────────────────
#  STORAGE
# ─────────────────────────────────────────────
DATA_FILE = "/tmp/ghostvr_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

db = load_data()

def get_guild(guild_id):
    gid = str(guild_id)
    if gid not in db:
        db[gid] = {
            "xp": {}, "levels": {}, "warnings": {},
            "welcome_channel": None,
            "welcome_msg": "Welcome {user} to **{server}**! 🎉",
            "leave_channel": None,
            "leave_msg": "**{user}** has left **{server}**. 😢",
            "log_channel": None,
            "stream_channel": None,
            "twitch_streamers": [],
            "tracked_streamers": {},
            "giveaways": {},
            "tickets": {},
            "automod": {"spam": True, "caps": True, "badwords": []},
            "afk": {},
            "reminders": [],
            "announcement_channel": None,
        }
        save_data(db)
    return db[gid]

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree
spam_tracker = defaultdict(list)

# ─────────────────────────────────────────────
#  KEEP-ALIVE WEB SERVER
# ─────────────────────────────────────────────
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Ghost VR Bot is alive!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()

# ─────────────────────────────────────────────
#  ON READY
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"\n{'═'*55}")
    print(f"  👑 Ghost VR's Ultimate Bot v2.0 is ONLINE!")
    print(f"  Bot: {bot.user} (ID: {bot.user.id})")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"{'═'*55}\n")
    try:
        synced = await tree.sync()
        print(f"  ✅ Synced {len(synced)} slash commands globally")
    except Exception as e:
        print(f"  ❌ Slash sync error: {e}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"👑 {len(bot.guilds)} servers | /help"
        )
    )
    check_streams.start()
    check_reminders.start()
    check_giveaways.start()

# ─────────────────────────────────────────────
#  ON MESSAGE (automod + xp + AFK)
# ─────────────────────────────────────────────
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    g = get_guild(message.guild.id)
    uid = str(message.author.id)

    # AFK mention check
    for mentioned in message.mentions:
        mid = str(mentioned.id)
        if mid in g["afk"]:
            await message.channel.send(
                embed=discord.Embed(description=f"💤 **{mentioned.display_name}** is AFK: {g['afk'][mid]}", color=discord.Color.orange()),
                delete_after=10
            )

    # AFK return
    if uid in g["afk"]:
        del g["afk"][uid]
        save_data(db)
        await message.channel.send(f"✅ Welcome back {message.author.mention}! AFK removed.", delete_after=8)

    # Automod
    am = g.get("automod", {})
    now = time.time()
    if am.get("spam"):
        spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]
        spam_tracker[uid].append(now)
        if len(spam_tracker[uid]) >= 5:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} stop spamming!", delete_after=5)
            return

    if am.get("caps") and len(message.content) > 10:
        caps = sum(1 for c in message.content if c.isupper()) / len(message.content)
        if caps > 0.7:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} no excessive caps!", delete_after=5)
            return

    for word in am.get("badwords", []):
        if word.lower() in message.content.lower():
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} watch your language!", delete_after=5)
            return

    # XP
    if uid not in g["xp"]:
        g["xp"][uid] = 0
        g["levels"][uid] = 1
    g["xp"][uid] += random.randint(5, 15)
    xp_needed = g["levels"][uid] * 100
    if g["xp"][uid] >= xp_needed:
        g["xp"][uid] -= xp_needed
        g["levels"][uid] += 1
        lv = g["levels"][uid]
        save_data(db)
        await message.channel.send(embed=discord.Embed(
            title="🎉 Level Up!",
            description=f"{message.author.mention} reached **Level {lv}**! 🚀",
            color=discord.Color.gold()
        ))
        return
    save_data(db)
    await bot.process_commands(message)

# ─────────────────────────────────────────────
#  MEMBER JOIN / LEAVE
# ─────────────────────────────────────────────
@bot.event
async def on_member_join(member):
    g = get_guild(member.guild.id)
    ch_id = g.get("welcome_channel")
    if ch_id:
        ch = bot.get_channel(int(ch_id))
        if ch:
            msg = g["welcome_msg"].replace("{user}", member.mention).replace("{server}", member.guild.name)
            embed = discord.Embed(title="👋 Welcome!", description=msg, color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Member Count", value=str(member.guild.member_count))
            await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    g = get_guild(member.guild.id)
    ch_id = g.get("leave_channel")
    if ch_id:
        ch = bot.get_channel(int(ch_id))
        if ch:
            msg = g["leave_msg"].replace("{user}", str(member)).replace("{server}", member.guild.name)
            await ch.send(embed=discord.Embed(description=msg, color=discord.Color.red()))

# ─────────────────────────────────────────────
#  BACKGROUND TASKS
# ─────────────────────────────────────────────
twitch_token_cache = {"token": None, "expires": 0}

async def get_twitch_token():
    if twitch_token_cache["token"] and time.time() < twitch_token_cache["expires"]:
        return twitch_token_cache["token"]
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.post("https://id.twitch.tv/oauth2/token", params={
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }) as r:
            if r.status == 200:
                data = await r.json()
                twitch_token_cache["token"] = data["access_token"]
                twitch_token_cache["expires"] = time.time() + data["expires_in"] - 60
                return twitch_token_cache["token"]
    return None

async def verify_twitch_user(username: str, token: str) -> dict | None:
    """Search Twitch to confirm the account exists. Returns user info or None."""
    if not token:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.twitch.tv/helix/users?login={username.lower()}",
            headers={"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()
            users = data.get("data", [])
            return users[0] if users else None

@tasks.loop(seconds=60)
async def check_streams():
    token = await get_twitch_token()
    if not token:
        return
    for guild in bot.guilds:
        g = get_guild(guild.id)
        streamers = g.get("twitch_streamers_v2", {})
        # streamers = { "username": {"channel_id": "123", "live": False, "login": "exactlogin"} }
        if not streamers:
            continue
        changed = False
        for username, info in streamers.items():
            ch_id = info.get("channel_id")
            if not ch_id:
                continue
            ch = bot.get_channel(int(ch_id))
            if not ch:
                continue
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.twitch.tv/helix/streams?user_login={username}",
                        headers={"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
                    ) as r:
                        if r.status != 200:
                            continue
                        data = await r.json()
                        streams = data.get("data", [])
                        was_live = info.get("live", False)
                        is_live = len(streams) > 0
                        if is_live and not was_live:
                            s = streams[0]
                            # Get profile image
                            display_name = s.get("user_name", username)
                            thumb = s.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180")
                            embed = discord.Embed(
                                title=f"🔴 {display_name} just went LIVE!",
                                description=f"**{s.get('title', 'No title')}**",
                                url=f"https://twitch.tv/{username}",
                                color=discord.Color.purple()
                            )
                            embed.add_field(name="🎮 Game", value=s.get("game_name", "Unknown"), inline=True)
                            embed.add_field(name="👀 Viewers", value=str(s.get("viewer_count", 0)), inline=True)
                            if thumb:
                                embed.set_image(url=thumb)
                            embed.set_footer(text=f"twitch.tv/{username} • Click the title to watch!")
                            await ch.send(f"@everyone 🔴 **{display_name} is live!** Come watch!", embed=embed)
                            info["live"] = True
                            changed = True
                        elif not is_live and was_live:
                            info["live"] = False
                            changed = True
            except Exception as e:
                print(f"[StreamCheck Error] {username}: {e}")
        if changed:
            save_data(db)

@tasks.loop(minutes=1)
async def check_reminders():
    now = datetime.datetime.utcnow().timestamp()
    changed = False
    for gid, gdata in db.items():
        remaining = []
        for r in gdata.get("reminders", []):
            if now >= r["time"]:
                try:
                    ch = bot.get_channel(int(r["channel"]))
                    user = await bot.fetch_user(int(r["user"]))
                    if ch and user:
                        await ch.send(f"⏰ {user.mention} Reminder: **{r['text']}**")
                except:
                    pass
                changed = True
            else:
                remaining.append(r)
        gdata["reminders"] = remaining
    if changed:
        save_data(db)

@tasks.loop(minutes=1)
async def check_giveaways():
    now = datetime.datetime.utcnow().timestamp()
    changed = False
    for gid, gdata in db.items():
        for msg_id, gav in list(gdata.get("giveaways", {}).items()):
            if gav.get("ended"):
                continue
            if now >= gav["ends"]:
                try:
                    guild = bot.get_guild(int(gid))
                    ch = guild.get_channel(int(gav["channel"])) if guild else None
                    if ch:
                        msg = await ch.fetch_message(int(msg_id))
                        reaction = discord.utils.get(msg.reactions, emoji="🎉")
                        users = [u async for u in reaction.users() if not u.bot] if reaction else []
                        if users:
                            winner = random.choice(users)
                            await ch.send(embed=discord.Embed(
                                title="🎉 Giveaway Ended!",
                                description=f"**Prize:** {gav['prize']}\n**Winner:** {winner.mention} 🏆",
                                color=discord.Color.gold()
                            ))
                        else:
                            await ch.send(embed=discord.Embed(
                                title="🎉 Giveaway Ended",
                                description=f"No one entered the **{gav['prize']}** giveaway.",
                                color=discord.Color.red()
                            ))
                except:
                    pass
                gdata["giveaways"][msg_id]["ended"] = True
                changed = True
    if changed:
        save_data(db)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════

# ─── GENERAL ───────────────────────────────────

@tree.command(name="help", description="Show all bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="👑 Ghost VR Bot — Command List", color=discord.Color.blurple())
    embed.add_field(name="🛡️ Moderation", value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/warnings` `/clearwarnings` `/purge` `/lockdown` `/unlock`", inline=False)
    embed.add_field(name="📢 Announcements", value="`/announce` `/embed`", inline=False)
    embed.add_field(name="⚙️ Setup", value="`/setwelcome` `/setleave` `/setlog` `/addstreamer` `/removestreamer` `/liststreamers`", inline=False)
    embed.add_field(name="⭐ Leveling", value="`/rank` `/leaderboard`", inline=False)
    embed.add_field(name="🎉 Fun & Games", value="`/giveaway` `/endgiveaway` `/poll` `/8ball` `/coinflip` `/roast` `/ship` `/roll`", inline=False)
    embed.add_field(name="🎫 Tickets", value="`/ticket` `/closeticket`", inline=False)
    embed.add_field(name="💤 AFK & Reminders", value="`/afk` `/remind`", inline=False)
    embed.add_field(name="🤖 AI", value="`/ask`", inline=False)
    embed.add_field(name="🔒 Automod", value="`/automod` `/addword` `/removeword`", inline=False)
    embed.add_field(name="ℹ️ Info", value="`/ping` `/uptime` `/serverinfo` `/userinfo`", inline=False)
    embed.set_footer(text="Ghost VR's Ultimate Bot v2.0")
    await interaction.response.send_message(embed=embed)

@tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    color = discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red()
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=color)
    await interaction.response.send_message(embed=embed)

@tree.command(name="uptime", description="Check how long the bot has been online")
async def uptime(interaction: discord.Interaction):
    seconds = int(time.time() - START_TIME)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    embed = discord.Embed(title="⏱️ Uptime", description=f"**{h}h {m}m {s}s**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@tree.command(name="serverinfo", description="Show server information")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"🏠 {g.name}", color=discord.Color.blurple())
    embed.add_field(name="Owner", value=str(g.owner))
    embed.add_field(name="Members", value=str(g.member_count))
    embed.add_field(name="Channels", value=str(len(g.channels)))
    embed.add_field(name="Roles", value=str(len(g.roles)))
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"))
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="Show info about a user")
@app_commands.describe(member="The member to look up")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 {member}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=str(member.id))
    embed.add_field(name="Nickname", value=member.nick or "None")
    embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown")
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
    top_role = member.top_role.name if member.top_role else "None"
    embed.add_field(name="Top Role", value=top_role)
    await interaction.response.send_message(embed=embed)

# ─── MODERATION ────────────────────────────────

@tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="Member to ban", reason="Reason for ban")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="🔨 Banned", description=f"**{member}** was banned.\n**Reason:** {reason}", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="Member to kick", reason="Reason for kick")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="👢 Kicked", description=f"**{member}** was kicked.\n**Reason:** {reason}", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@tree.command(name="mute", description="Mute a member")
@app_commands.describe(member="Member to mute", duration="Duration in minutes (0 = permanent)", reason="Reason")
@app_commands.default_permissions(manage_roles=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int = 0, reason: str = "No reason provided"):
    await interaction.response.defer()
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await interaction.guild.create_role(name="Muted")
        for ch in interaction.guild.channels:
            await ch.set_permissions(muted_role, send_messages=False, speak=False)
    await member.add_roles(muted_role, reason=reason)
    embed = discord.Embed(title="🔇 Muted", description=f"**{member}** was muted.\n**Reason:** {reason}", color=discord.Color.dark_gray())
    if duration > 0:
        embed.add_field(name="Duration", value=f"{duration} minutes")
    await interaction.followup.send(embed=embed)
    if duration > 0:
        await asyncio.sleep(duration * 60)
        if muted_role in member.roles:
            await member.remove_roles(muted_role)

@tree.command(name="unmute", description="Unmute a member")
@app_commands.describe(member="Member to unmute")
@app_commands.default_permissions(manage_roles=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if muted_role and muted_role in member.roles:
        await member.remove_roles(muted_role)
        await interaction.response.send_message(f"✅ {member.mention} has been unmuted.")
    else:
        await interaction.response.send_message("⚠️ That member isn't muted.", ephemeral=True)

@tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="Member to warn", reason="Reason for warning")
@app_commands.default_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    g = get_guild(interaction.guild.id)
    uid = str(member.id)
    if uid not in g["warnings"]:
        g["warnings"][uid] = []
    g["warnings"][uid].append({"reason": reason, "time": str(datetime.datetime.utcnow())})
    save_data(db)
    count = len(g["warnings"][uid])
    embed = discord.Embed(title="⚠️ Warning Issued", description=f"**{member}** has been warned.\n**Reason:** {reason}\n**Total Warnings:** {count}", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

@tree.command(name="warnings", description="Check warnings for a member")
@app_commands.describe(member="Member to check")
@app_commands.default_permissions(manage_messages=True)
async def warnings(interaction: discord.Interaction, member: discord.Member):
    g = get_guild(interaction.guild.id)
    warns = g["warnings"].get(str(member.id), [])
    if not warns:
        await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.yellow())
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"Warning {i}", value=w["reason"], inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearwarnings", description="Clear all warnings for a member")
@app_commands.describe(member="Member to clear warnings for")
@app_commands.default_permissions(manage_messages=True)
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    g = get_guild(interaction.guild.id)
    g["warnings"][str(member.id)] = []
    save_data(db)
    await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}.")

@tree.command(name="purge", description="Delete multiple messages")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("⚠️ Amount must be between 1 and 100.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)

@tree.command(name="lockdown", description="Lock a channel so only admins can talk")
@app_commands.default_permissions(manage_channels=True)
async def lockdown(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel has been locked down.")

@tree.command(name="unlock", description="Unlock a locked channel")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel has been unlocked.")

# ─── ANNOUNCEMENTS ─────────────────────────────

@tree.command(name="announce", description="Send an announcement embed")
@app_commands.describe(title="Announcement title", message="Announcement message", channel="Channel to send to (optional)", ping="Ping everyone? (yes/no)")
@app_commands.default_permissions(manage_messages=True)
async def announce(interaction: discord.Interaction, title: str, message: str, channel: discord.TextChannel = None, ping: str = "no"):
    ch = channel or interaction.channel
    embed = discord.Embed(title=f"📢 {title}", description=message, color=discord.Color.blurple())
    embed.set_footer(text=f"Announced by {interaction.user} • {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    content = "@everyone" if ping.lower() == "yes" else None
    await ch.send(content=content, embed=embed)
    await interaction.response.send_message(f"✅ Announcement sent to {ch.mention}!", ephemeral=True)

@tree.command(name="embed", description="Send a custom embed message")
@app_commands.describe(title="Embed title", description="Embed description", color="Color (red/green/blue/gold/purple)", channel="Channel to send to")
@app_commands.default_permissions(manage_messages=True)
async def embed_cmd(interaction: discord.Interaction, title: str, description: str, color: str = "blue", channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    colors = {"red": discord.Color.red(), "green": discord.Color.green(), "blue": discord.Color.blue(), "gold": discord.Color.gold(), "purple": discord.Color.purple()}
    embed = discord.Embed(title=title, description=description, color=colors.get(color.lower(), discord.Color.blue()))
    embed.set_footer(text=f"By {interaction.user}")
    await ch.send(embed=embed)
    await interaction.response.send_message("✅ Embed sent!", ephemeral=True)

# ─── SETUP ─────────────────────────────────────

@tree.command(name="setwelcome", description="Set the welcome channel and message")
@app_commands.describe(channel="Welcome channel", message="Welcome message. Use {user} and {server}")
@app_commands.default_permissions(manage_guild=True)
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str = "Welcome {user} to **{server}**! 🎉"):
    g = get_guild(interaction.guild.id)
    g["welcome_channel"] = str(channel.id)
    g["welcome_msg"] = message
    save_data(db)
    await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}!")

@tree.command(name="setleave", description="Set the leave channel and message")
@app_commands.describe(channel="Leave channel", message="Leave message. Use {user} and {server}")
@app_commands.default_permissions(manage_guild=True)
async def setleave(interaction: discord.Interaction, channel: discord.TextChannel, message: str = "**{user}** has left **{server}**. 😢"):
    g = get_guild(interaction.guild.id)
    g["leave_channel"] = str(channel.id)
    g["leave_msg"] = message
    save_data(db)
    await interaction.response.send_message(f"✅ Leave channel set to {channel.mention}!")

@tree.command(name="setlog", description="Set the moderation log channel")
@app_commands.describe(channel="Log channel")
@app_commands.default_permissions(manage_guild=True)
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    g = get_guild(interaction.guild.id)
    g["log_channel"] = str(channel.id)
    save_data(db)
    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}!")

@tree.command(name="addstreamer", description="Add a Twitch streamer with their own alert channel")
@app_commands.describe(username="Twitch username to track", channel="Channel to post alerts in")
@app_commands.default_permissions(manage_guild=True)
async def addstreamer(interaction: discord.Interaction, username: str, channel: discord.TextChannel):
    await interaction.response.defer()
    # Verify the Twitch account exists
    token = await get_twitch_token()
    if token:
        user_info = await verify_twitch_user(username, token)
        if not user_info:
            await interaction.followup.send(
                f"❌ Could not find a Twitch account named **{username}**. Double-check the username and try again.",
                ephemeral=True
            )
            return
        exact_login = user_info["login"]
        display_name = user_info["display_name"]
        profile_img = user_info.get("profile_image_url", "")
    else:
        exact_login = username.lower()
        display_name = username
        profile_img = ""

    g = get_guild(interaction.guild.id)
    if "twitch_streamers_v2" not in g:
        g["twitch_streamers_v2"] = {}

    if exact_login in g["twitch_streamers_v2"]:
        await interaction.followup.send(f"⚠️ Already tracking **{display_name}**.", ephemeral=True)
        return

    g["twitch_streamers_v2"][exact_login] = {
        "channel_id": str(channel.id),
        "live": False,
        "display_name": display_name,
        "profile_img": profile_img
    }
    save_data(db)

    embed = discord.Embed(
        title="✅ Streamer Added!",
        description=f"Now tracking **{display_name}** on Twitch.\nAlerts will post in {channel.mention} the moment they go live! 🔴",
        color=discord.Color.purple()
    )
    if profile_img:
        embed.set_thumbnail(url=profile_img)
    embed.set_footer(text=f"twitch.tv/{exact_login}")
    await interaction.followup.send(embed=embed)

@tree.command(name="removestreamer", description="Stop tracking a Twitch streamer")
@app_commands.describe(username="Twitch username to remove")
@app_commands.default_permissions(manage_guild=True)
async def removestreamer(interaction: discord.Interaction, username: str):
    g = get_guild(interaction.guild.id)
    streamers = g.get("twitch_streamers_v2", {})
    if username.lower() in streamers:
        del streamers[username.lower()]
        save_data(db)
        await interaction.response.send_message(f"✅ Stopped tracking **{username}**.")
    else:
        await interaction.response.send_message(f"⚠️ Not tracking **{username}**.", ephemeral=True)

@tree.command(name="liststreamers", description="List all tracked streamers and their alert channels")
async def liststreamers(interaction: discord.Interaction):
    g = get_guild(interaction.guild.id)
    streamers = g.get("twitch_streamers_v2", {})
    if not streamers:
        await interaction.response.send_message("📭 No streamers are being tracked yet. Use `/addstreamer` to add one!", ephemeral=True)
        return
    embed = discord.Embed(title="📡 Tracked Streamers", color=discord.Color.purple())
    for login, info in streamers.items():
        ch = bot.get_channel(int(info["channel_id"]))
        ch_name = ch.mention if ch else "Unknown channel"
        status = "🔴 LIVE" if info.get("live") else "⚫ Offline"
        embed.add_field(
            name=f"{info.get('display_name', login)}",
            value=f"Channel: {ch_name}\nStatus: {status}\ntwitch.tv/{login}",
            inline=True
        )
    await interaction.response.send_message(embed=embed)

# ─── LEVELING ──────────────────────────────────

@tree.command(name="rank", description="Check your rank and XP")
@app_commands.describe(member="Member to check (leave blank for yourself)")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    g = get_guild(interaction.guild.id)
    uid = str(member.id)
    xp = g["xp"].get(uid, 0)
    level = g["levels"].get(uid, 1)
    xp_needed = level * 100
    embed = discord.Embed(title=f"⭐ {member.display_name}'s Rank", color=discord.Color.gold())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=str(level))
    embed.add_field(name="XP", value=f"{xp} / {xp_needed}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="leaderboard", description="Show the server XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    g = get_guild(interaction.guild.id)
    sorted_users = sorted(g["levels"].items(), key=lambda x: (x[1], g["xp"].get(x[0], 0)), reverse=True)[:10]
    embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, level) in enumerate(sorted_users):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"User {uid}"
        medal = medals[i] if i < 3 else f"#{i+1}"
        embed.add_field(name=f"{medal} {name}", value=f"Level {level} • {g['xp'].get(uid, 0)} XP", inline=False)
    await interaction.response.send_message(embed=embed)

# ─── GIVEAWAYS ─────────────────────────────────

@tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(prize="What are you giving away?", duration="Duration in minutes", channel="Channel to host giveaway")
@app_commands.default_permissions(manage_guild=True)
async def giveaway(interaction: discord.Interaction, prize: str, duration: int, channel: discord.TextChannel = None):
    ch = channel or interaction.channel
    ends = datetime.datetime.utcnow().timestamp() + (duration * 60)
    ends_dt = datetime.datetime.utcfromtimestamp(ends).strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title="🎉 GIVEAWAY!",
        description=f"**Prize:** {prize}\n**Ends:** {ends_dt}\n\nReact with 🎉 to enter!",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Hosted by {interaction.user}")
    msg = await ch.send(embed=embed)
    await msg.add_reaction("🎉")
    g = get_guild(interaction.guild.id)
    g["giveaways"][str(msg.id)] = {"prize": prize, "ends": ends, "channel": str(ch.id), "ended": False}
    save_data(db)
    await interaction.response.send_message(f"✅ Giveaway started in {ch.mention}!", ephemeral=True)

@tree.command(name="endgiveaway", description="End a giveaway early by message ID")
@app_commands.describe(message_id="The message ID of the giveaway")
@app_commands.default_permissions(manage_guild=True)
async def endgiveaway(interaction: discord.Interaction, message_id: str):
    g = get_guild(interaction.guild.id)
    gav = g["giveaways"].get(message_id)
    if not gav or gav.get("ended"):
        await interaction.response.send_message("⚠️ Giveaway not found or already ended.", ephemeral=True)
        return
    gav["ends"] = 0
    save_data(db)
    await interaction.response.send_message("✅ Giveaway will end shortly!", ephemeral=True)

# ─── POLLS ─────────────────────────────────────

@tree.command(name="poll", description="Create a poll")
@app_commands.describe(question="Poll question", option1="Option 1", option2="Option 2", option3="Option 3 (optional)", option4="Option 4 (optional)")
async def poll(interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None):
    options = [opt for opt in [option1, option2, option3, option4] if opt]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    description = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(options)])
    embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.blurple())
    embed.set_footer(text=f"Poll by {interaction.user}")
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

# ─── TICKETS ───────────────────────────────────

@tree.command(name="ticket", description="Open a support ticket")
@app_commands.describe(reason="Reason for your ticket")
async def ticket(interaction: discord.Interaction, reason: str = "Support needed"):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    ch = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
    embed = discord.Embed(title="🎫 Ticket Opened", description=f"**User:** {interaction.user.mention}\n**Reason:** {reason}\n\nSupport will be with you shortly!\nUse `/closeticket` to close.", color=discord.Color.green())
    await ch.send(embed=embed)
    await interaction.response.send_message(f"✅ Ticket created: {ch.mention}", ephemeral=True)

@tree.command(name="closeticket", description="Close the current ticket channel")
@app_commands.default_permissions(manage_channels=True)
async def closeticket(interaction: discord.Interaction):
    if "ticket-" in interaction.channel.name:
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("⚠️ This is not a ticket channel.", ephemeral=True)

# ─── AFK ───────────────────────────────────────

@tree.command(name="afk", description="Set your AFK status")
@app_commands.describe(reason="AFK reason")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    g = get_guild(interaction.guild.id)
    g["afk"][str(interaction.user.id)] = reason
    save_data(db)
    await interaction.response.send_message(f"💤 {interaction.user.mention} is now AFK: **{reason}**")

# ─── REMINDERS ─────────────────────────────────

@tree.command(name="remind", description="Set a reminder")
@app_commands.describe(minutes="How many minutes from now?", reminder="What to remind you about")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    g = get_guild(interaction.guild.id)
    remind_time = datetime.datetime.utcnow().timestamp() + (minutes * 60)
    g["reminders"].append({
        "user": str(interaction.user.id),
        "channel": str(interaction.channel.id),
        "text": reminder,
        "time": remind_time
    })
    save_data(db)
    await interaction.response.send_message(f"⏰ I'll remind you in **{minutes} minutes**: {reminder}", ephemeral=True)

# ─── FUN ───────────────────────────────────────

@tree.command(name="8ball", description="Ask the magic 8ball a question")
@app_commands.describe(question="Your yes/no question")
async def eightball(interaction: discord.Interaction, question: str):
    answers = [
        "✅ It is certain.", "✅ Without a doubt.", "✅ Yes, definitely!",
        "✅ You may rely on it.", "✅ Most likely.", "🤔 Ask again later.",
        "🤔 Cannot predict now.", "🤔 Don't count on it.", "❌ My reply is no.",
        "❌ Very doubtful.", "❌ Outlook not so good.", "❌ No way!"
    ]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.dark_purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(answers), inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["🪙 Heads!", "🪙 Tails!"])
    await interaction.response.send_message(embed=discord.Embed(title="Coin Flip", description=result, color=discord.Color.gold()))

@tree.command(name="roll", description="Roll a dice")
@app_commands.describe(sides="Number of sides (default 6)")
async def roll(interaction: discord.Interaction, sides: int = 6):
    result = random.randint(1, sides)
    await interaction.response.send_message(embed=discord.Embed(title=f"🎲 Rolled a d{sides}", description=f"You got: **{result}**", color=discord.Color.blurple()))

@tree.command(name="roast", description="Roast a member (for fun!)")
@app_commands.describe(member="Who to roast")
async def roast(interaction: discord.Interaction, member: discord.Member):
    roasts = [
        f"{member.mention} you're the human equivalent of a participation trophy.",
        f"{member.mention} your WiFi password is probably 'password'.",
        f"If brains were gasoline, {member.mention} couldn't power a scooter.",
        f"{member.mention} you're like a cloud — when you disappear, it's a beautiful day.",
        f"{member.mention} you bring everyone so much joy... when you leave the room.",
        f"I'd agree with you, {member.mention}, but then we'd both be wrong.",
        f"{member.mention} you're proof that evolution can go in reverse.",
    ]
    await interaction.response.send_message(random.choice(roasts))

@tree.command(name="ship", description="Ship two users and check their compatibility!")
@app_commands.describe(user1="First user", user2="Second user")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    score = random.randint(0, 100)
    bar_filled = score // 10
    bar = "❤️" * bar_filled + "🖤" * (10 - bar_filled)
    embed = discord.Embed(title="💘 Ship-o-Meter", color=discord.Color.red())
    embed.description = f"**{user1.display_name}** x **{user2.display_name}**\n\n{bar}\n\n**{score}% compatible!**"
    if score >= 80:
        embed.set_footer(text="Match made in heaven! 💍")
    elif score >= 50:
        embed.set_footer(text="There's potential here! 💕")
    else:
        embed.set_footer(text="Maybe just friends... 😬")
    await interaction.response.send_message(embed=embed)

# ─── AI CHAT ───────────────────────────────────

@tree.command(name="ask", description="Ask the bot an AI-powered question")
@app_commands.describe(question="Your question")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    responses = [
        f"Great question! Based on what I know: {question} — the answer really depends on context, but generally speaking, you'll want to think carefully about it!",
        f"Hmm, '{question}' — that's a tricky one. I'd say the best approach is to keep it simple and focus on what matters most.",
        f"Interesting! Regarding '{question}': there are many perspectives on this. The most important thing is to do your research and trust your instincts.",
        f"For '{question}' — my best advice: break it down into smaller parts and tackle each one. You've got this!",
    ]
    embed = discord.Embed(title="🤖 AI Response", color=discord.Color.blurple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    embed.set_footer(text="Powered by Ghost VR Bot AI")
    await interaction.followup.send(embed=embed)

# ─── AUTOMOD ───────────────────────────────────

@tree.command(name="automod", description="Toggle automod features")
@app_commands.describe(feature="Feature to toggle: spam or caps", enabled="on or off")
@app_commands.default_permissions(manage_guild=True)
async def automod_cmd(interaction: discord.Interaction, feature: str, enabled: str):
    g = get_guild(interaction.guild.id)
    if feature.lower() not in ["spam", "caps"]:
        await interaction.response.send_message("⚠️ Feature must be `spam` or `caps`.", ephemeral=True)
        return
    g["automod"][feature.lower()] = enabled.lower() == "on"
    save_data(db)
    status = "✅ Enabled" if enabled.lower() == "on" else "❌ Disabled"
    await interaction.response.send_message(f"{status} **{feature}** filter.")

@tree.command(name="addword", description="Add a banned word to the filter")
@app_commands.describe(word="Word to ban")
@app_commands.default_permissions(manage_guild=True)
async def addword(interaction: discord.Interaction, word: str):
    g = get_guild(interaction.guild.id)
    if word.lower() not in g["automod"]["badwords"]:
        g["automod"]["badwords"].append(word.lower())
        save_data(db)
        await interaction.response.send_message(f"✅ Added `{word}` to the word filter.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ `{word}` is already in the filter.", ephemeral=True)

@tree.command(name="removeword", description="Remove a word from the filter")
@app_commands.describe(word="Word to remove")
@app_commands.default_permissions(manage_guild=True)
async def removeword(interaction: discord.Interaction, word: str):
    g = get_guild(interaction.guild.id)
    g["automod"]["badwords"] = [w for w in g["automod"]["badwords"] if w != word.lower()]
    save_data(db)
    await interaction.response.send_message(f"✅ Removed `{word}` from the word filter.", ephemeral=True)

# ─────────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN not set!")
        sys.exit(1)
    print("🚀 Starting Ghost VR's Ultimate Discord Bot v2.0...")
    threading.Thread(target=run_server, daemon=True).start()
    bot.run(TOKEN)
