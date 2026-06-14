#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║           👑 GHOST VR'S ULTIMATE DISCORD BOT 👑       ║
║         The most feature-packed bot ever built        ║
╚══════════════════════════════════════════════════════╝

FEATURES:
  ✅ Moderation (ban, kick, mute, warn, purge, lockdown)
  ✅ Auto-mod (spam filter, bad words, caps filter)
  ✅ Announcements with rich embeds
  ✅ Stream alerts (Twitch)
  ✅ Welcome / Leave messages
  ✅ XP & Leveling system with ranks
  ✅ Giveaways
  ✅ Polls
  ✅ Tickets support system
  ✅ Server stats
  ✅ Fun commands (coinflip, 8ball, roast, ship)
  ✅ AI chat (!ask)
  ✅ Reminders
  ✅ Role management
  ✅ Embed builder
  ✅ AFK system
  ✅ Server info / User info
  ✅ Ping, uptime, help
"""

import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import os
import json
import random
import datetime
import re
import sys
import time
from collections import defaultdict

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
PREFIX = "!"
BOT_VERSION = "1.0.0 — Ghost VR Edition"
START_TIME = time.time()

# Twitch config (set these env vars for stream alerts)
TWITCH_CLIENT_ID = os.environ.get("dnraeq1qmd7uk6zve3udx3ea9j3dpe", "")
TWITCH_CLIENT_SECRET = os.environ.get("0b0xioy36hnjwj1a1g4oxgo71pf11d", "")

# ─────────────────────────────────────────────
#  STORAGE (in-memory, persisted to JSON)
# ─────────────────────────────────────────────
DATA_FILE = "/tmp/data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

db = load_data()

def get_guild_data(guild_id):
    gid = str(guild_id)
    if gid not in db:
        db[gid] = {
            "xp": {}, "levels": {}, "warnings": {},
            "muted_roles": {}, "welcome_channel": None,
            "welcome_msg": "Welcome {user} to **{server}**! 🎉",
            "leave_msg": "**{user}** has left the server. 😢",
            "log_channel": None, "stream_channel": None,
            "twitch_streamers": [], "youtube_channels": [], "tiktok_users": [],
            "tracked_streamers": {}, "tracked_youtube": {}, "tracked_tiktok": {},
            "giveaways": {}, "tickets": {},
            "automod": {"spam": True, "caps": True, "badwords": []},
            "afk": {}, "reminders": [],
            "announcement_channel": None,
        }
        save_data(db)
    return db[str(guild_id)]

# ─────────────────────────────────────────────
#  INTENTS & BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Spam tracking
spam_tracker = defaultdict(list)

# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"\n{'═'*50}")
    print(f"  👑 Ghost VR's Ultimate Bot is ONLINE!")
    print(f"  Bot: {bot.user} (ID: {bot.user.id})")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"  Version: {BOT_VERSION}")
    print(f"{'═'*50}\n")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"👑 {len(bot.guilds)} servers | !help"
        )
    )
    check_streams.start()
    check_reminders.start()

@bot.event
async def on_member_join(member: discord.Member):
    print(f"JOIN EVENT: {member}")

    channel = member.guild.get_channel(1433981691973734471)

    if not channel:
        print("Channel not found")
        return

    try:
        await channel.send(f"👋 Welcome {member.mention}!")
    except Exception as e:
        print(f"Send failed: {e}")

@bot.event
async def on_member_remove(member):
    g = get_guild_data(member.guild.id)
    ch_id = g.get("welcome_channel")
    if ch_id:
        ch = bot.get_channel(int(ch_id))
        if ch:
            msg = g["leave_msg"].replace("{user}", str(member)).replace("{server}", member.guild.name)
            embed = discord.Embed(description=msg, color=discord.Color.red())
            await ch.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # AFK check — mention someone who is AFK
    if message.mentions:
        g = get_guild_data(message.guild.id)
        for mentioned in message.mentions:
            uid = str(mentioned.id)
            if uid in g["afk"]:
                reason = g["afk"][uid]
                embed = discord.Embed(
                    description=f"💤 **{mentioned.display_name}** is AFK: {reason}",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=embed)

    # AFK return
    g = get_guild_data(message.guild.id)
    uid = str(message.author.id)
    if uid in g["afk"]:
        del g["afk"][uid]
        save_data(db)
        await message.channel.send(f"✅ Welcome back {message.author.mention}, I removed your AFK.")

    # Auto-mod
    await automod_check(message)

    # XP gain
    await add_xp(message)

    await bot.process_commands(message)

async def automod_check(message):
    if not message.guild:
        return
    g = get_guild_data(message.guild.id)
    am = g.get("automod", {})

    # Spam filter
    if am.get("spam"):
        uid = str(message.author.id)
        now = time.time()
        spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]
        spam_tracker[uid].append(now)
        if len(spam_tracker[uid]) >= 5:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} slow down! No spamming.", delete_after=5)
            return

    # Caps filter (>70% caps in 10+ char message)
    if am.get("caps") and len(message.content) > 10:
        caps_ratio = sum(1 for c in message.content if c.isupper()) / len(message.content)
        if caps_ratio > 0.7:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} please don't use excessive caps.", delete_after=5)
            return

    # Bad words filter
    badwords = am.get("badwords", [])
    if badwords:
        content_lower = message.content.lower()
        for word in badwords:
            if word.lower() in content_lower:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} watch your language!", delete_after=5)
                return

async def add_xp(message):
    if not message.guild:
        return
    g = get_guild_data(message.guild.id)
    uid = str(message.author.id)
    if uid not in g["xp"]:
        g["xp"][uid] = 0
        g["levels"][uid] = 1
    xp_gain = random.randint(5, 15)
    g["xp"][uid] += xp_gain
    level = g["levels"][uid]
    xp_needed = level * 100
    if g["xp"][uid] >= xp_needed:
        g["xp"][uid] -= xp_needed
        g["levels"][uid] += 1
        new_level = g["levels"][uid]
        save_data(db)
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"{message.author.mention} just reached **Level {new_level}**! 🚀",
            color=discord.Color.gold()
        )
        await message.channel.send(embed=embed)
        return
    save_data(db)

# ─────────────────────────────────────────────
#  MODERATION COMMANDS
# ─────────────────────────────────────────────

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="🔨 Banned", description=f"**{member}** has been banned.\n**Reason:** {reason}", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="👢 Kicked", description=f"**{member}** has been kicked.\n**Reason:** {reason}", color=discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: int = 0, *, reason="No reason provided"):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False)
    await member.add_roles(muted_role, reason=reason)
    embed = discord.Embed(title="🔇 Muted", description=f"**{member}** has been muted.\n**Reason:** {reason}", color=discord.Color.dark_gray())
    if duration > 0:
        embed.add_field(name="Duration", value=f"{duration} minutes")
    await ctx.send(embed=embed)
    if duration > 0:
        await asyncio.sleep(duration * 60)
        await member.remove_roles(muted_role)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role and muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f"✅ {member.mention} has been unmuted.")
    else:
        await ctx.send("⚠️ That member isn't muted.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    g = get_guild_data(ctx.guild.id)
    uid = str(member.id)
    if uid not in g["warnings"]:
        g["warnings"][uid] = []
    g["warnings"][uid].append({"reason": reason, "date": str(datetime.datetime.utcnow()), "by": str(ctx.author)})
    save_data(db)
    count = len(g["warnings"][uid])
    embed = discord.Embed(title="⚠️ Warning Issued", description=f"**{member}** has been warned.\n**Reason:** {reason}\n**Total Warnings:** {count}", color=discord.Color.yellow())
    await ctx.send(embed=embed)
    if count >= 3:
        await ctx.send(f"⚠️ {member.mention} has reached **{count} warnings**! Consider taking action.")

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    member = member or ctx.author
    g = get_guild_data(ctx.guild.id)
    uid = str(member.id)
    warns = g["warnings"].get(uid, [])
    if not warns:
        await ctx.send(f"✅ {member.display_name} has no warnings.")
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member.display_name}", color=discord.Color.yellow())
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"Warning #{i}", value=f"**Reason:** {w['reason']}\n**By:** {w['by']}\n**Date:** {w['date'][:10]}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarnings(ctx, member: discord.Member):
    g = get_guild_data(ctx.guild.id)
    g["warnings"][str(member.id)] = []
    save_data(db)
    await ctx.send(f"✅ Cleared all warnings for {member.mention}.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount > 200:
        await ctx.send("⚠️ Max purge is 200 messages.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ Deleted **{len(deleted)-1}** messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lockdown(ctx, *, reason="No reason provided"):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    embed = discord.Embed(title="🔒 Channel Locked", description=f"This channel has been locked.\n**Reason:** {reason}", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Channel unlocked!")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname):
    await member.edit(nick=nickname)
    await ctx.send(f"✅ Changed {member.mention}'s nickname to **{nickname}**.")

# ─────────────────────────────────────────────
#  ANNOUNCEMENTS
# ─────────────────────────────────────────────

@bot.command()
@commands.has_permissions(manage_guild=True)
async def announce(ctx, channel: discord.TextChannel, *, message):
    embed = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"Announced by {ctx.author.display_name}")
    await channel.send("@everyone", embed=embed)
    await ctx.send(f"✅ Announcement sent to {channel.mention}!")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def embed(ctx, channel: discord.TextChannel, title, *, description):
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    embed.set_footer(text=f"By {ctx.author.display_name}")
    await channel.send(embed=embed)
    await ctx.send(f"✅ Embed sent to {channel.mention}!")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setwelcome(ctx, channel: discord.TextChannel, *, message=None):
    g = get_guild_data(ctx.guild.id)
    g["welcome_channel"] = str(channel.id)
    if message:
        g["welcome_msg"] = message
    save_data(db)
    await ctx.send(f"✅ Welcome channel set to {channel.mention}!\nUse `{{user}}` for mention, `{{server}}` for server name.")

# ─────────────────────────────────────────────
#  STREAM ALERTS
# ─────────────────────────────────────────────

import re
from discord.ext import commands

STREAM_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com|youtu\.be|twitch\.tv|tiktok\.com)/.+"
)

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setstream(ctx, link: str):
    g = get_guild_data(ctx.guild.id)

    # validate link
    if not STREAM_REGEX.match(link):
        return await ctx.send("❌ Please provide a valid YouTube, Twitch, or TikTok link.")

    g["stream_link"] = link
    save_data(db)

    await ctx.send(f"✅ Stream link saved: {link}")

# ── TWITCH ──────────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(manage_guild=True)
async def addtwitch(ctx, username: str):
    g = get_guild_data(ctx.guild.id)
    if username.lower() not in g["twitch_streamers"]:
        g["twitch_streamers"].append(username.lower())
        save_data(db)
        await ctx.send(f"✅ Now tracking **{username}** on Twitch! 🟣")
    else:
        await ctx.send(f"⚠️ Already tracking **{username}** on Twitch.")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def removetwitch(ctx, username: str):
    g = get_guild_data(ctx.guild.id)
    if username.lower() in g["twitch_streamers"]:
        g["twitch_streamers"].remove(username.lower())
        save_data(db)
        await ctx.send(f"✅ Stopped tracking **{username}** on Twitch.")
    else:
        await ctx.send("⚠️ That Twitch streamer wasn't being tracked.")

# ── YOUTUBE ──────────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(manage_guild=True)
async def addyoutube(ctx, *, channel_name: str):
    """Add a YouTube channel to track for live streams. Use their @handle or channel name."""
    g = get_guild_data(ctx.guild.id)
    if channel_name.lower() not in g["youtube_channels"]:
        g["youtube_channels"].append(channel_name.lower())
        save_data(db)
        await ctx.send(f"✅ Now tracking **{channel_name}** on YouTube! 🔴\n⚠️ Note: Set YOUTUBE_API_KEY env var for live stream detection.")
    else:
        await ctx.send(f"⚠️ Already tracking **{channel_name}** on YouTube.")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def removeyoutube(ctx, *, channel_name: str):
    g = get_guild_data(ctx.guild.id)
    if channel_name.lower() in g["youtube_channels"]:
        g["youtube_channels"].remove(channel_name.lower())
        save_data(db)
        await ctx.send(f"✅ Stopped tracking **{channel_name}** on YouTube.")
    else:
        await ctx.send("⚠️ That YouTube channel wasn't being tracked.")

# ── TIKTOK ──────────────────────────────────────────────────────────
@bot.command()
@commands.has_permissions(manage_guild=True)
async def addtiktok(ctx, username: str):
    """Add a TikTok user to track for LIVE streams."""
    g = get_guild_data(ctx.guild.id)
    u = username.lstrip("@").lower()
    if u not in g["tiktok_users"]:
        g["tiktok_users"].append(u)
        save_data(db)
        await ctx.send(f"✅ Now tracking **@{u}** on TikTok! 🎵")
    else:
        await ctx.send(f"⚠️ Already tracking **@{u}** on TikTok.")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def removetiktok(ctx, username: str):
    g = get_guild_data(ctx.guild.id)
    u = username.lstrip("@").lower()
    if u in g["tiktok_users"]:
        g["tiktok_users"].remove(u)
        save_data(db)
        await ctx.send(f"✅ Stopped tracking **@{u}** on TikTok.")
    else:
        await ctx.send("⚠️ That TikTok user wasn't being tracked.")

# ── LIST ALL STREAMERS ───────────────────────────────────────────────
@bot.command()
async def streamers(ctx):
    g = get_guild_data(ctx.guild.id)
    embed = discord.Embed(title="🎮 Tracked Streamers", color=discord.Color.purple())
    twitch_list = g.get("twitch_streamers", [])
    yt_list = g.get("youtube_channels", [])
    tt_list = g.get("tiktok_users", [])
    embed.add_field(
        name="🟣 Twitch",
        value="\n".join(f"• {s}" for s in twitch_list) if twitch_list else "None",
        inline=False
    )
    embed.add_field(
        name="🔴 YouTube",
        value="\n".join(f"• {s}" for s in yt_list) if yt_list else "None",
        inline=False
    )
    embed.add_field(
        name="🎵 TikTok",
        value="\n".join(f"• @{s}" for s in tt_list) if tt_list else "None",
        inline=False
    )
    if not twitch_list and not yt_list and not tt_list:
        embed.description = "No streamers tracked yet! Use `!addtwitch`, `!addyoutube`, or `!addtiktok`."
    await ctx.send(embed=embed)

# ── STREAM CHECKER LOOP ──────────────────────────────────────────────
@tasks.loop(minutes=5)
async def check_streams():
    await check_twitch_streams()
    await check_youtube_streams()
    await check_tiktok_streams()

async def check_twitch_streams():
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={"client_id": TWITCH_CLIENT_ID, "client_secret": TWITCH_CLIENT_SECRET, "grant_type": "client_credentials"}
            ) as r:
                token_data = await r.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    return

            for guild in bot.guilds:
                g = get_guild_data(guild.id)
                streamers = g.get("twitch_streamers", [])
                ch_id = g.get("stream_channel")
                if not streamers or not ch_id:
                    continue
                channel = bot.get_channel(int(ch_id))
                if not channel:
                    continue

                for streamer in streamers:
                    try:
                        async with session.get(
                            f"https://api.twitch.tv/helix/streams?user_login={streamer}",
                            headers={"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {access_token}"}
                        ) as r:
                            data = await r.json()
                            streams = data.get("data", [])
                            was_live = g["tracked_streamers"].get(streamer, False)
                            is_live = len(streams) > 0

                            if is_live and not was_live:
                                stream = streams[0]
                                embed = discord.Embed(
                                    title=f"🟣 {streamer} is LIVE on Twitch!",
                                    description=f"**{stream.get('title', 'No title')}**",
                                    url=f"https://twitch.tv/{streamer}",
                                    color=discord.Color.purple()
                                )
                                embed.add_field(name="🎮 Game", value=stream.get("game_name", "Unknown"))
                                embed.add_field(name="👥 Viewers", value=f"{stream.get('viewer_count', 0):,}")
                                thumb = stream.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180")
                                if thumb:
                                    embed.set_image(url=thumb)
                                embed.set_footer(text="Twitch Stream Alert • Ghost VR Bot")
                                await channel.send(f"@everyone 🟣 **{streamer}** just went live on Twitch!", embed=embed)
                                g["tracked_streamers"][streamer] = True
                            elif not is_live:
                                g["tracked_streamers"][streamer] = False
                    except Exception as e:
                        print(f"[Twitch] Error checking {streamer}: {e}")

                save_data(db)
    except Exception as e:
        print(f"[Twitch Check Error] {e}")

async def check_youtube_streams():
    """Check YouTube live streams using RSS feed (no API key needed for basic check)."""
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
    try:
        async with aiohttp.ClientSession() as session:
            for guild in bot.guilds:
                g = get_guild_data(guild.id)
                channels_list = g.get("youtube_channels", [])
                ch_id = g.get("stream_channel")
                if not channels_list or not ch_id:
                    continue
                alert_channel = bot.get_channel(int(ch_id))
                if not alert_channel:
                    continue

                for yt_channel in channels_list:
                    try:
                        if YOUTUBE_API_KEY:
                            # Search for live streams using YouTube Data API
                            search_url = (
                                f"https://www.googleapis.com/youtube/v3/search"
                                f"?part=snippet&channelId={yt_channel}&eventType=live"
                                f"&type=video&key={YOUTUBE_API_KEY}"
                            )
                            async with session.get(search_url) as r:
                                if r.status == 200:
                                    data = await r.json()
                                    items = data.get("items", [])
                                    was_live = g["tracked_youtube"].get(yt_channel, False)
                                    is_live = len(items) > 0

                                    if is_live and not was_live:
                                        item = items[0]
                                        snippet = item["snippet"]
                                        video_id = item["id"]["videoId"]
                                        embed = discord.Embed(
                                            title=f"🔴 {snippet['channelTitle']} is LIVE on YouTube!",
                                            description=f"**{snippet['title']}**",
                                            url=f"https://youtube.com/watch?v={video_id}",
                                            color=discord.Color.red()
                                        )
                                        thumb = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                                        if thumb:
                                            embed.set_image(url=thumb)
                                        embed.set_footer(text="YouTube Stream Alert • Ghost VR Bot")
                                        await alert_channel.send(f"@everyone 🔴 **{snippet['channelTitle']}** is LIVE on YouTube!", embed=embed)
                                        g["tracked_youtube"][yt_channel] = True
                                    elif not is_live:
                                        g["tracked_youtube"][yt_channel] = False
                        else:
                            # RSS feed fallback — checks recent uploads
                            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_channel}"
                            async with session.get(rss_url) as r:
                                if r.status == 200:
                                    text = await r.text()
                                    # Basic check for live indicator in feed
                                    if "yt:videoId" in text:
                                        import re as _re
                                        video_ids = _re.findall(r"<yt:videoId>([^<]+)</yt:videoId>", text)
                                        titles = _re.findall(r"<title>([^<]+)</title>", text)
                                        if video_ids:
                                            latest_id = video_ids[0]
                                            latest_title = titles[1] if len(titles) > 1 else "New Video"
                                            last_tracked = g["tracked_youtube"].get(yt_channel, "")
                                            if latest_id != last_tracked:
                                                embed = discord.Embed(
                                                    title=f"🔴 New YouTube Upload!",
                                                    description=f"**{latest_title}**",
                                                    url=f"https://youtube.com/watch?v={latest_id}",
                                                    color=discord.Color.red()
                                                )
                                                embed.add_field(name="Channel", value=yt_channel)
                                                embed.set_footer(text="YouTube Alert • Ghost VR Bot")
                                                await alert_channel.send(f"@everyone 🔴 **{yt_channel}** posted on YouTube!", embed=embed)
                                                g["tracked_youtube"][yt_channel] = latest_id
                    except Exception as e:
                        print(f"[YouTube] Error checking {yt_channel}: {e}")

                save_data(db)
    except Exception as e:
        print(f"[YouTube Check Error] {e}")

async def check_tiktok_streams():
    """Check TikTok live status by scraping public profile page."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            for guild in bot.guilds:
                g = get_guild_data(guild.id)
                tiktok_users = g.get("tiktok_users", [])
                ch_id = g.get("stream_channel")
                if not tiktok_users or not ch_id:
                    continue
                alert_channel = bot.get_channel(int(ch_id))
                if not alert_channel:
                    continue

                for user in tiktok_users:
                    try:
                        url = f"https://www.tiktok.com/@{user}/live"
                        async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as r:
                            text = await r.text()
                            was_live = g["tracked_tiktok"].get(user, False)
                            # TikTok redirects away from /live if not live
                            is_live = (r.status == 200 and "LIVE" in text and "liveRoomId" in text)

                            if is_live and not was_live:
                                embed = discord.Embed(
                                    title=f"🎵 @{user} is LIVE on TikTok!",
                                    description=f"**@{user}** just started a TikTok LIVE! Come watch! 🎉",
                                    url=f"https://www.tiktok.com/@{user}/live",
                                    color=discord.Color.from_rgb(0, 0, 0)
                                )
                                embed.set_footer(text="TikTok Stream Alert • Ghost VR Bot")
                                await alert_channel.send(f"@everyone 🎵 **@{user}** is LIVE on TikTok!", embed=embed)
                                g["tracked_tiktok"][user] = True
                            elif not is_live:
                                g["tracked_tiktok"][user] = False
                    except Exception as e:
                        print(f"[TikTok] Error checking {user}: {e}")

                save_data(db)
    except Exception as e:
        print(f"[TikTok Check Error] {e}")

