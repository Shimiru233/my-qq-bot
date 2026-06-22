import random
import httpx
from nonebot import on_command, on_startswith, get_driver
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.adapters.onebot.v11.exception import ActionFailed

API_BASE = "https://bandori.party/api/cards/"
MEMBERS_API = "https://bandori.party/api/members/"
USER_AGENT = "ShimiruBot/1.0"
PAGE_SIZE = 100  # API 最大页大小

# ── 本地缓存 ──
all_cards: list[dict] = []           # 全量卡牌
member_map: dict[str, int] = {}      # 角色名 → member_id
member_names: dict[int, str] = {}    # member_id → 显示名
cards_by_member: dict[int, list[int]] = {}  # member_id → 卡牌索引列表

# 中文别名
EXTRA_ALIASES: dict[str, int] = {
    # Poppin'Party
    "ksm": 6, "香澄": 6, "户山香澄": 6, "ksar": 6,
    "tae": 7, "多英": 7, "花园多英": 7, "otae": 7,
    "rimi": 8, "里美": 8, "牛込里美": 8, "rimirin": 8,
    "saaya": 9, "沙绫": 9, "山吹沙绫": 9,
    "arisa": 10, "有咲": 10, "市谷有咲": 10,
    # Afterglow
    "ran": 11, "兰": 11, "美竹兰": 11,
    "moca": 12, "摩卡": 12, "青叶摩卡": 12,
    "himari": 13, "绯玛丽": 13, "上原绯玛丽": 13,
    "tomoe": 14, "巴": 14, "宇田川巴": 14,
    "tsugumi": 15, "鶇": 15, "羽泽鶇": 15,
    # HHW
    "kokoro": 16, "心": 16, "弦卷心": 16, "kkr": 16, "扣扣肉": 16,
    "kaoru": 17, "薰": 17, "濑田薰": 17,
    "hagumi": 18, "育美": 18, "北泽育美": 18,
    "kanon": 19, "花音": 19, "松原花音": 19,
    "misaki": 20, "美咲": 20, "奥泽美咲": 20, "msk": 20,
    # PasuPare
    "aya": 21, "彩": 21, "丸山彩": 21,
    "hina": 22, "日菜": 22, "冰川日菜": 22,
    "chisato": 23, "千圣": 23, "白鹭千圣": 23,
    "maya": 24, "麻弥": 24, "大和麻弥": 24,
    "eve": 25, "依芙": 25, "若宫依芙": 25, "夏娃": 25,
    # Roselia
    "yukina": 26, "友希那": 26, "凑友希那": 26, "ykn": 26,
    "sayo": 27, "纱夜": 27, "冰川纱夜": 27,
    "lisa": 28, "莉莎": 28, "今井莉莎": 28,
    "ako": 29, "亚子": 29, "宇田川亚子": 29,
    "rinko": 30, "燐子": 30, "白金燐子": 30,
    # Morfonica
    "mashiro": 31, "真白": 31, "仓田真白": 31,
    "touko": 32, "透子": 32, "桐谷透子": 32,
    "nanami": 33, "七深": 33, "广町七深": 33,
    "tsukushi": 34, "筑紫": 34, "二叶筑紫": 34,
    "rui": 35, "瑠依": 35, "八潮瑠依": 35,
    # RAS
    "layer": 36, "蕾拉": 36, "和奏蕾拉": 36, "reiyer": 36,
    "lock": 37, "六花": 37, "朝日六花": 37, "rokka": 37,
    "masking": 38, "增姬": 38, "佐藤增姬": 38, "masuki": 38,
    "pareo": 39, "帕蕾欧": 39, "鳰原令王那": 39,
    "chu2": 40, "chuchu": 40, "珠手": 40, "珠手知由": 40, "知由": 40,
    # MyGO!!!!!
    "tomori": 41, "灯": 41, "高松灯": 41,
    "anon": 42, "爱音": 42, "千早爱音": 42,
    "raana": 43, "乐奈": 43, "要乐奈": 43, "rana": 43,
    "soyo": 44, "爽世": 44, "长崎爽世": 44,
    "taki": 45, "立希": 45, "椎名立希": 45,
    # Ave Mujica
    "doloris": 46, "初华": 46, "三角初华": 46,
    "mortis": 47, "睦": 47, "若叶睦": 47,
    "timoris": 48, "海铃": 48, "八幡海铃": 48,
    "amoris": 49, "喵梦": 49, "祐天寺若麦": 49,
    "oblivionis": 50, "祥子": 50, "丰川祥子": 50,
}


def fetch_all_cards() -> list[dict]:
    """同步拉取全量卡牌（精简字段）"""
    cards = []
    page = 1
    while True:
        resp = httpx.get(
            API_BASE,
            params={"page": page, "page_size": PAGE_SIZE},
            headers={"User-Agent": USER_AGENT}, timeout=30.0,
        )
        data = resp.json()
        for c in data["results"]:
            cards.append({
                "id": c["id"],
                "name": c.get("name", ""),
                "member": c.get("member", 0),
                "attribute": c.get("i_attribute", "?"),
                "rarity": c.get("i_rarity", 0),
                "image": c.get("image"),
                "skill_name": c.get("skill_name", ""),
            })
        if data["next"] is None:
            break
        page += 1
    return cards


