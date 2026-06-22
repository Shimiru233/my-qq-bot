import hashlib
import random
from pathlib import Path

import yaml
from curl_cffi import requests
from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
# from nonebot.logger import logger

PLUGIN_DIR = Path(__file__).parent
CACHE_DIR = PLUGIN_DIR / "cards_cache"
YAML_PATH = PLUGIN_DIR / "as_cards.yaml"
BASE_URL = "https://llwiki.org/mediawiki/img_auth.php"

with YAML_PATH.open("r", encoding="utf-8") as f:
    CHAR_CARDS: dict[str, list[int]] = yaml.safe_load(f)

CACHE_DIR.mkdir(exist_ok=True)

watch_matcher = on_startswith("看")


def get_wiki_path(card_id: int, suffix: str) -> Path:
    """Local cache path for a card image."""
    return CACHE_DIR / f"{card_id}_{suffix}.png"


def build_wiki_url(card_id: int, suffix: str) -> str:
    """Build the img_auth.php URL via MD5 hash of the wiki filename."""
    wiki_name = f"AS_Card_{card_id}_{suffix}.png"
    md5 = hashlib.md5(wiki_name.encode()).hexdigest()
    return f"{BASE_URL}/{md5[0]}/{md5[:2]}/{wiki_name}"


def ensure_cached(card_id: int, suffix: str) -> Path | None:
    """Download the image to local cache if not already present. Returns the cache path or None."""
    cache_path = get_wiki_path(card_id, suffix)
    if cache_path.exists():
        return cache_path

    url = build_wiki_url(card_id, suffix)
    try:
        resp = requests.get(url, impersonate="chrome131", timeout=15)
        if resp.status_code == 200:
            cache_path.write_bytes(resp.content)
            return cache_path
    except Exception as e:
  #      logger.warning(f"Download failed for card {card_id}_{suffix}: {e}"
        return None


@watch_matcher.handle()
async def handle_watch(bot: Bot, event: Event):
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    card_ids = CHAR_CARDS.get(char_name)
    if not card_ids:
        return

    card_id = random.choice(card_ids)
    suffix = random.choice(("a", "b"))

    img_path = ensure_cached(card_id, suffix)
    if img_path is None:
        # fallback to the other suffix
        alt = "a" if suffix == "b" else "b"
        img_path = ensure_cached(card_id, alt)

    if img_path is None:
   #     logger.warning(f"Could not fetch image for card {card_id}")
        return

    await bot.send(event, MessageSegment.image(img_path))