# ─────────────────────────────────────────────
#  XP / LEVELING
# ─────────────────────────────────────────────

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    g = get_guild_data(ctx.guild.id)
    uid = str(member.id)
    xp = g["xp"].get(uid, 0)
    level = g["levels"].get(uid, 1)
    xp_needed = level * 100
    bar_filled = int((xp / xp_needed) * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    embed = discord.Embed(title=f"📊 {member.display_name}'s Rank", color=discord.Color.gold())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=str(level))
    embed.add_field(name="XP", value=f"{xp}/{xp_needed}")
    embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    g = get_guild_data(ctx.guild.id)
    xp_data = g.get("xp", {})
    sorted_users = sorted(xp_data.items(), key=lambda x: (g["levels"].get(x[0], 1), x[1]), reverse=True)[:10]
    embed = discord.Embed(title="🏆 Server Leaderboard", color=discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for i, (uid, xp) in enumerate(sorted_users):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User#{uid[:4]}"
        level = g["levels"].get(uid, 1)
        embed.add_field(name=f"{medals[i]} #{i+1} {name}", value=f"Level {level} • {xp} XP", inline=False)
    await ctx.send(embed=embed)

# ─────────────────────────────────────────────
#  GIVEAWAYS
# ─────────────────────────────────────────────

@bot.command()
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, duration: int, winners: int, *, prize: str):
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration)
    embed = discord.Embed(
        title="🎉 GIVEAWAY!",
        description=f"**Prize:** {prize}\n\nReact with 🎉 to enter!\n\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold(),
        timestamp=end_time
    )
    embed.set_footer(text="Ends at")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    g = get_guild_data(ctx.guild.id)
    g["giveaways"][str(msg.id)] = {
        "prize": prize, "winners": winners,
        "end_time": end_time.isoformat(), "channel_id": str(ctx.channel.id)
    }
    save_data(db)

    await asyncio.sleep(duration * 60)

    msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    users = [u async for u in reaction.users() if not u.bot]

    if not users:
        await ctx.send("🎉 No one entered the giveaway!")
        return

    actual_winners = random.sample(users, min(winners, len(users)))
    winner_mentions = ", ".join(w.mention for w in actual_winners)
    win_embed = discord.Embed(
        title="🎉 Giveaway Ended!",
        description=f"**Prize:** {prize}\n**Winners:** {winner_mentions}\n\nCongratulations! 🥳",
        color=discord.Color.gold()
    )
    await ctx.send(embed=win_embed)

