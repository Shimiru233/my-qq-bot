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
from .card_cache import get_assetbundle_name

# 环境路径配置
sys.path.insert(0, "/home/admin/Sources/nonebot/nonebot.venv/lib/python3.12/site-packages")

# 初始化配置与数据库连接池
CONFIG_PATH = Path(__file__).parent / "my_config.yaml"
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

# 假设与 Arcaea 使用同一个数据库实例，但表结构不同
db_pool = pool.ThreadedConnectionPool(
    1, 5, host="localhost", database="pjsk_assets",
    user="common_user;", password="password"
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

def get_random_card_id_by_char(char_id: int) -> int | None:
    """获取指定角色下的随机一张卡面 ID"""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # 假设你的卡面表名为 m_card，角色字段为 character_id
            cur.execute("SELECT id FROM m_card WHERE character_id = %s", (char_id,))
            rows = cur.fetchall()
            if not rows:
                return None
            return random.choice(rows)[0]
    finally:
        db_pool.putconn(conn)

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
    # 提取“看”后面的内容并去除空格
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    char_id = await to_thread.run_sync(get_char_id_by_alias_exact, char_name)
    if not char_id:
        await bot.send(event, "没找到这个角色。")
        return

    card_id = await to_thread.run_sync(get_random_card_id_by_char, char_id)
    asset_name = get_assetbundle_name(card_id) if card_id else None
    
    if not asset_name:
        await bot.send(event, "该角色暂无卡面数据。")
        return

    # 随机返回一张（普通或觉醒）
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