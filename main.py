import discord
from discord.ext import commands, tasks
import datetime
import json
import asyncio
import os

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

voice_sessions = {}
voice_durations = {}

def save_voice_durations():
    with open("voice_durations.json", "w", encoding="utf-8") as f:
        json.dump(voice_durations, f, ensure_ascii=False, indent=4)

def load_voice_durations():
    global voice_durations
    try:
        with open("voice_durations.json", "r", encoding="utf-8") as f:
            voice_durations = json.load(f)
    except FileNotFoundError:
        voice_durations = {}

def get_today():
    return datetime.datetime.now().date()

def get_week_start():
    today = get_today()
    return today - datetime.timedelta(days=today.weekday())

def get_month_start():
    now = datetime.datetime.now()
    return datetime.date(now.year, now.month, 1)

def get_year_start():
    now = datetime.datetime.now()
    return datetime.date(now.year, 1, 1)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as: {bot.user} (ID: {bot.user.id})")
    print(f"✅ Connected to {len(bot.guilds)} guild(s).")
    load_voice_durations()
    if not monthly_ranking_loop.is_running():
        monthly_ranking_loop.start()
    if not yearly_ranking_loop.is_running():
        yearly_ranking_loop.start()

@bot.event
async def on_voice_state_update(member, before, after):
    user_id = str(member.id)
    now = datetime.datetime.now()

    if before.channel is None and after.channel is not None:
        voice_sessions[user_id] = now
    elif before.channel is not None and after.channel is None:
        start_time = voice_sessions.pop(user_id, None)
        if start_time:
            duration = (now - start_time).total_seconds()
            update_voice_duration(user_id, duration)

def update_voice_duration(user_id, duration):
    if user_id not in voice_durations:
        voice_durations[user_id] = {"total": 0, "本日": 0, "week": 0, "month": 0, "year": 0}
    voice_durations[user_id]["total"] += duration
    voice_durations[user_id]["本日"] += duration
    voice_durations[user_id]["week"] += duration
    voice_durations[user_id]["month"] += duration
    voice_durations[user_id]["year"] += duration
    save_voice_durations()

async def send_time_report(ctx, key, label):
    lines = []
    for user_id, durations in voice_durations.items():
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"ID: {user_id}"
        seconds = durations.get(key, 0)
        minutes = int(seconds // 60)
        lines.append(f"{name}: {minutes}分")
    if lines:
        await ctx.send(f"**{label} 通話時間:**\n" + "\n".join(lines))
    else:
        await ctx.send("データがありません。")

@bot.command()
async def calltime(ctx):
    await send_time_report(ctx, "total", "累積")

@bot.command()
async def calltime_today(ctx):
    await send_time_report(ctx, "本日", "本日")

@bot.command()
async def calltime_week(ctx):
    await send_time_report(ctx, "week", "週間")

@bot.command()
async def calltime_month(ctx):
    await send_time_report(ctx, "month", "月間")

@bot.command()
async def calltime_year(ctx):
    await send_time_report(ctx, "year", "年間")

@tasks.loop(hours=1)
async def monthly_ranking_loop():
    now = datetime.datetime.now()
    if now.day == 1 and now.hour == 0:
        await post_ranking("month", "月間通話時間ランキング")
        for durations in voice_durations.values():
            durations["month"] = 0
        save_voice_durations()

@tasks.loop(hours=6)
async def yearly_ranking_loop():
    now = datetime.datetime.now()
    if now.month == 1 and now.day == 1 and now.hour == 0:
        await post_ranking("year", "年間通話時間ランキング")
        for durations in voice_durations.values():
            durations["year"] = 0
        save_voice_durations()

async def post_ranking(key, title):
    ranking = sorted(voice_durations.items(), key=lambda x: x[1].get(key, 0), reverse=True)
    if not ranking:
        return
    report_lines = [f"📊 **{title}** 📊"]
    for i, (user_id, durations) in enumerate(ranking, start=1):
        member = None
        for guild in bot.guilds:
            member = guild.get_member(int(user_id))
            if member:
                break
        name = member.display_name if member else f"ID: {user_id}"
        minutes = int(durations.get(key, 0) // 60)
        report_lines.append(f"{i}. {name} - {minutes}分")
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send("\n".join(report_lines))
                break
            except:
                continue

@bot.command(name="test_monthly_ranking")
async def test_monthly_ranking(ctx):
    await post_ranking("month", "月間通話時間ランキング")

@bot.command(name="test_yearly_ranking")
async def test_yearly_ranking(ctx):
    await post_ranking("year", "年間通話時間ランキング")

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"⚠ エラー: {str(error)}")
    print(f"エラー: {str(error)}")

# 環境変数からトークンを取得して起動
bot.run(os.getenv("DISCORD_TOKEN"))
