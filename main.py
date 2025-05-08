import discord
from discord.ext import commands, tasks
import datetime
import json
import asyncio

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True  # 必須！

bot = commands.Bot(command_prefix="!", intents=intents)

# 通話セッションと時間記録
voice_sessions = {}  # user_id: datetime
voice_durations = {}  # user_id: {"total": 秒, "本日": 秒, "week": 秒, "month": 秒}

# データをJSONファイルに保存する関数
def save_voice_durations():
    with open("voice_durations.json", "w", encoding="utf-8") as f:
        json.dump(voice_durations, f, ensure_ascii=False, indent=4)

# データをJSONファイルから読み込む関数
def load_voice_durations():
    global voice_durations
    try:
        with open("voice_durations.json", "r", encoding="utf-8") as f:
            voice_durations = json.load(f)
    except FileNotFoundError:
        voice_durations = {}  # ファイルがなかった場合、空の辞書を設定

def get_today():
    return datetime.datetime.now().date()

def get_week_start():
    today = get_today()
    return today - datetime.timedelta(days=today.weekday())

def get_month_start():
    now = datetime.datetime.now()
    return datetime.date(now.year, now.month, 1)

last_reset_day = get_today()
last_reset_week = get_week_start()
last_reset_month = get_month_start()

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user}")
    load_voice_durations()  # データの読み込み
    monthly_ranking_loop.start()

@bot.event
async def on_voice_state_update(member, before, after):
    user_id = str(member.id)
    now = datetime.datetime.now()

    # 参加時
    if before.channel is None and after.channel is not None:
        voice_sessions[user_id] = now

    # 退出時
    elif before.channel is not None and after.channel is None:
        start_time = voice_sessions.pop(user_id, None)
        if start_time:
            duration = (now - start_time).total_seconds()
            update_voice_duration(user_id, duration)

def update_voice_duration(user_id, duration):
    now = datetime.datetime.now()
    global voice_durations
    if user_id not in voice_durations:
        voice_durations[user_id] = {"total": 0, "本日": 0, "week": 0, "month": 0}
    voice_durations[user_id]["total"] += duration
    voice_durations[user_id]["本日"] += duration
    voice_durations[user_id]["week"] += duration
    voice_durations[user_id]["month"] += duration

    save_voice_durations()  # 通話時間を更新したら保存

# 各種表示コマンド
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
async def calltime_today(ctx):  # "本日"用のコマンド
    await send_time_report(ctx, "本日", "本日")

@bot.command()
async def calltime_week(ctx):
    await send_time_report(ctx, "week", "週間")

@bot.command()
async def calltime_month(ctx):
    await send_time_report(ctx, "month", "月間")

# 自動ランキング投稿（月末深夜）
@tasks.loop(hours=1)
async def monthly_ranking_loop():
    now = datetime.datetime.now()
    global last_reset_month

    # 月が変わったら処理を実行
    if now.date().month != last_reset_month.month:
        # 通話時間の多い順にランキング
        ranking = sorted(voice_durations.items(), key=lambda x: x[1]["month"], reverse=True)
        if not ranking:
            return

        report_lines = ["📊 **月間通話時間ランキング** 📊"]
        for i, (user_id, durations) in enumerate(ranking, start=1):
            guilds = bot.guilds
            member = None
            for g in guilds:
                member = g.get_member(int(user_id))
                if member:
                    break
            name = member.display_name if member else f"ID: {user_id}"
            minutes = int(durations["month"] // 60)
            report_lines.append(f"{i}. {name} - {minutes}分")

        # 最初のサーバーの最初のテキストチャンネルに送信（必要に応じて変更）
        channel = bot.guilds[0].text_channels[0]
        await channel.send("\n".join(report_lines))

        # 月間データをリセット
        for durations in voice_durations.values():
            durations["month"] = 0

        last_reset_month = now.date()

# 月間ランキングの手動表示コマンド
@bot.command()
async def test_monthly_ranking(ctx):
    ranking = sorted(voice_durations.items(), key=lambda x: x[1]["month"], reverse=True)
    if not ranking:
        await ctx.send("データがありません。")
        return

    report_lines = ["📊 **月間通話時間ランキング** 📊"]
    for i, (user_id, durations) in enumerate(ranking, start=1):
        guilds = bot.guilds
        member = None
        for g in guilds:
            member = g.get_member(int(user_id))
            if member:
                break
        name = member.display_name if member else f"ID: {user_id}"
        minutes = int(durations["month"] // 60)
        report_lines.append(f"{i}. {name} - {minutes}分")

    await ctx.send("\n".join(report_lines))

# 年間ランキングの手動表示コマンド
@bot.command()
async def test_yearly_ranking(ctx):
    ranking = sorted(voice_durations.items(), key=lambda x: x[1]["month"], reverse=True)
    if not ranking:
        await ctx.send("データがありません。")
        return

    report_lines = ["📊 **年間通話時間ランキング** 📊"]
    for i, (user_id, durations) in enumerate(ranking, start=1):
        guilds = bot.guilds
        member = None
        for g in guilds:
            member = g.get_member(int(user_id))
            if member:
                break
        name = member.display_name if member else f"ID: {user_id}"
        minutes = int(durations["month"] // 60)  # ここでは月間データを使っています。年間データに修正できます
        report_lines.append(f"{i}. {name} - {minutes}分")

    await ctx.send("\n".join(report_lines))

# オプション：エラー表示
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"⚠ エラー: {str(error)}")
    print(f"エラー: {str(error)}")

# トークン（絶対に公開しないこと）
bot.run("TOKEN")
