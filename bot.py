#!/usr/bin/env python3
"""
Nexora Bot v4.0 — Rock Solid Edition
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import aiohttp
import os
import json
import random
import time
import xml.etree.ElementTree as ET
import re
import traceback
from collections import defaultdict

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1515543797247770654"
BOT_WEBSITE = "https://nexorabot-e5b5g6zd.manus.space/"
START_TIME = time.time()

# ─────────────────────────────────────────────
#  STORAGE
# ─────────────────────────────────────────────
DATA_FILE = "/tmp/nexora_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[SaveData Error] {e}")

db = load_data()

def get_guild(guild_id):
    gid = str(guild_id)
    if gid not in db:
        db[gid] = {}
    g = db[gid]
    defaults = {
        "xp": {}, "levels": {}, "warnings": {},
        "welcome_channel": None,
        "welcome_msg": "Welcome {user} to **{server}**! 🎉",
        "leave_channel": None,
        "leave_msg": "**{user}** has left **{server}**. 😢",
        "log_channel": None,
        "twitch_streamers_v2": {},
        "youtube_channels": {},
        "tiktok_accounts": {},
        "tickets": {},
        "ticket_panels": {},
        "automod": {"spam": False, "caps": False, "badwords": []},
        "afk": {},
        "reminders": [],
        "giveaways": {},
    }
    for key, val in defaults.items():
        if key not in g:
            g[key] = val
    save_data(db)
    return g

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
spam_tracker = defaultdict(list)

# ─────────────────────────────────────────────
#  ERROR HANDLER — catches ALL interaction errors
# ─────────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    tb = traceback.format_exc()
    print(f"[SlashCmd Error] {error}\n{tb}")
    msg = f"❌ An error occurred: `{str(error)}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except:
        pass

# ─────────────────────────────────────────────
#  ON READY
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"  Nexora Bot v4.0 ONLINE!")
    print(f"  Logged in as: {bot.user} (ID: {bot.user.id})")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"{'='*50}")
    try:
        synced = await bot.tree.sync()
        print(f"  Synced {len(synced)} slash commands globally")
        for cmd in synced:
            print(f"    /{cmd.name}")
    except Exception as e:
        print(f"  Slash sync error: {e}")
        traceback.print_exc()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers | /help"
        )
    )
    # Start background tasks
    if not check_streams.is_running():
        check_streams.start()
    if not check_youtube.is_running():
        check_youtube.start()
    if not check_tiktok.is_running():
        check_tiktok.start()
    if not check_reminders.is_running():
        check_reminders.start()
    if not check_giveaways.is_running():
        check_giveaways.start()

# ─────────────────────────────────────────────
#  ON MESSAGE
# ─────────────────────────────────────────────
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    g = get_guild(message.guild.id)
    uid = str(message.author.id)

    # AFK notifications
    for mentioned in message.mentions:
        mid = str(mentioned.id)
        if mid in g["afk"]:
            try:
                await message.channel.send(
                    embed=discord.Embed(
                        description=f"💤 **{mentioned.display_name}** is AFK: {g['afk'][mid]}",
                        color=discord.Color.orange()
                    ), delete_after=10
                )
            except:
                pass

    if uid in g["afk"]:
        del g["afk"][uid]
        save_data(db)
        try:
            await message.channel.send(f"✅ Welcome back {message.author.mention}! AFK removed.", delete_after=8)
        except:
            pass

    # Automod
    am = g.get("automod", {})
    now = time.time()
    if am.get("spam"):
        spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]
        spam_tracker[uid].append(now)
        if len(spam_tracker[uid]) >= 5:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} slow down!", delete_after=5)
            except:
                pass
            return

    if am.get("caps") and len(message.content) > 10:
        caps = sum(1 for c in message.content if c.isupper()) / max(len(message.content), 1)
        if caps > 0.7:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} no excessive caps!", delete_after=5)
            except:
                pass
            return

    for word in am.get("badwords", []):
        if word.lower() in message.content.lower():
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention} watch your language!", delete_after=5)
            except:
                pass
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
        try:
            await message.channel.send(embed=discord.Embed(
                title="🎉 Level Up!",
                description=f"{message.author.mention} reached **Level {lv}**!",
                color=discord.Color.gold()
            ))
        except:
            pass
        return
    save_data(db)
    await bot.process_commands(message)

# ─────────────────────────────────────────────
#  MEMBER EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_member_join(member):
    g = get_guild(member.guild.id)
    ch_id = g.get("welcome_channel")
    if ch_id:
        ch = bot.get_channel(int(ch_id))
        if ch:
            try:
                msg = g["welcome_msg"].replace("{user}", member.mention).replace("{server}", member.guild.name)
                embed = discord.Embed(title="👋 Welcome!", description=msg, color=discord.Color.green())
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Members", value=str(member.guild.member_count))
                await ch.send(embed=embed)
            except:
                pass

@bot.event
async def on_member_remove(member):
    g = get_guild(member.guild.id)
    ch_id = g.get("leave_channel")
    if ch_id:
        ch = bot.get_channel(int(ch_id))
        if ch:
            try:
                msg = g["leave_msg"].replace("{user}", str(member)).replace("{server}", member.guild.name)
                await ch.send(embed=discord.Embed(description=msg, color=discord.Color.red()))
            except:
                pass

# ═══════════════════════════════════════════════
#  BACKGROUND TASKS
# ═══════════════════════════════════════════════
twitch_token_cache = {"token": None, "expires": 0}

async def get_twitch_token():
    if twitch_token_cache["token"] and time.time() < twitch_token_cache["expires"]:
        return twitch_token_cache["token"]
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    try:
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
    except Exception as e:
        print(f"[TwitchToken Error] {e}")
    return None

@tasks.loop(seconds=300)
async def check_streams():
    try:
        token = await get_twitch_token()
        if not token:
            return
        for guild in bot.guilds:
            g = get_guild(guild.id)
            streamers = g.get("twitch_streamers_v2", {})
            if not streamers:
                continue
            for username, info in list(streamers.items()):
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
                                embed = discord.Embed(
                                    title=f"🔴 {username} is LIVE on Twitch!",
                                    description=s.get("title", ""),
                                    url=f"https://twitch.tv/{username}",
                                    color=discord.Color.purple()
                                )
                                embed.add_field(name="Game", value=s.get("game_name", "Unknown"))
                                embed.add_field(name="Viewers", value=str(s.get("viewer_count", 0)))
                                thumb = s.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180")
                                if thumb:
                                    embed.set_image(url=thumb)
                                role_id = info.get("role_id")
                                mention = f"<@&{role_id}> " if role_id else ""
                                await ch.send(f"{mention}🔴 **{username}** just went live!", embed=embed)
                            info["live"] = is_live
                            save_data(db)
                except Exception as e:
                    print(f"[TwitchCheck Error] {username}: {e}")
    except Exception as e:
        print(f"[check_streams Error] {e}")

@tasks.loop(seconds=300)
async def check_youtube():
    try:
        for guild in bot.guilds:
            g = get_guild(guild.id)
            yt_channels = g.get("youtube_channels", {})
            if not yt_channels:
                continue
            for channel_id, info in list(yt_channels.items()):
                ch_id = info.get("discord_channel")
                if not ch_id:
                    continue
                ch = bot.get_channel(int(ch_id))
                if not ch:
                    continue
                try:
                    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                            if r.status != 200:
                                continue
                            text = await r.text()
                    root = ET.fromstring(text)
                    ns = {
                        "atom": "http://www.w3.org/2005/Atom",
                        "yt": "http://www.youtube.com/xml/schemas/2015",
                        "media": "http://search.yahoo.com/mrss/"
                    }
                    entries = root.findall("atom:entry", ns)
                    if not entries:
                        continue
                    latest = entries[0]
                    vid_id_el = latest.find("yt:videoId", ns)
                    title_el = latest.find("atom:title", ns)
                    link_el = latest.find("atom:link", ns)
                    vid_id = vid_id_el.text if vid_id_el is not None else ""
                    title = title_el.text if title_el is not None else "New Video"
                    link = link_el.get("href") if link_el is not None else f"https://youtube.com/watch?v={vid_id}"
                    last_vid = info.get("last_video_id", "")
                    if vid_id and vid_id != last_vid:
                        info["last_video_id"] = vid_id
                        save_data(db)
                        if last_vid:
                            channel_name = info.get("name", channel_id)
                            embed = discord.Embed(
                                title=f"📺 New YouTube Video!",
                                description=f"**{channel_name}** just uploaded:\n[{title}]({link})",
                                color=discord.Color.red(),
                                url=link
                            )
                            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg")
                            await ch.send(embed=embed)
                except Exception as e:
                    print(f"[YouTubeCheck Error] {channel_id}: {e}")
    except Exception as e:
        print(f"[check_youtube Error] {e}")

@tasks.loop(seconds=300)
async def check_tiktok():
    try:
        for guild in bot.guilds:
            g = get_guild(guild.id)
            accounts = g.get("tiktok_accounts", {})
            if not accounts:
                continue
            for username, info in list(accounts.items()):
                ch_id = info.get("discord_channel")
                if not ch_id:
                    continue
                ch = bot.get_channel(int(ch_id))
                if not ch:
                    continue
                try:
                    url = f"https://www.tiktok.com/@{username}"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                            if r.status != 200:
                                continue
                            text = await r.text()
                    matches = re.findall(r'"id":"(\d+)","desc":"([^"]{1,100})"', text)
                    if not matches:
                        continue
                    latest_id, latest_desc = matches[0]
                    last_vid = info.get("last_video_id", "")
                    if latest_id and latest_id != last_vid:
                        info["last_video_id"] = latest_id
                        save_data(db)
                        if last_vid:
                            vid_url = f"https://www.tiktok.com/@{username}/video/{latest_id}"
                            embed = discord.Embed(
                                title=f"📱 New TikTok Video!",
                                description=f"**@{username}** just posted:\n[{latest_desc[:100]}]({vid_url})",
                                color=discord.Color.from_rgb(10, 10, 10),
                                url=vid_url
                            )
                            await ch.send(embed=embed)
                except Exception as e:
                    print(f"[TikTokCheck Error] {username}: {e}")
    except Exception as e:
        print(f"[check_tiktok Error] {e}")

@tasks.loop(seconds=60)
async def check_reminders():
    try:
        now = time.time()
        changed = False
        for guild in bot.guilds:
            g = get_guild(guild.id)
            remaining = []
            for r in g.get("reminders", []):
                if now >= r.get("time", 0):
                    try:
                        ch = bot.get_channel(int(r["channel_id"]))
                        if ch:
                            await ch.send(f"⏰ <@{r['user_id']}> Reminder: **{r['message']}**")
                    except:
                        pass
                    changed = True
                else:
                    remaining.append(r)
            g["reminders"] = remaining
        if changed:
            save_data(db)
    except Exception as e:
        print(f"[check_reminders Error] {e}")

@tasks.loop(seconds=60)
async def check_giveaways():
    try:
        now = time.time()
        for guild in bot.guilds:
            g = get_guild(guild.id)
            for msg_id, gw in list(g.get("giveaways", {}).items()):
                if gw.get("ended"):
                    continue
                if now >= gw.get("end_time", float("inf")):
                    try:
                        ch = bot.get_channel(int(gw["channel_id"]))
                        if ch:
                            msg = await ch.fetch_message(int(msg_id))
                            reaction = discord.utils.get(msg.reactions, emoji="🎉")
                            users = [u async for u in reaction.users() if not u.bot] if reaction else []
                            if users:
                                winners = random.sample(users, min(gw.get("winners", 1), len(users)))
                                winner_mentions = ", ".join(w.mention for w in winners)
                                await ch.send(f"🎉 Giveaway ended! Winner(s): {winner_mentions}\nPrize: **{gw['prize']}**")
                            else:
                                await ch.send(f"🎉 Giveaway ended but no one entered for **{gw['prize']}**.")
                    except Exception as e:
                        print(f"[Giveaway Error] {e}")
                    gw["ended"] = True
                    save_data(db)
    except Exception as e:
        print(f"[check_giveaways Error] {e}")

# ═══════════════════════════════════════════════
#  TICKET SYSTEM
# ═══════════════════════════════════════════════
class TicketModal(discord.ui.Modal, title="Open a Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for opening a ticket",
        placeholder="Describe your issue...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, ping_role_id=None, log_channel_id=None):
        super().__init__()
        self.ping_role_id = ping_role_id
        self.log_channel_id = log_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            user = interaction.user
            g = get_guild(guild.id)
            ticket_num = len(g["tickets"]) + 1
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            if self.ping_role_id:
                role = guild.get_role(int(self.ping_role_id))
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            ch = await guild.create_text_channel(
                f"ticket-{ticket_num:04d}",
                category=None,
                overwrites=overwrites,
                topic=f"Ticket by {user} | Reason: {self.reason.value}"
            )
            g["tickets"][str(ch.id)] = {
                "user_id": str(user.id),
                "reason": self.reason.value,
                "ticket_num": ticket_num
            }
            save_data(db)

            embed = discord.Embed(
                title=f"🎫 Ticket #{ticket_num:04d}",
                description=f"**Opened by:** {user.mention}\n**Reason:** {self.reason.value}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="React or use buttons below to manage this ticket.")

            close_view = TicketCloseView()
            ping_txt = ""
            if self.ping_role_id:
                ping_txt = f"<@&{self.ping_role_id}> "
            await ch.send(f"{ping_txt}{user.mention}", embed=embed, view=close_view)

            if self.log_channel_id:
                log_ch = bot.get_channel(int(self.log_channel_id))
                if log_ch:
                    await log_ch.send(embed=discord.Embed(
                        description=f"📋 Ticket #{ticket_num:04d} opened by {user.mention} — {self.reason.value}",
                        color=discord.Color.blurple()
                    ))

            await interaction.response.send_message(f"✅ Ticket created: {ch.mention}", ephemeral=True)
        except Exception as e:
            print(f"[TicketModal Error] {e}")
            traceback.print_exc()
            try:
                await interaction.response.send_message("❌ Failed to create ticket. Please try again.", ephemeral=True)
            except:
                pass

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            g = get_guild(interaction.guild.id)
            ch_id = str(interaction.channel.id)
            if ch_id not in g["tickets"]:
                await interaction.response.send_message("⚠️ This is not a ticket channel.", ephemeral=True)
                return
            embed = discord.Embed(
                description=f"🔒 Ticket closed by {interaction.user.mention}. Channel deletes in 5s.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(5)
            del g["tickets"][ch_id]
            save_data(db)
            await interaction.channel.delete(reason="Ticket closed")
        except Exception as e:
            print(f"[CloseTicket Error] {e}")

class TicketPanelView(discord.ui.View):
    def __init__(self, ping_role_id=None, log_channel_id=None):
        super().__init__(timeout=None)
        self.ping_role_id = ping_role_id
        self.log_channel_id = log_channel_id

        btn = discord.ui.Button(
            label="Open a Ticket",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=f"open_ticket_{ping_role_id or 'none'}_{log_channel_id or 'none'}"
        )
        btn.callback = self.open_ticket_callback
        self.add_item(btn)

    async def open_ticket_callback(self, interaction: discord.Interaction):
        modal = TicketModal(
            ping_role_id=self.ping_role_id,
            log_channel_id=self.log_channel_id
        )
        await interaction.response.send_modal(modal)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — GENERAL
# ═══════════════════════════════════════════════

@bot.tree.command(name="help", description="Show all bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👑 Nexora Bot — Commands",
        description="Here's everything I can do!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📋 General", value="`/help` `/ping` `/uptime` `/invite` `/website`", inline=False)
    embed.add_field(name="👤 User", value="`/userinfo` `/serverinfo` `/rank` `/leaderboard` `/afk`", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/warnings` `/clearwarnings` `/purge` `/lockdown` `/unlock`", inline=False)
    embed.add_field(name="🎟️ Tickets", value="`/ticket-panel` `/closeticket`", inline=False)
    embed.add_field(name="🎉 Fun", value="`/giveaway` `/remind` `/8ball` `/coinflip` `/roll`", inline=False)
    embed.add_field(name="📡 Alerts", value="`/addtwitch` `/removetwitch` `/addyoutube` `/removeyoutube` `/addtiktok` `/removetiktok` `/listalerts`", inline=False)
    embed.add_field(name="⚙️ Setup", value="`/setwelcome` `/setleave` `/setlog` `/automod` `/addbadword` `/removebadword`", inline=False)
    embed.add_field(name="📺 Lookups", value="`/youtubelatest` `/tiktoklatest`", inline=False)
    embed.set_footer(text="Nexora Bot v4.0")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="Check how long the bot has been online")
async def uptime(interaction: discord.Interaction):
    seconds = int(time.time() - START_TIME)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    embed = discord.Embed(title="⏱️ Uptime", description=f"**{h}h {m}m {s}s**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Get the bot invite link")
async def invite_cmd(interaction: discord.Interaction):
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Invite Nexora Bot", url=BOT_INVITE, style=discord.ButtonStyle.link, emoji="🔗"))
    embed = discord.Embed(title="📨 Invite Nexora", description="Click below to add me to your server!", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="website", description="Get the bot website link")
async def website_cmd(interaction: discord.Interaction):
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Visit Website", url=BOT_WEBSITE, style=discord.ButtonStyle.link, emoji="🌐"))
    embed = discord.Embed(title="🌐 Nexora Website", description="Click below to visit our website!", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="serverinfo", description="Show server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏠 {guild.name}", color=discord.Color.blurple())
    embed.add_field(name="Owner", value=str(guild.owner))
    embed.add_field(name="Members", value=str(guild.member_count))
    embed.add_field(name="Channels", value=str(len(guild.channels)))
    embed.add_field(name="Roles", value=str(len(guild.roles)))
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"))
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Show info about a user")
@app_commands.describe(member="The user to check")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color)
    embed.add_field(name="ID", value=str(member.id))
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown")
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
    embed.add_field(name="Roles", value=str(len(member.roles) - 1))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="Check your XP rank")
@app_commands.describe(member="The user to check")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    g = get_guild(interaction.guild.id)
    uid = str(member.id)
    xp = g["xp"].get(uid, 0)
    level = g["levels"].get(uid, 1)
    needed = level * 100
    embed = discord.Embed(title=f"⭐ {member.display_name}'s Rank", color=discord.Color.gold())
    embed.add_field(name="Level", value=str(level))
    embed.add_field(name="XP", value=f"{xp}/{needed}")
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Show the XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    g = get_guild(interaction.guild.id)
    sorted_users = sorted(g["xp"].items(), key=lambda x: (g["levels"].get(x[0], 1), x[1]), reverse=True)[:10]
    embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, xp) in enumerate(sorted_users):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"Unknown ({uid})"
        medal = medals[i] if i < 3 else f"{i+1}."
        lv = g["levels"].get(uid, 1)
        lines.append(f"{medal} **{name}** — Level {lv} ({xp} XP)")
    embed.description = "\n".join(lines) if lines else "No data yet!"
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="afk", description="Set your AFK status")
@app_commands.describe(reason="Your AFK reason")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    g = get_guild(interaction.guild.id)
    g["afk"][str(interaction.user.id)] = reason
    save_data(db)
    await interaction.response.send_message(f"💤 You're now AFK: **{reason}**")

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — MODERATION
# ═══════════════════════════════════════════════

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.describe(member="Member to ban", reason="Reason for ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    embed = discord.Embed(description=f"🔨 **{member}** has been banned.\nReason: {reason}", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(member="Member to kick", reason="Reason for kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    embed = discord.Embed(description=f"👢 **{member}** has been kicked.\nReason: {reason}", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mute", description="Timeout a member")
@app_commands.describe(member="Member to mute", minutes="Duration in minutes")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10):
    until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(until, reason=f"Muted by {interaction.user}")
    embed = discord.Embed(description=f"🔇 **{member}** muted for {minutes} minutes.", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unmute", description="Remove timeout from a member")
@app_commands.describe(member="Member to unmute")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"✅ {member.mention} has been unmuted.")

@bot.tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="Member to warn", reason="Reason")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    g = get_guild(interaction.guild.id)
    uid = str(member.id)
    if uid not in g["warnings"]:
        g["warnings"][uid] = []
    g["warnings"][uid].append({"reason": reason, "by": str(interaction.user), "time": time.time()})
    save_data(db)
    count = len(g["warnings"][uid])
    embed = discord.Embed(description=f"⚠️ **{member}** warned. Total: {count}\nReason: {reason}", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warnings", description="Check warnings for a member")
@app_commands.describe(member="Member to check")
@app_commands.checks.has_permissions(manage_messages=True)
async def warnings_cmd(interaction: discord.Interaction, member: discord.Member):
    g = get_guild(interaction.guild.id)
    warns = g["warnings"].get(str(member.id), [])
    if not warns:
        await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.yellow())
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"#{i}", value=f"{w['reason']} — by {w['by']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarnings", description="Clear all warnings for a member")
@app_commands.describe(member="Member to clear")
@app_commands.checks.has_permissions(manage_messages=True)
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    g = get_guild(interaction.guild.id)
    g["warnings"][str(member.id)] = []
    save_data(db)
    await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}.")

@bot.tree.command(name="purge", description="Delete multiple messages")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if not 1 <= amount <= 100:
        await interaction.response.send_message("⚠️ Amount must be between 1 and 100.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="lockdown", description="Lock the current channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def lockdown(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel has been locked down.")

@bot.tree.command(name="unlock", description="Unlock the current channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
    await interaction.response.send_message("🔓 Channel has been unlocked.")

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — TICKETS
# ═══════════════════════════════════════════════

@bot.tree.command(name="ticket-panel", description="Create a ticket panel in this channel")
@app_commands.describe(
    title="Panel title",
    description="Panel description",
    ping_role="Role to ping when a ticket is opened",
    log_channel="Channel to log ticket activity"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def ticket_panel(
    interaction: discord.Interaction,
    title: str = "🎫 Support Tickets",
    description: str = "Click below to open a support ticket.",
    ping_role: discord.Role = None,
    log_channel: discord.TextChannel = None
):
    ping_role_id = str(ping_role.id) if ping_role else None
    log_channel_id = str(log_channel.id) if log_channel else None
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
    embed.set_footer(text="Nexora Bot • Ticket System")
    view = TicketPanelView(ping_role_id=ping_role_id, log_channel_id=log_channel_id)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Ticket panel created!", ephemeral=True)

@bot.tree.command(name="closeticket", description="Close the current ticket channel")
async def closeticket(interaction: discord.Interaction):
    g = get_guild(interaction.guild.id)
    ch_id = str(interaction.channel.id)
    if ch_id not in g["tickets"]:
        await interaction.response.send_message("⚠️ This is not a ticket channel.", ephemeral=True)
        return
    await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
    await asyncio.sleep(5)
    del g["tickets"][ch_id]
    save_data(db)
    await interaction.channel.delete(reason="Ticket closed")

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — FUN
# ═══════════════════════════════════════════════

@bot.tree.command(name="8ball", description="Ask the magic 8-ball")
@app_commands.describe(question="Your question")
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        "✅ It is certain.", "✅ Yes, definitely!", "✅ Without a doubt.",
        "✅ Most likely.", "🤷 Ask again later.", "🤷 Cannot predict now.",
        "❌ Don't count on it.", "❌ Very doubtful.", "❌ My sources say no."
    ]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.dark_blue())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads 🪙", "Tails 🔄"])
    embed = discord.Embed(title="🪙 Coin Flip", description=f"Result: **{result}**", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="roll", description="Roll a dice")
@app_commands.describe(sides="Number of sides (default: 6)")
async def roll(interaction: discord.Interaction, sides: int = 6):
    result = random.randint(1, max(2, sides))
    embed = discord.Embed(title="🎲 Dice Roll", description=f"Rolled a **{sides}**-sided die: **{result}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remind", description="Set a reminder")
@app_commands.describe(minutes="Minutes until reminder", message="What to remind you about")
async def remind(interaction: discord.Interaction, minutes: int, message: str):
    g = get_guild(interaction.guild.id)
    remind_time = time.time() + (minutes * 60)
    g["reminders"].append({
        "user_id": str(interaction.user.id),
        "channel_id": str(interaction.channel.id),
        "message": message,
        "time": remind_time
    })
    save_data(db)
    embed = discord.Embed(
        title="⏰ Reminder Set",
        description=f"I'll remind you in **{minutes} minute(s)**: {message}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    prize="What you're giving away",
    minutes="Duration in minutes",
    winners="Number of winners"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def giveaway(interaction: discord.Interaction, prize: str, minutes: int, winners: int = 1):
    end_time = time.time() + (minutes * 60)
    embed = discord.Embed(
        title="🎉 GIVEAWAY!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends in:** {minutes} minutes\n\nReact with 🎉 to enter!",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("🎉")
    g = get_guild(interaction.guild.id)
    g["giveaways"][str(msg.id)] = {
        "prize": prize,
        "channel_id": str(interaction.channel.id),
        "end_time": end_time,
        "winners": winners,
        "ended": False
    }
    save_data(db)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — ALERTS (Twitch / YouTube / TikTok)
# ═══════════════════════════════════════════════

@bot.tree.command(name="addtwitch", description="Track a Twitch streamer for live alerts")
@app_commands.describe(username="Twitch username", channel="Channel to send alerts", role="Role to ping (optional)")
@app_commands.checks.has_permissions(manage_guild=True)
async def addtwitch(interaction: discord.Interaction, username: str, channel: discord.TextChannel, role: discord.Role = None):
    g = get_guild(interaction.guild.id)
    g["twitch_streamers_v2"][username.lower()] = {
        "channel_id": str(channel.id),
        "role_id": str(role.id) if role else None,
        "live": False
    }
    save_data(db)
    await interaction.response.send_message(f"✅ Now tracking **{username}** on Twitch → {channel.mention}")

@bot.tree.command(name="removetwitch", description="Remove a Twitch streamer alert")
@app_commands.describe(username="Twitch username to remove")
@app_commands.checks.has_permissions(manage_guild=True)
async def removetwitch(interaction: discord.Interaction, username: str):
    g = get_guild(interaction.guild.id)
    if username.lower() in g["twitch_streamers_v2"]:
        del g["twitch_streamers_v2"][username.lower()]
        save_data(db)
        await interaction.response.send_message(f"✅ Removed Twitch alert for **{username}**.")
    else:
        await interaction.response.send_message(f"❌ **{username}** not found.", ephemeral=True)

@bot.tree.command(name="addyoutube", description="Track a YouTube channel for new video alerts")
@app_commands.describe(channel_id="YouTube channel ID", channel="Discord channel to send alerts", name="Display name for the channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def addyoutube(interaction: discord.Interaction, channel_id: str, channel: discord.TextChannel, name: str = ""):
    g = get_guild(interaction.guild.id)
    g["youtube_channels"][channel_id] = {
        "discord_channel": str(channel.id),
        "name": name or channel_id,
        "last_video_id": ""
    }
    save_data(db)
    await interaction.response.send_message(f"✅ Now tracking YouTube channel `{channel_id}` → {channel.mention}")

@bot.tree.command(name="removeyoutube", description="Remove a YouTube channel alert")
@app_commands.describe(channel_id="YouTube channel ID to remove")
@app_commands.checks.has_permissions(manage_guild=True)
async def removeyoutube(interaction: discord.Interaction, channel_id: str):
    g = get_guild(interaction.guild.id)
    if channel_id in g["youtube_channels"]:
        del g["youtube_channels"][channel_id]
        save_data(db)
        await interaction.response.send_message(f"✅ Removed YouTube alert for `{channel_id}`.")
    else:
        await interaction.response.send_message(f"❌ Not found.", ephemeral=True)

@bot.tree.command(name="addtiktok", description="Track a TikTok account for new video alerts")
@app_commands.describe(username="TikTok username (without @)", channel="Discord channel to send alerts")
@app_commands.checks.has_permissions(manage_guild=True)
async def addtiktok(interaction: discord.Interaction, username: str, channel: discord.TextChannel):
    g = get_guild(interaction.guild.id)
    g["tiktok_accounts"][username.lstrip("@")] = {
        "discord_channel": str(channel.id),
        "last_video_id": ""
    }
    save_data(db)
    await interaction.response.send_message(f"✅ Now tracking TikTok **@{username}** → {channel.mention}")

@bot.tree.command(name="removetiktok", description="Remove a TikTok account alert")
@app_commands.describe(username="TikTok username to remove")
@app_commands.checks.has_permissions(manage_guild=True)
async def removetiktok(interaction: discord.Interaction, username: str):
    g = get_guild(interaction.guild.id)
    uname = username.lstrip("@")
    if uname in g["tiktok_accounts"]:
        del g["tiktok_accounts"][uname]
        save_data(db)
        await interaction.response.send_message(f"✅ Removed TikTok alert for **@{uname}**.")
    else:
        await interaction.response.send_message(f"❌ Not found.", ephemeral=True)

@bot.tree.command(name="listalerts", description="List all active stream/video alerts")
async def listalerts(interaction: discord.Interaction):
    g = get_guild(interaction.guild.id)
    embed = discord.Embed(title="📡 Active Alerts", color=discord.Color.blurple())
    twitch_list = "\n".join(f"• {u}" for u in g["twitch_streamers_v2"]) or "None"
    yt_list = "\n".join(f"• {info.get('name', cid)}" for cid, info in g["youtube_channels"].items()) or "None"
    tt_list = "\n".join(f"• @{u}" for u in g["tiktok_accounts"]) or "None"
    embed.add_field(name="🟣 Twitch", value=twitch_list, inline=False)
    embed.add_field(name="🔴 YouTube", value=yt_list, inline=False)
    embed.add_field(name="⚫ TikTok", value=tt_list, inline=False)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — SETUP
# ═══════════════════════════════════════════════

@bot.tree.command(name="setwelcome", description="Set the welcome channel and message")
@app_commands.describe(channel="Welcome channel", message="Welcome message (use {user} and {server})")
@app_commands.checks.has_permissions(manage_guild=True)
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str = "Welcome {user} to **{server}**! 🎉"):
    g = get_guild(interaction.guild.id)
    g["welcome_channel"] = str(channel.id)
    g["welcome_msg"] = message
    save_data(db)
    await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")

@bot.tree.command(name="setleave", description="Set the leave channel and message")
@app_commands.describe(channel="Leave channel", message="Leave message (use {user} and {server})")
@app_commands.checks.has_permissions(manage_guild=True)
async def setleave(interaction: discord.Interaction, channel: discord.TextChannel, message: str = "**{user}** has left **{server}**. 😢"):
    g = get_guild(interaction.guild.id)
    g["leave_channel"] = str(channel.id)
    g["leave_msg"] = message
    save_data(db)
    await interaction.response.send_message(f"✅ Leave channel set to {channel.mention}")

@bot.tree.command(name="setlog", description="Set the log channel")
@app_commands.describe(channel="Log channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    g = get_guild(interaction.guild.id)
    g["log_channel"] = str(channel.id)
    save_data(db)
    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}")

@bot.tree.command(name="automod", description="Toggle automod features")
@app_commands.describe(feature="Feature to toggle", enabled="Enable or disable")
@app_commands.choices(feature=[
    app_commands.Choice(name="Anti-Spam", value="spam"),
    app_commands.Choice(name="Anti-Caps", value="caps"),
])
@app_commands.checks.has_permissions(manage_guild=True)
async def automod(interaction: discord.Interaction, feature: str, enabled: bool):
    g = get_guild(interaction.guild.id)
    g["automod"][feature] = enabled
    save_data(db)
    status = "enabled ✅" if enabled else "disabled ❌"
    await interaction.response.send_message(f"Automod **{feature}** is now {status}")

@bot.tree.command(name="addbadword", description="Add a word to the bad words filter")
@app_commands.describe(word="Word to block")
@app_commands.checks.has_permissions(manage_guild=True)
async def addbadword(interaction: discord.Interaction, word: str):
    g = get_guild(interaction.guild.id)
    if word.lower() not in g["automod"]["badwords"]:
        g["automod"]["badwords"].append(word.lower())
        save_data(db)
        await interaction.response.send_message(f"✅ Added `{word}` to the bad words filter.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ That word is already in the filter.", ephemeral=True)

@bot.tree.command(name="removebadword", description="Remove a word from the bad words filter")
@app_commands.describe(word="Word to remove")
@app_commands.checks.has_permissions(manage_guild=True)
async def removebadword(interaction: discord.Interaction, word: str):
    g = get_guild(interaction.guild.id)
    if word.lower() in g["automod"]["badwords"]:
        g["automod"]["badwords"].remove(word.lower())
        save_data(db)
        await interaction.response.send_message(f"✅ Removed `{word}` from the filter.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ That word wasn't in the filter.", ephemeral=True)

# ═══════════════════════════════════════════════
#  SLASH COMMANDS — LOOKUPS
# ═══════════════════════════════════════════════

@bot.tree.command(name="youtubelatest", description="Get latest videos from a YouTube channel")
@app_commands.describe(channel_id="YouTube channel ID")
async def youtubelatest(interaction: discord.Interaction, channel_id: str):
    await interaction.response.defer()
    try:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    await interaction.followup.send("❌ Could not fetch feed. Check the channel ID.", ephemeral=True)
                    return
                text = await r.text()
        root = ET.fromstring(text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/"
        }
        entries = root.findall("atom:entry", ns)[:5]
        channel_title_el = root.find("atom:title", ns)
        channel_title = channel_title_el.text if channel_title_el is not None else channel_id
        embed = discord.Embed(title=f"📺 Latest from {channel_title}", color=discord.Color.red())
        for entry in entries:
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            published_el = entry.find("atom:published", ns)
            vid_id_el = entry.find("yt:videoId", ns)
            title = title_el.text if title_el is not None else "Unknown"
            link = link_el.get("href") if link_el is not None else "#"
            published = (published_el.text[:10] if published_el is not None else "")
            vid_id = vid_id_el.text if vid_id_el is not None else ""
            embed.add_field(name=f"🎬 {title}", value=f"📅 {published}\n[▶️ Watch]({link})", inline=False)
            if vid_id:
                embed.set_thumbnail(url=f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg")
        embed.set_footer(text="Nexora Bot • YouTube")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"[YouTubeLatest Error] {e}")
        await interaction.followup.send("❌ Something went wrong. Try again.", ephemeral=True)

@bot.tree.command(name="tiktoklatest", description="Get latest TikTok videos from a user")
@app_commands.describe(username="TikTok username (without @)")
async def tiktoklatest(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    username = username.lstrip("@")
    try:
        url = f"https://www.tiktok.com/@{username}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    await interaction.followup.send(f"❌ Could not find @{username}.", ephemeral=True)
                    return
                text = await r.text()
        embed = discord.Embed(
            title=f"📱 TikTok — @{username}",
            url=f"https://www.tiktok.com/@{username}",
            color=discord.Color.from_rgb(10, 10, 10)
        )
        videos = re.findall(r'"id":"(\d+)","desc":"([^"]{1,100})"[^}]*?"playCount":(\d+)', text)
        if videos:
            for vid_id, desc, plays in videos[:5]:
                vid_url = f"https://www.tiktok.com/@{username}/video/{vid_id}"
                embed.add_field(
                    name=f"🎵 {desc[:60]}",
                    value=f"▶️ {int(plays):,} plays\n[Watch]({vid_url})",
                    inline=False
                )
        else:
            embed.description = f"[View @{username}'s TikTok profile](https://www.tiktok.com/@{username})\n*TikTok limits automated access.*"
        embed.set_footer(text="Nexora Bot • TikTok")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"[TikTokLatest Error] {e}")
        await interaction.followup.send("❌ Something went wrong. Try again.", ephemeral=True)

# ─────────────────────────────────────────────
#  MISSING IMPORT FIX

# ─────────────────────────────────────────────
#  ANNOUNCE COMMAND (with optional anonymous mode)
# ─────────────────────────────────────────────
@bot.tree.command(name="announce", description="Send an announcement to a channel")
@app_commands.describe(
    channel="Channel to send the announcement to",
    message="The announcement message",
    title="Optional title for the announcement",
    anonymous="Send anonymously? (hides your name)",
    ping_role="Optional role to ping with the announcement"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    title: str = "📢 Announcement",
    anonymous: bool = False,
    ping_role: discord.Role = None
):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title=title, description=message, color=0x5865F2)
    embed.timestamp = discord.utils.utcnow()
    if anonymous:
        embed.set_author(name="Anonymous", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        embed.set_footer(text="Anonymous Announcement")
    else:
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
    ping_text = f"{ping_role.mention} " if ping_role else ""
    await channel.send(content=ping_text if ping_text else None, embed=embed)
    await interaction.followup.send(f"✅ Announcement sent to {channel.mention}!", ephemeral=True)

@announce.error
async def announce_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You need **Manage Messages** permission to use this.", ephemeral=True)

# ─────────────────────────────────────────────
#  RULES COMMAND
# ─────────────────────────────────────────────
@bot.tree.command(name="rules", description="Display the server rules")
async def rules(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=f"📋 {guild.name} Rules",
        description="Please read and follow all rules to keep this server a great place for everyone.",
        color=0x5865F2
    )
    rules_list = [
        ("1. Be Respectful", "Treat everyone with respect. No harassment, hate speech, or bullying."),
        ("2. No Spam", "Do not spam messages, emojis, or mentions."),
        ("3. No NSFW Content", "Keep all content appropriate for all ages unless in designated channels."),
        ("4. No Self-Promotion", "Do not advertise servers, social media, or products without permission."),
        ("5. Follow Discord TOS", "All Discord Terms of Service apply here. See discord.com/terms."),
        ("6. Listen to Staff", "Follow instructions from moderators and admins at all times."),
        ("7. Have Fun!", "Enjoy your time here and be a positive part of the community."),
    ]
    for name, value in rules_list:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Breaking rules may result in a warning, mute, kick, or ban.")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
import datetime

# ─────────────────────────────────────────────
#  RUN BOT
# ─────────────────────────────────────────────
if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not set!")
    exit(1)

bot.run(TOKEN, reconnect=True)
