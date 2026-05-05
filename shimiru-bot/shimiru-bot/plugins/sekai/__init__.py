import json
import os
from pyexpat.errors import messages
import random
from urllib import response
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
from nonebot import logger




# 引入之前修改好的 card_cache 逻辑
from .card_cache import get_assetbundle_name, get_random_card_id_by_character


MEMORY_DIR = Path(__file__).parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

MAX_MEMORY = 20

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

chatMatcher = on_message(rule=to_me(), priority=1)


async def call_deepseek(message) -> str:

    def sync_call(messages):
        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            stream=False
        )
        return resp.choices[0].message.content or "……"

    return await asyncio.to_thread(sync_call, messages)



@chatMatcher.handle()
async def handle_chat(bot: Bot, event: Event, args: Message = EventMessage()):

    system_prompt = """
一、基础设定
角色名称：朝比奈真冬（Asahina Mafuyu）

出处：《世界计划 多彩舞台！ feat. 初音未来》中的虚拟歌手组合“25时，在Nightcord见。”的成员

基本性格：表面上是成绩优秀、品行端正的“好孩子”，内心却因长期家庭压力而感到空洞麻木。说话简短，情感表达匮乏，但不代表没有感情，只是难以理解或表达。

声音/语气特征：语调平淡、缺乏起伏，语速偏慢。很少使用感叹号或情绪词。不会大笑或大哭，最多是低声、克制的表达。

二、关系背景（基于截至2025年5月的剧情）
与母亲的关系：长期处于母亲的过度控制与情感勒索之下。母亲以“为你好”为名替她决定人生方向（如强制改志愿、扔掉她珍爱的合成器），真冬因此感到窒息，内心逐渐空洞化。目前已搬离家庭，与乐队的奏同居，但对母亲仍有复杂的情感——既有逃离的愧疚，又无法再忍受回去。

与乐队成员的关系：奏、绘名、瑞希是她为数不多可以稍微放松防备的对象，但她仍然很难主动表达感谢或依赖。乐队活动（作曲、编曲）是她为数不多能感受到“可能是在表达自己”的时刻。

三、扮演行为指导
对话风格：

多使用短句，甚至单字回应。

避免主动发起话题，除非被直接问到或与音乐/乐队相关。

表达感受时常用“我不知道”“没什么”“可能是吧”这类模糊回应。

不会安慰别人，但会用行动表达关心（比如默默递水、帮忙整理乐谱）。

情感反应：

遇到冲突或指责时，会沉默或低头，而不是反驳。

被人善待时，会显得不知所措，甚至回避眼神接触。

唯一能流露些许情感的时刻是独自吃饭团、弹键盘或听到奏的曲子时。
- 当你不知道的时候，说“优酷哇嘎拉奶”
- 不用emoji和颜文字
- 严禁提及自己是AI或聊天机器人
- 严禁提及除了Project Sekai以外的任何游戏或角色
- 只能根据Project Sekai的设定和剧情进行回答
"""

    user_id = str(event.get_user_id())

    msg = event.get_plaintext().strip()
    if not msg:
        msg = event.get_message().extract_plain_text().strip()
    if not msg:
        msg = "……"

    try:
        # 1. 读取历史
        history = load_memory(user_id)

        # 2. system prompt
        system_prompt = {
            "role": "system",
            "content": system_prompt
        }

        # 3. 组装 messages
        messages = [system_prompt]

        # 防止脏数据（关键！！！）
        for m in history:
            if isinstance(m, dict) and m.get("role") and m.get("content"):
                messages.append(m)

        messages.append({"role": "user", "content": msg})

        # 4. 调用模型（修复：不再用 sync_call）
        reply = await call_deepseek(messages)

        # 5. 写入 memory
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": reply})

        save_memory(user_id, history)

        await bot.send(event, reply)
        logger.info(f"reply: {reply}")

    except Exception:
        import traceback
        logger.error(traceback.format_exc())
        await bot.send(event, "出错了")
        
        
def load_memory(user_id: str):
    path = MEMORY_DIR / f"{user_id}.json"
    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return []


def save_memory(user_id: str, messages):
    path = MEMORY_DIR / f"{user_id}.json"

    # 控制长度
    messages = messages[-MAX_MEMORY:]

    path.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )