import os
import random
import asyncio
import threading
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
from nonebot import on_command, on_message, get_driver
from nonebot.params import EventMessage, CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.rule import to_me
from anyio import to_thread
from PIL import Image
from psycopg2 import pool

db_pool = pool.ThreadedConnectionPool(
    1, 5, host="localhost", database="arcaea_assets",
    user="common_user", password="password"
)

BASE_DIR = os.path.abspath("shimiru-bot/plugins/arcaea/arcaea-assets")
COVERS_DIR = os.path.join(BASE_DIR, "covers")
DAYU_DIR = os.path.join(BASE_DIR, "dayu")
HTTP_PORT = 18766

# 全群游戏状态，key 为 group_id
game_states: dict[int, dict] = {}


def random_crop_quarter(input_path: str, output_path: str):
    """裁剪原图的 1/4 大小区域，随机位置"""
    img = Image.open(input_path)
    width, height = img.size
    crop_w = width // 2
    crop_h = height // 2
    x = random.randint(0, width - crop_w)
    y = random.randint(0, height - crop_h)
    cropped = img.crop((x, y, x + crop_w, y + crop_h))
    cropped.save(output_path, "JPEG")


def start_image_server():
    handler = partial(SimpleHTTPRequestHandler, directory=BASE_DIR)
    server = HTTPServer(("127.0.0.1", HTTP_PORT), handler)
    print(f"[图片服务] 已启动: http://127.0.0.1:{HTTP_PORT}")
    server.serve_forever()


driver = get_driver()


@driver.on_startup
async def on_startup():
    t = threading.Thread(target=start_image_server, daemon=True)
    t.start()


