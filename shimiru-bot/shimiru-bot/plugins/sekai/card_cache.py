import json
from pathlib import Path

# JSON 文件路径（按你的实际位置改）
CARD_MAP_PATH = Path(__file__).parent / "card_map.json"

# 全局缓存
CARD_MAP: dict[str, str] = {}


def load_card_map() -> dict[str, str]:
    """カードID -> assetbundleName のマップを読み込む"""
    global CARD_MAP

    if not CARD_MAP_PATH.exists():
        raise FileNotFoundError(f"找不到文件: {CARD_MAP_PATH}")

    with CARD_MAP_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("card_map.json 格式错误：必须是 dict，例如 {'1': 'res001_no001'}")

    # 确保 key/value 都是 str
    CARD_MAP = {str(k): str(v) for k, v in data.items()}
    return CARD_MAP


# 模块导入时立刻加载（只执行一次）
load_card_map()


def get_assetbundle_name(card_id: int) -> str | None:
    """カードIDからassetbundleNameを取得する"""
    return CARD_MAP.get(str(card_id))
