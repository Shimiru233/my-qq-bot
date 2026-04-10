import os
import random
import yaml
import sys
from pathlib import Path

from nonebot import on_command, on_startswith, get_driver
from nonebot.params import EventMessage, CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.rule import to_me
from anyio import to_thread
from psycopg2 import pool

# 引入之前修改好的 card_cache 逻辑
from .card_cache import get_assetbundle_name, get_random_card_id_by_character
# 环境路径配置
sys.path.insert(0, "/home/admin/Sources/nonebot/nonebot.venv/lib/python3.12/site-packages")

# 初始化配置与数据库连接池
CONFIG_PATH = Path(__file__).parent / "my_config.yaml"
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

# 假设与 Arcaea 使用同一个数据库实例，但表结构不同
db_pool = pool.ThreadedConnectionPool(
    1, 5, host="localhost", database="project_sekai_assets",
    user="common_user", password="password"
)

# ── 数据库同步辅助函数 (精确匹配) ──────────────────────

def get_char_id_by_alias_exact(keyword: str) -> int | None:
    """通过别名精确检索角色 ID"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # 只做完全一致的查询
            sql = "SELECT charId FROM char_alias WHERE alias = %s OR charId::text = %s LIMIT 1"
            cur.execute(sql, (keyword, keyword))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        db_pool.putconn(conn)

async def get_random_card_id_logic(char_id: int) -> int | None:
    # 这一步直接在异步环境调用同步的缓存检索
    return get_random_card_id_by_character(char_id)

def modify_alias_db_exact(target: str, alias_val: str, mode: str):
    """精确匹配后添加或删除别名"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # 先找 ID
            cur.execute("SELECT charId FROM char_alias WHERE alias = %s OR charId::text = %s LIMIT 1", (target, target))
            row = cur.fetchone()
            if not row:
                return False, f"未找到角色: {target}"
            
            char_id = row[0]
            if mode == "add":
                cur.execute("INSERT INTO char_alias (charId, alias) VALUES (%s, %s) ON CONFLICT DO NOTHING", (char_id, alias_val))
                msg = f"已为角色 {char_id} 添加别名: {alias_val}"
            else:
                cur.execute("DELETE FROM char_alias WHERE charId = %s AND alias = %s", (char_id, alias_val))
                msg = f"已删除角色 {char_id} 的别名: {alias_val}"
            
            conn.commit()
            return True, msg
    except Exception as e:
        conn.rollback()
        return False, f"数据库操作失败: {e}"
    finally:
        db_pool.putconn(conn)

# ── 指令处理器 ──────────────────────────────────────

# 1. kard 指令 (根据 ID 查询)
kardMatcher = on_startswith("kard", ignorecase=True)

@kardMatcher.handle()
async def handle_card(bot: Bot, event: Event, msg: Message = EventMessage()):
    plain_text = msg.extract_plain_text().strip()
    parceled_card_id_str = plain_text.replace(" ", "")[4:]

    try:
        n = int(parceled_card_id_str)
    except ValueError:
        await bot.send(event=event, message="不知道。")
        return

    asset_name = get_assetbundle_name(n)
    if not asset_name:
        await bot.send(event=event, message="没找到这个卡。")
        return

    url1 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_normal.png"
    url2 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_after_training.png"

    msgs = MessageSegment.image(url1) + MessageSegment.image(url2)

    try:
        await bot.send(event=event, message=msgs)
    except ActionFailed:
        await bot.send(event=event, message=MessageSegment.image(url1))

# 2. 看XX 指令 (根据名称随机查询)
watchMatcher = on_startswith("看")

@watchMatcher.handle()
async def handle_watch(bot: Bot, event: Event):
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    # 1. 这里返回的是 int | None
    char_id = await to_thread.run_sync(get_char_id_by_alias_exact, char_name)
    
    # 2. 显式检查：如果 char_id 为 None，直接返回并提示
    if char_id is None:
        await bot.send(event, "没找到这个角色。")
        return

    # 3. 此时类型检查器知道 char_id 必定是 int，不会再报错
    card_id = get_random_card_id_by_character(char_id)
    
    if not char_name:
        return

    # 1. 依然通过数据库精确查找 charId
    char_id = await to_thread.run_sync(get_char_id_by_alias_exact, char_name)
    if not char_id:
        await bot.send(event, "没找到这个角色。")
        return

    # 2. 【核心修改】从 JSON 缓存中随机取一个卡面 ID
    card_id = get_random_card_id_by_character(char_id)
    
    # 3. 获取资源名
    asset_name = get_assetbundle_name(card_id) if card_id else None
    
    if not asset_name:
        await bot.send(event, "该角色暂无卡面数据。")
        return

    # 4. 随机返回一张
    suffix = random.choice(["card_normal.png", "card_after_training.png"])
    url = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/{suffix}"
    
    try:
        await bot.send(event, MessageSegment.image(url))
    except ActionFailed:
        await bot.send(event, "图片发送失败。")

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
    
    success, result_msg = await to_thread.run_sync(modify_alias_db_exact, target, new_alias, mode)
    await bot.send(event, result_msg)