def get_song_payload_sync(song_id: str = None):
    """获取歌曲数据，song_id 为 None 时随机取一首"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            if song_id is None:
                cur.execute("SELECT count(*) FROM m_song")
                total = cur.fetchone()[0]
                if total == 0:
                    return None
                offset = random.randint(0, total - 1)
                cur.execute("SELECT id FROM m_song LIMIT 1 OFFSET %s", (offset,))
                song_id = cur.fetchone()[0]

            # title 只需取一条（同一 id 下 title 应相同）
            cur.execute("SELECT title FROM m_alias WHERE id = %s LIMIT 1", (song_id,))
            row = cur.fetchone()
            title = row[0] if row else song_id  # fallback 到 id

            cur.execute("SELECT alias FROM m_alias WHERE id = %s", (song_id,))
            aliases = [r[0] for r in cur.fetchall()]

            img_filename = f"Songs_{song_id}.jpg"
            img_path = os.path.join(COVERS_DIR, img_filename)

            return {
                "id": song_id,
                "title": title,
                "aliases": aliases,
                "img_url": f"https://covers.shimiru233.dpdns.org/{img_filename}" if os.path.exists(img_path) else None,
                "img_path": img_path if os.path.exists(img_path) else None,
            }
    finally:
        db_pool.putconn(conn)


def search_songs_sync(keyword: str) -> dict | None:
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            sql = """
	        SELECT id, title,
                       GREATEST(
                           similarity(id, %s),
                           similarity(title, %s),
                           similarity(alias, %s)
                       ) AS sim
                FROM m_alias
                WHERE
                    id %% %s
                    OR title ILIKE %s
                    OR alias ILIKE %s
                    OR alias %% %s
                ORDER BY sim DESC
                LIMIT 1
                """

            cur.execute(sql, (
                keyword,          # similarity(id)
                keyword,          # similarity(title)
                keyword,          # similarity(alias)
                keyword,          # id %%
                f"%{keyword}%",   # title ILIKE
                f"%{keyword}%",   # alias ILIKE
                keyword           # alias %%
            ))
            row = cur.fetchone()
            if not row:
                return None
            sid = row[0]

            cur.execute("SELECT title FROM m_alias WHERE id = %s LIMIT 1", (sid,))
            title_row = cur.fetchone()
            title = title_row[0] if title_row else sid

            cur.execute("SELECT alias FROM m_alias WHERE id = %s", (sid,))
            aliases = [r[0] for r in cur.fetchall()]

        return {"id": sid, "title": title, "aliases": aliases}
    finally:
        db_pool.putconn(conn)


# ── /ra 随机展示一首谱面 ──────────────────────────────
randomChartMatcher = on_command("ra", aliases={"guesschart"})


@randomChartMatcher.handle()
async def get_random_chart(bot: Bot, event: Event):
    data = await to_thread.run_sync(get_song_payload_sync)
    if not data:
        await bot.send(event, "曲库为空")
        return

    alias_text = ", ".join(data["aliases"]) if data["aliases"] else "无"
    text_msg = f"歌曲: {data['title']} ({data['id']})\n别名: {alias_text}"

    if data["img_url"]:
        try:
            await bot.send(event, MessageSegment.image(data["img_url"]))
        except ActionFailed:
            pass
    await bot.send(event, text_msg)


# ── /gs 开始猜谱面游戏 ───────────────────────────────
guessSongMatcher = on_command("gs")


@guessSongMatcher.handle()
async def start_guess_song(bot: Bot, event: Event):
    group_id = getattr(event, "group_id", None)
    if not group_id:
        await bot.send(event, "请在群聊中使用")
        return

    if group_id in game_states:
        await bot.send(event, "当前已有进行中的游戏，请等待结束")
        return

    data = await to_thread.run_sync(get_song_payload_sync)
    if not data:
        await bot.send(event, "曲库为空")
        return

    # 生成截图临时文件
    crop_path = None
    crop_url = None
    if data["img_path"]:
        crop_filename = f"_crop_{uuid.uuid4().hex}.jpg"
        crop_path = os.path.join(COVERS_DIR, crop_filename)
        await to_thread.run_sync(lambda: random_crop_quarter(data["img_path"], crop_path))
        crop_url = f"http://127.0.0.1:{HTTP_PORT}/{crop_filename}"

    game_states[group_id] = {
        "id": data["id"],
        "title": data["title"],
        "aliases": data["aliases"],
        "img_url": data["img_url"],
        "crop_path": crop_path,
    }

    # 发截图而不是完整图
    if crop_url:
        try:
            await bot.send(event, MessageSegment.image(crop_url))
        except ActionFailed:
            pass
    await bot.send(event, "请在 60 秒内猜出这首歌的名称！")

    # 60 秒后超时处理
    await asyncio.sleep(60)

    if group_id in game_states:
        state = game_states.pop(group_id)
        # 清理临时截图
        if state.get("crop_path") and os.path.exists(state["crop_path"]):
            os.remove(state["crop_path"])
        alias_text = ", ".join(state["aliases"]) if state["aliases"] else "无"
        # 超时后发完整图
        if state.get("img_url"):
            try:
                await bot.send(event, MessageSegment.image(state["img_url"]))
            except ActionFailed:
                pass
        await bot.send(event, f"时间到！答案是：{state['title']} ({state['id']})\n别名: {alias_text}")


# ── /s 模糊查询歌曲 ──────────────────────────────────
searchMatcher = on_command("s")


@searchMatcher.handle()
async def search_song(bot: Bot, event: Event, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    if not keyword:
        await bot.send(event, "请输入歌曲名称，例如：/s lenfent")
        return

    song = await to_thread.run_sync(search_songs_sync, keyword)
    if not song:
        await bot.send(event, "没有找到相关歌曲")
        return

    data = await to_thread.run_sync(get_song_payload_sync, song["id"])
    if not data:
        await bot.send(event, "没有找到相关歌曲")
        return

    alias_text = ", ".join(data["aliases"]) if data["aliases"] else "无"
    text_msg = f"歌曲: {data['title']} ({data['id']})\n别名: {alias_text}"

    if data["img_url"]:
        try:
            await bot.send(event, MessageSegment.image(data["img_url"]))
        except ActionFailed:
            pass
    await bot.send(event, text_msg)


# ── 猜歌回答监听 ─────────────────────────────────────
to_meMatcher = on_message(rule=to_me(), priority=10)


@to_meMatcher.handle()
async def handle_to_me(bot: Bot, event: Event, msg: Message = EventMessage()):
    group_id = getattr(event, "group_id", None)
    plain_text = msg.extract_plain_text().strip()

    if plain_text.startswith("/"):
        return

    # 如果该群有进行中的游戏，优先处理猜歌
    if group_id and group_id in game_states:
        state = game_states[group_id]
        correct_answers = [state["id"]] + state["aliases"]

        matched = False
        for ans in correct_answers:
            if ans:
                if await to_thread.run_sync(lambda kw=plain_text, a=ans: trigram_similarity(kw, a) > 0.4):
                    matched = True
                    break

        if matched:
            state = game_states.pop(group_id)
            # 清理临时截图
            if state.get("crop_path") and os.path.exists(state["crop_path"]):
                os.remove(state["crop_path"])
            # 猜对后发完整图
            if state.get("img_url"):
                try:
                    await bot.send(event, MessageSegment.image(state["img_url"]))
                except ActionFailed:
                    pass
            alias_text = ", ".join(state["aliases"]) if state["aliases"] else "无"
            await bot.send(event, f"回答正确！答案就是：{state['title']} ({state['id']})\n别名: {alias_text}")
        else:
            await bot.send(event, "不对哦，继续猜！")
            return

    if plain_text == "help":
        await bot.send(event, "图片和别名摘自Arcaea中文维基，/gs 开始猜曲，/s XXX 搜索歌曲，/ra 随机展示")


def trigram_similarity(keyword: str, answer: str) -> float:
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT similarity(%s, %s)", (keyword, answer))
            return cur.fetchone()[0]
    finally:
        db_pool.putconn(conn)
