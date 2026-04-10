import json
from pathlib import Path
import random

# JSON 文件路径
CARD_MAP_PATH = Path(__file__).parent / "card_map.json"

# 全局缓存：key 为字符串格式的 id，value 为 assetbundleName
CARD_MAP: dict[str, str] = {}
# 新增：按 characterId 分组的缓存 { char_id: [card_id1, card_id2, ...] }
CHAR_TO_CARDS: dict[int, list[int]] = {}

def load_card_map() -> dict[str, str]:
    """从对象列表格式的 JSON 中加载数据到内存缓存"""
    global CARD_MAP

    if not CARD_MAP_PATH.exists():
        raise FileNotFoundError(f"找不到文件: {CARD_MAP_PATH}")

    with CARD_MAP_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # 校验是否为列表格式
    if not isinstance(data, list):
        raise ValueError("card_map.json 格式错误：应当是一个包含对象的列表 [...]")

    # 遍历列表，提取 id 和 assetbundleName
    # 使用字典推导式快速构建缓存
    new_map = {}
    for item in data:
        # 确保必要的键存在
        card_id = item.get("id")
        asset_name = item.get("assetbundleName")
        
        if card_id is not None and asset_name:
            new_map[str(card_id)] = str(asset_name)

    CARD_MAP = new_map
    return CARD_MAP


# 模块导入时立刻加载
load_card_map()
print(f"成功加载角色卡面索引，共计 {len(CHAR_TO_CARDS)} 个角色")

def get_assetbundle_name(card_id: int) -> str | None:
    """通过卡片 ID 获取对应的资源包名称"""
    return CARD_MAP.get(str(card_id))

def get_random_card_id_by_character(char_id: int) -> int | None:
    """从 JSON 缓存中按 characterId 随机抽取一个 card_id"""
    card_ids = CHAR_TO_CARDS.get(char_id)
    return random.choice(card_ids) if card_ids else None