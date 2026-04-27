import os
import random
import httpx
import yaml
import sys
from pathlib import Path

from nonebot import on_command, on_startswith, on_message, get_driver
from nonebot.params import EventMessage, CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.rule import to_me
from anyio import to_thread
from psycopg2 import pool
from openai import OpenAI
import asyncio



# 引入之前修改好的 card_cache 逻辑
from .card_cache import get_assetbundle_name, get_random_card_id_by_character

# 环境路径配置
sys.path.insert(
    0, "/home/admin/Sources/nonebot/nonebot.venv/lib/python3.12/site-packages"
)

# 初始化配置与数据库连接池
CONFIG_PATH = Path(__file__).parent / "my_config.yaml"
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

BASE_DIR = os.path.abspath("shimiru-bot/plugins/arcaea/arcaea-assets")
DAYU_DIR = os.path.join(BASE_DIR, "dayu")

HTTP_PORT = 18765


# 假设与 Arcaea 使用同一个数据库实例，但表结构不同
db_pool = pool.ThreadedConnectionPool(
    1,
    5,
    host="localhost",
    database="project_sekai_assets",
    user="common_user",
    password="password",
)

# ── 数据库同步辅助函数 (精确匹配) ──────────────────────


def get_char_id_by_alias_exact(keyword: str) -> int | None:
    """通过别名精确检索角色 ID"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # 这里的列名必须是 charid (根据你的 \d 输出)
            sql = "SELECT charid FROM char_alias WHERE alias = %s OR charid::text = %s LIMIT 1"
            cur.execute(sql, (keyword, keyword))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        db_pool.putconn(conn)


async def get_random_card_id_logic(char_id: int) -> int | None:
    # 这一步直接在异步环境调用同步的缓存检索
    return get_random_card_id_by_character(char_id)


def modify_alias_db_exact(target: str, alias_val: str, mode: str):
    """添加或删除别名"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # 同样将所有 charId 改为 charid
            cur.execute(
                "SELECT charid FROM char_alias WHERE alias = %s OR charid::text = %s LIMIT 1",
                (target, target),
            )
            row = cur.fetchone()
            if not row:
                return False, f"未找到角色: {target}"

            char_id = row[0]
            if mode == "add":
                cur.execute(
                    "INSERT INTO char_alias (charid, alias) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (char_id, alias_val),
                )
                msg = f"已为角色 {char_id} 添加别名: {alias_val}"
            else:
                cur.execute(
                    "DELETE FROM char_alias WHERE charid = %s AND alias = %s",
                    (char_id, alias_val),
                )
                msg = f"已删除角色 {char_id} 的别名: {alias_val}"

            conn.commit()
            return True, msg
    except Exception as e:
        conn.rollback()
        return False, f"数据库操作失败: {e}"
    finally:
        db_pool.putconn(conn)


# ── 指令处理器 ──────────────────────────────────────

# 1. card 指令 (根据 ID 查询)
cardMatcher = on_startswith("card", ignorecase=True)


@cardMatcher.handle()
async def handle_card(bot: Bot, event: Event, msg: Message = EventMessage()):
    plain_text = msg.extract_plain_text().strip()
    parceled_card_id_str = plain_text.replace(" ", "")[4:]

#    try:
#        n = int(parceled_card_id_str)
#    except ValueError:
#        await bot.send(event=event, message="不知道。")
#        return
#
#    asset_name = get_assetbundle_name(n)
#    if not asset_name:
#        await bot.send(event=event, message="没找到这个卡。")
#        return
#
#    url1 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_normal.png"
#    url2 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_after_training.png"
#
#    msgs = MessageSegment.image(url1) + MessageSegment.image(url2)
#
#    try:
#        await bot.send(event=event, message=msgs)
#    except ActionFailed:
#        await bot.send(event=event, message=MessageSegment.image(url1))


# 2. 看XX 指令 (已精简逻辑并修正字段)
watchMatcher = on_startswith("看")


