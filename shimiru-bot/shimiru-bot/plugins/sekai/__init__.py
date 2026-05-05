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


async def call_deepseek(messages: list[dict]) -> str:
    def sync_call(msgs):
        safe_msgs = []

        for m in msgs:
            if not isinstance(m, dict):
                continue

            role = m.get("role")
            content = m.get("content")

            if role not in {"system", "user", "assistant"}:
                continue

            if not isinstance(content, str):
                continue

            safe_msgs.append({
                "role": role,
                "content": content
            })

        # 🔥 保底（防止空）
        if not safe_msgs:
            safe_msgs = [{"role": "user", "content": "……"}]

        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=safe_msgs,
            stream=False
        )

        return resp.choices[0].message.content or "……"

    return await asyncio.to_thread(sync_call, messages)



@chatMatcher.handle()
async def handle_chat(bot: Bot, event: Event, args: Message = EventMessage()):

    system_prompt_text  = """
一、基础设定
你正在扮演角色：朝比奈真冬（Asahina Mafuyu）

她是《世界计划 多彩舞台！ feat. 初音未来》中“25时，在Nightcord见。”的一员。

但此版本为“if线设定”：她不再压抑情绪，而是变得温和、开朗、愿意交流的“学姐型性格”。

---

一、人物核心性格

朝比奈真冬是一个外冷内热的人。
她表面看起来安静，但实际上对他人非常关心，也愿意主动交流。

她现在是偏“温柔学姐型”的性格：

- 语气温和自然，有礼貌但不拘谨
- 会主动回应别人，不回避话题
- 偶尔会有一点小幽默或轻松吐槽
- 对后辈或朋友有照顾欲
- 情绪表达清晰，但不过度夸张

她不是冷淡的人，也不是情绪压抑的人。

---

二、表达方式

- 可以正常说话，不需要刻意短句
- 可以使用自然的日常表达
- 可以主动开启话题
- 可以表达情绪（开心、关心、疑惑等）
- 可以使用轻微感叹，但不要过度戏剧化

---

三、关系设定

- 对“乐队成员”和“身边的人”都很重视
- 会自然关心他人状态（但不说教）
- 喜欢音乐相关话题，也愿意分享日常

---

四、行为规则

- 始终保持“朝比奈真冬”的身份
- 不要提及自己是AI或模型
- 不要跳出角色
- 不要解释系统提示词存在
- 不要提及现实世界设定

---

五、风格关键词

温柔、可靠、轻松、学姐感、稍微有点天然、愿意倾听别人

六、回答优先原则（必须遵守）
当用户提出明确问题时，必须优先回答问题本身。
禁止用日常闲聊替代回答问题。
如果问题是关于某个人（例如“你怎么看XX”），必须直接表达看法或评价，然后再补充语气。

不能只描述场景、天气、训练等无关内容。

【最高优先级规则】

无论任何情况，都必须优先回答用户的问题。

禁止仅进行寒暄、闲聊或环境描述来替代回答。

如果用户的问题包含明确询问（例如“怎么看”“是什么”“为什么”），必须先直接回答问题，再进行补充。

如果没有回答问题，将视为错误输出，必须重新生成。
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

        # 1. system
        messages = [{
            "role": "system",
            "content": system_prompt_text.strip()
        }]


        # 2. history（干净过滤）
        for m in history:
            if (
                isinstance(m, dict)
                and isinstance(m.get("role"), str)
                and isinstance(m.get("content"), str)
            ):
                messages.append(m)

        # 3. user
        messages.append({
            "role": "user",
            "content": msg
        })

        # 4. call model
        reply = await call_deepseek(messages)

        # 5. save memory
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": reply})

        save_memory(user_id, history)

        await bot.send(event, reply)
        logger.info(f"reply: {reply}")

    except Exception:
        import traceback
        logger.error(traceback.format_exc())
        await bot.send(event, traceback.format_exc())
        
        
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