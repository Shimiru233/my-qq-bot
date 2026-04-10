import json
import random
from pathlib import Path

CARD_MAP_PATH = Path(__file__).parent / "card_map.json"

CARD_MAP: dict[str, str] = {}
CHAR_TO_CARDS: dict[int, list[int]] = {}

def load_card_map():
    global CARD_MAP, CHAR_TO_CARDS
    if not CARD_MAP_PATH.exists():
        print(f"[PJSK Cache] 错误：找不到文件 {CARD_MAP_PATH}")
        return

    try:
        with CARD_MAP_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[PJSK Cache] JSON 解析失败: {e}")
        return

    tmp_card_map = {}
    tmp_char_to_cards = {}

    for item in data:
        # 强制将读取到的 ID 都转为 int，防止 JSON 里是字符串
        try:
            c_id = int(item.get("id"))
            char_id = int(item.get("characterId"))
            asset_name = str(item.get("assetbundleName"))
        except (TypeError, ValueError):
            continue # 跳过格式不规范的条目

        tmp_card_map[str(c_id)] = asset_name
        
        if char_id not in tmp_char_to_cards:
            tmp_char_to_cards[char_id] = []
        tmp_char_to_cards[char_id].append(c_id)

    CARD_MAP = tmp_card_map
    CHAR_TO_CARDS = tmp_char_to_cards
    print(f"[PJSK Cache] 加载成功: {len(CARD_MAP)} 张卡面, {len(CHAR_TO_CARDS)} 个角色")

load_card_map()

def get_assetbundle_name(card_id: int | None) -> str | None:
    if card_id is None: return None
    return CARD_MAP.get(str(card_id))

def get_random_card_id_by_character(char_id: int | None) -> int | None:
    """从缓存中随机抽取"""
    if char_id is None:
        return None
    
    # 强制将传入的 char_id 转为 int 查找
    ids = CHAR_TO_CARDS.get(int(char_id))
    return random.choice(ids) if ids else None