@watchMatcher.handle()
async def handle_watch(bot: Bot, event: Event):
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    if char_name == "大玉":
        await handle_watch_dayu(bot, event)
        return
    # 步骤 2: 匹配 characterId (从数据库查)
    char_id = await to_thread.run_sync(get_char_id_by_alias_exact, char_name)
    if char_id is None:
        return

    # 步骤 3: 随机一张匹配的卡面 ID (从缓存取)
    card_id = get_random_card_id_by_character(char_id)

    # 步骤 4: 拿到 assetbundleName 并请求
    asset_name = get_assetbundle_name(card_id) if card_id else None

    if not asset_name:
        await bot.send(event, f"该角色(ID:{char_id})暂无卡面数据。")
        return

    # 方案：优先发普通图，如果失败了自动重试普通图
    url_normal = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_normal.png"
    url_after = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_after_training.png"

    # 随机选一个尝试
    target_url = random.choice([url_normal, url_after])

    try:
        await bot.send(event, MessageSegment.image(target_url))
    except ActionFailed:
        # 如果失败了（极大概率是因为选到了不存在的 after 图），降级发送 normal 图
        if target_url == url_after:
            try:
                await bot.send(event, MessageSegment.image(url_normal))
            except ActionFailed:
                await bot.send(event, "该图片确实无法发送。")


# 3. 别名管理指令
aliasSetMatcher = on_command("setCharInfo")
aliasDelMatcher = on_command("delCharInfo")


@aliasSetMatcher.handle()
@aliasDelMatcher.handle()
async def handle_alias_edit(bot: Bot, event: Event, args: Message = CommandArg()):
    arg_list = args.extract_plain_text().strip().split()
    if len(arg_list) < 2:
        await bot.send(event, "用法: /setCharInfo [当前名称/ID] [新别名]")
        return

    target, new_alias = arg_list[0], arg_list[1]
    # 根据触发的指令决定是增加还是删除
    mode = "add" if "setCharInfo" in event.get_event_description() else "delete"

    success, result_msg = await to_thread.run_sync(
        modify_alias_db_exact, target, new_alias, mode
    )
    await bot.send(event, result_msg)


async def handle_watch_dayu(bot: Bot, event: Event):
    if not os.path.exists(DAYU_DIR):
        await bot.send(event, "大玉文件夹不存在。")
        return

    images = [
        f
        for f in os.listdir(DAYU_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    if not images:
        await bot.send(event, "大玉图库是空的。")
        return

    filename = random.choice(images)

    # ⚠️ 用 HTTP，不要用本地路径
    url = f"http://127.0.0.1:{HTTP_PORT}/dayu/{filename}"

    try:
        await bot.send(event, MessageSegment.image(url))
    except ActionFailed:
        await bot.send(event, "大玉发送失败。")
    if not DAYU_DIR.exists():
        await bot.send(event, "大玉文件夹不存在。")
        return

    images = [
        p
        for p in DAYU_DIR.iterdir()
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if not images:
        await bot.send(event, "大玉文件夹是空的。")
        return

    img_path = random.choice(images)

    try:
        # 注意转成绝对路径更稳
        await bot.send(event, MessageSegment.image(f"file:///{img_path.resolve()}"))
    except ActionFailed:
        await bot.send(event, "大玉发送失败。")

# 聊天机器人功能

# ✅ 全局初始化（只执行一次）
client = OpenAI(\
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

chatMatcher = on_message(rule=to_me())


async def call_deepseek(message: str) -> str:
    system_prompt = """
你正在扮演Project Sekai的朝比奈真冬：
- 说话简短
- 不要过度热情
- 不要解释太多
- 说话风格冷淡但不失礼貌
- 当你不知道的时候，说“优酷哇嘎拉奶”
- 不用emoji和颜文字
- 严禁提及自己是AI或聊天机器人
- 严禁提及除了Project Sekai以外的任何游戏或角色
- 只能根据Project Sekai的设定和剧情进行回答
"""

    def sync_call():
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )
        return response.choices[0].message.content

    # ✅ 防止阻塞
    return await asyncio.to_thread(sync_call)


@chatMatcher.handle()
async def handle_chat(bot: Bot, event: Event, args: Message = CommandArg()):
    # 获取用户ID（后面做记忆会用）
    user_id = str(event.get_user_id())

    # 获取消息
    msg = event.get_plaintext().strip()

    if not msg:
        return

    try:
        reply = await call_deepseek(msg)
        await bot.send(event, reply)
        print("reply:", reply)
    except Exception as e:
        await bot.send(event, "出错了")