# ─────────────────────────────────────────────
#  POLLS
# ─────────────────────────────────────────────

@bot.command()
async def poll(ctx, question, *options):
    if len(options) < 2:
        await ctx.send("⚠️ Provide at least 2 options. Example: `!poll \"Best color?\" Red Blue Green`")
        return
    if len(options) > 10:
        await ctx.send("⚠️ Max 10 options.")
        return
    number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    description = "\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    embed.set_footer(text=f"Poll by {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    for i in range(len(options)):
        await msg.add_reaction(number_emojis[i])

# ─────────────────────────────────────────────
#  TICKETS
# ─────────────────────────────────────────────

@bot.command()
async def ticket(ctx, *, reason="No reason specified"):
    guild = ctx.guild
    category = discord.utils.get(guild.categories, name="Support Tickets")
    if not category:
        category = await guild.create_category("Support Tickets")

    ticket_channel = await guild.create_text_channel(
        f"ticket-{ctx.author.name}",
        category=category,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    )
    embed = discord.Embed(
        title="🎟️ Support Ticket",
        description=f"Thank you {ctx.author.mention}! Support will be with you shortly.\n**Reason:** {reason}\n\nType `!closeticket` to close this ticket.",
        color=discord.Color.green()
    )
    await ticket_channel.send(embed=embed)
    await ctx.send(f"✅ Ticket created: {ticket_channel.mention}", delete_after=10)

@bot.command()
async def closeticket(ctx):
    if "ticket-" in ctx.channel.name:
        await ctx.send("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("⚠️ This isn't a ticket channel.")

# ─────────────────────────────────────────────
#  FUN COMMANDS
# ─────────────────────────────────────────────

@bot.command(name="8ball")
async def eightball(ctx, *, question):
    responses = [
        "✅ It is certain.", "✅ Absolutely yes!", "✅ Without a doubt.",
        "✅ Yes, definitely!", "✅ Signs point to yes.",
        "❓ Reply hazy, try again.", "❓ Ask again later.", "❓ Cannot predict now.",
        "❌ Don't count on it.", "❌ Very doubtful.", "❌ My sources say no.", "❌ Outlook not so good."
    ]
    embed = discord.Embed(title="🎱 8-Ball", color=discord.Color.dark_purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def coinflip(ctx):
    result = random.choice(["🪙 Heads!", "🪙 Tails!"])
    await ctx.send(result)

@bot.command()
async def roll(ctx, sides: int = 6):
    result = random.randint(1, sides)
    await ctx.send(f"🎲 You rolled a **{result}** (d{sides})")

@bot.command()
async def ship(ctx, user1: discord.Member, user2: discord.Member = None):
    user2 = user2 or ctx.author
    score = random.randint(0, 100)
    bar_filled = int(score / 10) * 2
    bar = "❤️" * (bar_filled // 2) + "🖤" * (10 - bar_filled // 2)
    embed = discord.Embed(title="💘 Love Meter", color=discord.Color.red())
    embed.description = f"**{user1.display_name}** & **{user2.display_name}**\n\n{bar}\n\n**{score}% compatible!**"
    await ctx.send(embed=embed)

@bot.command()
async def roast(ctx, member: discord.Member = None):
    member = member or ctx.author
    roasts = [
        f"{member.mention}, you're the reason they put instructions on shampoo.",
        f"{member.mention}, I'd agree with you but then we'd both be wrong.",
        f"{member.mention}, your WiFi password is probably your only secret.",
        f"{member.mention}, you have your entire life to be a jerk. Why not take today off?",
        f"{member.mention}, I'd call you a tool, but even tools are useful.",
    ]
    await ctx.send(random.choice(roasts))

@bot.command()
async def hug(ctx, member: discord.Member):
    await ctx.send(f"🤗 {ctx.author.mention} hugs {member.mention}!")

@bot.command()
async def slap(ctx, member: discord.Member):
    await ctx.send(f"👋 {ctx.author.mention} slapped {member.mention}! That's gotta hurt!")

@bot.command()
async def meme(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as r:
            if r.status == 200:
                data = await r.json()
                embed = discord.Embed(title=data["title"], color=discord.Color.random())
                embed.set_image(url=data["url"])
                embed.set_footer(text=f"r/{data['subreddit']} • 👍 {data['ups']}")
                await ctx.send(embed=embed)
            else:
                await ctx.send("Couldn't fetch a meme right now, try again!")

@bot.command()
async def joke(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://official-joke-api.appspot.com/random_joke") as r:
            if r.status == 200:
                data = await r.json()
                embed = discord.Embed(title="😂 Joke", description=f"{data['setup']}\n\n||{data['punchline']}||", color=discord.Color.green())
                await ctx.send(embed=embed)

# ─────────────────────────────────────────────
#  INFO COMMANDS
# ─────────────────────────────────────────────

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"📊 {g.name}", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="👑 Owner", value=str(g.owner))
    embed.add_field(name="👥 Members", value=str(g.member_count))
    embed.add_field(name="💬 Channels", value=str(len(g.channels)))
    embed.add_field(name="🎭 Roles", value=str(len(g.roles)))
    embed.add_field(name="📅 Created", value=g.created_at.strftime("%b %d, %Y"))
    embed.add_field(name="🆔 ID", value=str(g.id))
    embed.add_field(name="🚀 Boosts", value=str(g.premium_subscription_count))
    embed.add_field(name="😀 Emojis", value=str(len(g.emojis)))
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color, timestamp=datetime.datetime.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID", value=str(member.id))
    embed.add_field(name="📅 Joined Server", value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "Unknown")
    embed.add_field(name="📅 Account Created", value=member.created_at.strftime("%b %d, %Y"))
    embed.add_field(name="🎭 Roles", value=" ".join(roles) if roles else "None", inline=False)
    embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No")
    g = get_guild_data(ctx.guild.id)
    uid = str(member.id)
    embed.add_field(name="⚡ Level", value=str(g["levels"].get(uid, 1)))
    embed.add_field(name="✨ XP", value=str(g["xp"].get(uid, 0)))
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
async def uptime(ctx):
    seconds = int(time.time() - START_TIME)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    embed = discord.Embed(title="⏱️ Uptime", description=f"**{days}d {hours}h {minutes}m {seconds}s**", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
async def botinfo(ctx):
    embed = discord.Embed(title="🤖 Bot Info", color=discord.Color.blurple())
    embed.add_field(name="Version", value=BOT_VERSION)
    embed.add_field(name="Servers", value=str(len(bot.guilds)))
    embed.add_field(name="Users", value=str(sum(g.member_count for g in bot.guilds)))
    embed.add_field(name="Commands", value=str(len(bot.commands)))
    embed.add_field(name="Prefix", value=PREFIX)
    embed.set_footer(text="Made with ❤️ for Ghost VR")
    await ctx.send(embed=embed)

# ─────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────

@bot.command()
async def afk(ctx, *, reason="AFK"):
    g = get_guild_data(ctx.guild.id)
    g["afk"][str(ctx.author.id)] = reason
    save_data(db)
    await ctx.send(f"💤 {ctx.author.mention} is now AFK: **{reason}**")

@bot.command()
async def remind(ctx, duration: int, unit: str, *, reminder: str):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if unit not in units:
        await ctx.send("⚠️ Use: s (seconds), m (minutes), h (hours), d (days). Example: `!remind 30 m Take a break`")
        return
    seconds = duration * units[unit]
    await ctx.send(f"⏰ I'll remind you in **{duration}{unit}**: {reminder}")
    await asyncio.sleep(seconds)
    await ctx.send(f"⏰ {ctx.author.mention} Reminder: **{reminder}**")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=discord.Color.blurple())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, *, role: discord.Role):
    await member.add_roles(role)
    await ctx.send(f"✅ Gave {role.mention} to {member.mention}.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send(f"✅ Removed {role.mention} from {member.mention}.")

@bot.command()
async def ask(ctx, *, question):
    """Simple AI-powered Q&A"""
    thinking_msg = await ctx.send("🤔 Thinking...")
    # Smart rule-based responses + fun fallback
    q = question.lower()
    if any(w in q for w in ["hello", "hi", "hey", "sup"]):
        answer = f"Hey {ctx.author.display_name}! 👋 What's up?"
    elif "how are you" in q:
        answer = "I'm doing great, thanks for asking! Ready to help 🚀"
    elif "who made you" in q or "who created you" in q:
        answer = "I was built by **Ghost VR** — the most powerful Discord bot ever made! 👑"
    elif "what can you do" in q:
        answer = "Type `!help` to see everything I can do — and it's a LOT! 😎"
    elif "time" in q:
        answer = f"Current UTC time: **{datetime.datetime.utcnow().strftime('%H:%M:%S')}**"
    elif "date" in q:
        answer = f"Today is **{datetime.datetime.utcnow().strftime('%A, %B %d, %Y')}** (UTC)"
    else:
        answer = f"That's a great question! Unfortunately I can't search the internet, but your question was: *{question}*. Try asking your community! 🤝"
    embed = discord.Embed(title="🤖 Answer", description=answer, color=discord.Color.blurple())
    embed.set_footer(text=f"Asked by {ctx.author.display_name}")
    await thinking_msg.edit(content=None, embed=embed)

@tasks.loop(minutes=1)
async def check_reminders():
    pass  # Handled inline with asyncio.sleep in !remind

# ─────────────────────────────────────────────
#  AUTOMOD CONFIG
# ─────────────────────────────────────────────

@bot.command()
@commands.has_permissions(manage_guild=True)
async def automod(ctx, setting: str, value: str = None):
    g = get_guild_data(ctx.guild.id)
    am = g["automod"]
    setting = setting.lower()
    if setting == "spam":
        am["spam"] = value != "off"
        await ctx.send(f"✅ Spam filter: **{'ON' if am['spam'] else 'OFF'}**")
    elif setting == "caps":
        am["caps"] = value != "off"
        await ctx.send(f"✅ Caps filter: **{'ON' if am['caps'] else 'OFF'}**")
    elif setting == "addbadword" and value:
        if value not in am["badwords"]:
            am["badwords"].append(value.lower())
        await ctx.send(f"✅ Added `{value}` to bad words list.")
    elif setting == "removebadword" and value:
        if value.lower() in am["badwords"]:
            am["badwords"].remove(value.lower())
        await ctx.send(f"✅ Removed `{value}` from bad words list.")
    elif setting == "status":
        embed = discord.Embed(title="🛡️ Auto-Mod Status", color=discord.Color.green())
        embed.add_field(name="Spam Filter", value="✅ ON" if am["spam"] else "❌ OFF")
        embed.add_field(name="Caps Filter", value="✅ ON" if am["caps"] else "❌ OFF")
        embed.add_field(name="Bad Words", value=str(len(am["badwords"])) + " words")
        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Usage: `!automod spam on/off` | `!automod caps on/off` | `!automod addbadword <word>` | `!automod status`")
    save_data(db)

# ─────────────────────────────────────────────
#  HELP COMMAND
# ─────────────────────────────────────────────

@bot.command()
async def help(ctx, category: str = None):
    if category is None:
        embed = discord.Embed(
            title="👑 Ghost VR Bot — Command Help",
            description="The most powerful Discord bot ever made! Use `!help <category>` for details.",
            color=discord.Color.gold()
        )
        embed.add_field(name="🔨 Moderation", value="`!help mod`", inline=True)
        embed.add_field(name="📢 Announcements", value="`!help announce`", inline=True)
        embed.add_field(name="🔴 Streams", value="`!help stream`", inline=True)
        embed.add_field(name="⚡ Leveling", value="`!help level`", inline=True)
        embed.add_field(name="🎉 Giveaways", value="`!help give`", inline=True)
        embed.add_field(name="📊 Polls", value="`!help poll`", inline=True)
        embed.add_field(name="🎟️ Tickets", value="`!help ticket`", inline=True)
        embed.add_field(name="😂 Fun", value="`!help fun`", inline=True)
        embed.add_field(name="🛡️ Auto-Mod", value="`!help automod`", inline=True)
        embed.add_field(name="🔧 Utility", value="`!help util`", inline=True)
        embed.set_footer(text=f"Ghost VR Bot v{BOT_VERSION} | Prefix: {PREFIX}")
        await ctx.send(embed=embed)
        return

    cat = category.lower()
    embed = discord.Embed(color=discord.Color.gold())

    if cat == "mod":
        embed.title = "🔨 Moderation Commands"
        embed.description = (
            "`!ban @user [reason]` — Ban a member\n"
            "`!kick @user [reason]` — Kick a member\n"
            "`!mute @user [minutes] [reason]` — Mute a member\n"
            "`!unmute @user` — Unmute a member\n"
            "`!warn @user [reason]` — Warn a member\n"
            "`!warnings [@user]` — View warnings\n"
            "`!clearwarnings @user` — Clear warnings\n"
            "`!purge <amount>` — Delete messages\n"
            "`!lockdown [reason]` — Lock channel\n"
            "`!unlock` — Unlock channel\n"
            "`!nick @user <name>` — Change nickname\n"
            "`!giverole @user @role` — Give role\n"
            "`!removerole @user @role` — Remove role"
        )
    elif cat == "announce":
        embed.title = "📢 Announcement Commands"
        embed.description = (
            "`!announce #channel <message>` — Send an @everyone announcement\n"
            "`!embed #channel <title> <description>` — Send a custom embed\n"
            "`!setwelcome #channel [message]` — Set welcome channel"
        )
    elif cat == "stream":
        embed.title = "🔴 Stream Alert Commands"
        embed.description = (
            "`!setstreamchannel #channel` — Set the stream alerts channel\n"
            "`!addstreamer <twitch_username>` — Track a streamer\n"
            "`!removestreamer <twitch_username>` — Stop tracking\n"
            "`!streamers` — List tracked streamers\n\n"
            "⚠️ Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET env vars"
        )
    elif cat == "level":
        embed.title = "⚡ Leveling Commands"
        embed.description = (
            "`!rank [@user]` — View your rank/XP\n"
            "`!leaderboard` — Top 10 XP leaderboard"
        )
    elif cat == "give":
        embed.title = "🎉 Giveaway Commands"
        embed.description = "`!giveaway <minutes> <winners> <prize>` — Start a giveaway"
    elif cat == "poll":
        embed.title = "📊 Poll Commands"
        embed.description = '`!poll "Question" Option1 Option2 ...` — Create a poll (up to 10 options)'
    elif cat == "ticket":
        embed.title = "🎟️ Ticket Commands"
        embed.description = (
            "`!ticket [reason]` — Open a support ticket\n"
            "`!closeticket` — Close the current ticket"
        )
    elif cat == "fun":
        embed.title = "😂 Fun Commands"
        embed.description = (
            "`!8ball <question>` — Ask the magic 8ball\n"
            "`!coinflip` — Flip a coin\n"
            "`!roll [sides]` — Roll a dice\n"
            "`!ship @user1 [@user2]` — Check compatibility\n"
            "`!roast [@user]` — Roast someone\n"
            "`!hug @user` — Hug someone\n"
            "`!slap @user` — Slap someone\n"
            "`!meme` — Random meme\n"
            "`!joke` — Random joke\n"
            "`!ask <question>` — Ask the bot anything"
        )
    elif cat == "automod":
        embed.title = "🛡️ Auto-Mod Commands"
        embed.description = (
            "`!automod spam on/off` — Toggle spam filter\n"
            "`!automod caps on/off` — Toggle caps filter\n"
            "`!automod addbadword <word>` — Add a banned word\n"
            "`!automod removebadword <word>` — Remove a banned word\n"
            "`!automod status` — View current settings"
        )
    elif cat == "util":
        embed.title = "🔧 Utility Commands"
        embed.description = (
            "`!serverinfo` — Server information\n"
            "`!userinfo [@user]` — User information\n"
            "`!avatar [@user]` — View avatar\n"
            "`!ping` — Bot latency\n"
            "`!uptime` — Bot uptime\n"
            "`!botinfo` — Bot information\n"
            "`!afk [reason]` — Set AFK status\n"
            "`!remind <time> <s/m/h/d> <reminder>` — Set a reminder"
        )
    await ctx.send(embed=embed)

# ─────────────────────────────────────────────
#  ERROR HANDLER
# ─────────────────────────────────────────────

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found. Try mentioning them directly.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Use `!help` for usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands silently
    else:
        print(f"[Error] {error}")

# ─────────────────────────────────────────────
#  KEEP-ALIVE WEB SERVER (required for Render)
# ─────────────────────────────────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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
#  LAUNCH
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN not set!")
        sys.exit(1)
    print("🚀 Starting Ghost VR's Ultimate Discord Bot...")
    threading.Thread(target=run_server, daemon=True).start()
    bot.run(TOKEN)