def build_member_map():
    """从 API 拉取角色列表，构建名字→ID 映射"""
    global member_map, member_names
    try:
        resp = httpx.get(
            MEMBERS_API, params={"page_size": 50},
            headers={"User-Agent": USER_AGENT}, timeout=15.0,
        )
        for m in resp.json()["results"]:
            mid = m["id"]
            member_names[mid] = m["name"]
            # 全名
            member_map[m["name"].lower()] = mid
            # 拆分名
            for part in m["name"].lower().split():
                if part not in member_map:
                    member_map[part] = mid
            # 日文名
            if m.get("japanese_name"):
                member_map[m["japanese_name"]] = mid
    except Exception:
        pass
    # 合并中文别名
    for alias, mid in EXTRA_ALIASES.items():
        member_map[alias.lower()] = mid


def build_cards_index():
    """构建 member_id → [卡牌索引列表]"""
    global cards_by_member, all_cards
    cards_by_member = {}
    for i, card in enumerate(all_cards):
        mid = card["member"]
        cards_by_member.setdefault(mid, []).append(i)


def _load_data():
    """启动时加载所有数据"""
    global all_cards
    build_member_map()
    all_cards = fetch_all_cards()
    build_cards_index()


driver = get_driver()


@driver.on_startup
async def on_startup():
    # 后台线程加载，不阻塞启动
    import threading
    t = threading.Thread(target=_load_data, daemon=True)
    t.start()


# ── 公共函数 ──


def format_card(card: dict) -> dict:
    """补全展示字段"""
    rarity_stars = "★" * card.get("rarity", 0)
    mid = card.get("member", 0)
    return {
        **card,
        "member_name": member_names.get(mid, f"ID:{mid}"),
        "rarity_stars": rarity_stars,
    }


def search_local(keyword: str) -> dict | None:
    """本地模糊搜索：卡牌名字包含关键词（忽略大小写）"""
    kw = keyword.lower()
    # 优先开头匹配
    for card in all_cards:
        if card["name"].lower().startswith(kw):
            return format_card(card)
    # 再包含匹配
    for card in all_cards:
        if kw in card["name"].lower():
            return format_card(card)
    return None


def random_card(member_id: int | None = None) -> dict | None:
    """随机一张卡牌，可指定角色"""
    if member_id is not None:
        indices = cards_by_member.get(member_id, [])
        if not indices:
            return None
        idx = random.choice(indices)
    else:
        if not all_cards:
            return None
        idx = random.randrange(len(all_cards))
    return format_card(all_cards[idx])


async def send_card(bot: Bot, event: Event, card: dict):
    """发卡图 + 文字信息"""
    text_msg = (
        f"卡牌: {card['name']}\n"
        f"角色: {card['member_name']}  |  "
        f"属性: {card['attribute']}  |  稀有度: {card['rarity_stars']}"
    )
    if card["skill_name"]:
        text_msg += f"\n技能: {card['skill_name']}"

    if card["image"]:
        try:
            await bot.send(event, MessageSegment.image(card["image"]))
        except ActionFailed:
            pass
    await bot.send(event, text_msg)


# ── /bds 模糊搜索卡牌 ──
bds_matcher = on_command("bds", aliases={"bandorisearch"})


@bds_matcher.handle()
async def search_card(bot: Bot, event: Event, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    if not keyword:
        await bot.send(event, "请输入卡牌名称，例如：/bds starry")
        return

    if not all_cards:
        await bot.send(event, "卡牌数据加载中，请稍候...")
        return

    card = search_local(keyword)
    if not card:
        await bot.send(event, "没有找到相关卡牌")
        return

    await send_card(bot, event, card)


# ── /bdra 随机展示卡牌 ──
bdra_matcher = on_command("bdra", aliases={"bandorirandom"})


@bdra_matcher.handle()
async def random_card_handler(bot: Bot, event: Event):
    if not all_cards:
        await bot.send(event, "卡牌数据加载中，请稍候...")
        return

    card = random_card()
    if not card:
        await bot.send(event, "卡牌库为空")
        return
    await send_card(bot, event, card)


# ── 看 <角色名> ──
watch_matcher = on_startswith("看")


@watch_matcher.handle()
async def handle_watch(bot: Bot, event: Event):
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    mid = member_map.get(char_name.lower())
    if mid is None:
        return  # 不是 bandori 角色

    if not all_cards:
        await bot.send(event, "卡牌数据加载中，请稍候...")
        return

    card = random_card(member_id=mid)
    if not card:
        await bot.send(event, f"角色 {char_name} 没有卡牌数据")
        return

    await send_card(bot, event, card)
