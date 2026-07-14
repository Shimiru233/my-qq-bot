import hashlib
import random
import re
from pathlib import Path

import httpx
import yaml
from curl_cffi import requests
from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment

PLUGIN_DIR = Path(__file__).parent
CACHE_DIR = PLUGIN_DIR / "cards_cache"
YAML_PATH = PLUGIN_DIR / "as_cards.yaml"
WIKI_BASE = "https://llwiki.org/mediawiki/img_auth.php"
SIF2_BASE = "https://idol.st/SIF2"
SIF2_RANDOM = f"{SIF2_BASE}/cards/random/"

with YAML_PATH.open("r", encoding="utf-8") as f:
    CHAR_CARDS: dict[str, list[int]] = yaml.safe_load(f)

# SIF2 Romaji 路径 → [中文名, 别名, ...]
SIF2_CHARS: dict[str, list[str]] = {
    # µ's
    "Honoka-Kosaka":      ["高坂穗乃果", "穗乃果", "果皇", "honoka"],
    "Eli-Ayase":          ["绚濑绘里", "绘里", "eli"],
    "Kotori-Minami":      ["南小鸟", "小鸟", "kotori"],
    "Umi-Sonoda":         ["园田海未", "海未", "umi"],
    "Rin-Hoshizora":      ["星空凛", "凛", "rin"],
    "Maki-Nishikino":     ["西木野真姬", "真姬", "真姫", "maki"],
    "Nozomi-Tojo":        ["东条希", "希", "nozomi"],
    "Hanayo-Koizumi":     ["小泉花阳", "花阳", "hanayo"],
    "Nico-Yazawa":        ["矢泽妮可", "妮可", "日香", "nico", "niko"],
    # Aqours
    "Chika-Takami":       ["高海千歌", "千歌", "chika"],
    "Riko-Sakurauchi":    ["樱内梨子", "梨子", "riko"],
    "Kanan-Matsuura":     ["松浦果南", "果南", "kanan"],
    "Dia-Kurosawa":       ["黑泽黛雅", "黛雅", "dia"],
    "You-Watanabe":       ["渡边曜", "曜", "you"],
    "Yoshiko-Tsushima":   ["津岛善子", "善子", "夜羽", "yoshiko", "yohane"],
    "Hanamaru-Kunikida":  ["国木田花丸", "花丸", "hanamaru", "maru"],
    "Mari-Ohara":         ["小原鞠莉", "鞠莉", "mari"],
    "Ruby-Kurosawa":      ["黑泽露比", "露比", "ruby"],
    # 虹咲
    "Ayumu-Uehara":       ["上原步梦", "步梦", "ayumu"],
    "Kasumi-Nakasu":      ["中须霞", "霞", "kasumi"],
    "Shizuku-Osaka":      ["樱坂雫", "雫", "shizuku"],
    "Karin-Asaka":        ["朝香果林", "果林", "karin"],
    "Ai-Miyashita":       ["宫下爱", "爱", "ai"],
    "Kanata-Konoe":       ["近江彼方", "彼方", "kanata"],
    "Setsuna-Yuki":       ["优木雪菜", "雪菜", "setsuna"],
    "Emma-Verde":         ["艾玛·维尔德", "艾玛", "emma"],
    "Rina-Tennoji":       ["天王寺璃奈", "璃奈", "rina"],
    "Shioriko-Mifune":    ["三船栞子", "栞子", "shioriko"],
    "Mia-Taylor":         ["米娅·泰勒", "米娅", "mia"],
    "Lanzhu-Zhong":       ["钟岚珠", "岚珠", "lanzhu"],
    # Liella!
    "Kanon-Shibuya":      ["涩谷香音", "香音", "kanon"],
    "Keke-Tang":          ["唐可可", "可可", "keke"],
    "Chisato-Arashi":     ["岚千砂都", "千砂都", "chisato"],
    "Sumire-Heanna":      ["平安名堇", "堇", "sumire"],
    "Ren-Hazuki":         ["叶月恋", "恋", "ren"],
    "Kinako-Sakurakoji":  ["樱小路希奈子", "希奈子", "kinako"],
    "Mei-Yoneme":         ["米女芽衣", "芽衣", "mei"],
    "Shiki-Wakana":       ["若菜四季", "四季", "shiki"],
    "Natsumi-Onitsuka":   ["鬼冢夏美", "夏美", "natsumi"],
    "Wien-Margarete":     ["薇恩玛格丽特", "薇恩", "wien"],
    "Tomari-Onitsuka":    ["鬼冢冬毬", "冬毬", "tomari"],
    # Sunny Passion (SIF2 有收录)
    "Yuna-Ichiki":        ["一木优奈", "优奈", "yuna"],
    "Mao-Mihara":         ["三原真绪", "真绪", "mao"],
}

# 别名 → SIF2 路径（自动构建）
_sif2_lookup: dict[str, str] = {}
for _path, _aliases in SIF2_CHARS.items():
    for _a in _aliases:
        _sif2_lookup[_a.lower()] = _path


# ── LinkLike (莲之空) 角色 ──────────────────────────────
LINKLIKE_RANDOM = "https://idol.st/LinkLike/cards/random/"

LINKLIKE_CHARS: dict[str, list[str]] = {
    "Kaho-Hinoshita":             ["日野下花帆", "花帆", "kaho"],
    "Sayaka-Murano":              ["村野沙耶香", "沙耶香", "sayaka"],
    "Kozue-Otomune":              ["乙宗梢", "梢", "kozue"],
    "Tsuzuri-Yugiri":             ["夕雾缀理", "缀理", "tsuzuri"],
    "Rurino-Osawa":               ["大泽瑠璃乃", "瑠璃乃", "rurino"],
    "Megumi-Fujishima":           ["藤岛慈", "慈", "megumi"],
    "Ginko-Momose":               ["百生吟子", "吟子", "ginko"],
    "Kosuzu-Kachimachi":          ["徒町小铃", "小铃", "kosuzu"],
    "Hime-Anyoji":                ["安养寺姬", "姬芽", "hime"],
    "Ceras-Yanagida-Lilienfeld":  ["柳田赛丽丝", "赛丽丝", "ceras", "琉璃"],
    "Izumi-Katsuragi":            ["桂城泉", "泉", "izumi"],
    "Mion-Shinowa":               ["篠羽美音", "美音", "mion"],
    "Sachi-Ogami":                ["大神幸", "咲", "sachi"],
}

_linklike_lookup: dict[str, str] = {}
for _path, _aliases in LINKLIKE_CHARS.items():
    for _a in _aliases:
        _linklike_lookup[_a.lower()] = _path

CACHE_DIR.mkdir(exist_ok=True)

watch_matcher = on_startswith("看")
sif2_matcher = on_startswith(("/sif2", "/SIF2"))


# ── Wiki (All Stars) 图源 ─────────────────────────────

def get_wiki_path(card_id: int, suffix: str) -> Path:
    return CACHE_DIR / f"{card_id}_{suffix}.png"


def build_wiki_url(card_id: int, suffix: str) -> str:
    wiki_name = f"AS_Card_{card_id}_{suffix}.png"
    md5 = hashlib.md5(wiki_name.encode()).hexdigest()
    return f"{WIKI_BASE}/{md5[0]}/{md5[:2]}/{wiki_name}"


def ensure_cached(card_id: int, suffix: str) -> Path | None:
    cache_path = get_wiki_path(card_id, suffix)
    if cache_path.exists():
        return cache_path
    url = build_wiki_url(card_id, suffix)
    try:
        resp = requests.get(url, impersonate="chrome131", timeout=15)
        if resp.status_code == 200:
            cache_path.write_bytes(resp.content)
            return cache_path
    except Exception:
        return None


def get_wiki_image(card_id: int) -> Path | None:
    """随机取 a/b，失败就换另一个"""
    suffix = random.choice(("a", "b"))
    path = ensure_cached(card_id, suffix)
    if path is None:
        alt = "a" if suffix == "b" else "b"
        path = ensure_cached(card_id, alt)
    return path


# ── SIF2 图源 ─────────────────────────────────────────

async def _fetch_random(url: str, pattern: str) -> str | None:
    """通用：抓取随机卡面图 URL"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=20)
            html = resp.text
        match = re.search(pattern, html)
        if match:
            return match.group(0)
    except Exception:
        pass
    return None


async def fetch_sif2_random() -> str | None:
    return await _fetch_random(
        "https://idol.st/SIF2/cards/random/",
        r'https://i\.idol\.st/u/sif2/card/art/[^"\s]+\.png',
    )


async def fetch_linklike_random() -> str | None:
    return await _fetch_random(
        "https://idol.st/LinkLike/cards/random/",
        r'https://i\.idol\.st/u/linklike/card/art/[^"\s]+\.png',
    )


# ── 看 <角色名> ────────────────────────────────────────

@watch_matcher.handle()
async def handle_watch(bot: Bot, event: Event):
    char_name = event.get_plaintext().strip()[1:].strip()
    if not char_name:
        return

    card_ids = CHAR_CARDS.get(char_name)                # All Stars wiki
    sif2_path = _sif2_lookup.get(char_name.lower())     # SIF2
    ll_path = _linklike_lookup.get(char_name.lower())   # LinkLike

    if not card_ids and not sif2_path and not ll_path:
        return

    # 收集可用源，随机选一个
    sources = []
    if card_ids:
        sources.append("wiki")
    if sif2_path:
        sources.append("sif2")
    if ll_path:
        sources.append("linklike")

    choice = random.choice(sources)

    if choice == "sif2":
        url = await fetch_sif2_random()
        if url:
            await bot.send(event, MessageSegment.image(url))
            return
        # 失败回退 wiki
        if not card_ids:
            return
        choice = "wiki"

    if choice == "linklike":
        url = await fetch_linklike_random()
        if url:
            await bot.send(event, MessageSegment.image(url))
            return
        if not card_ids:
            return
        choice = "wiki"

    # wiki
    card_id = random.choice(card_ids)
    img_path = get_wiki_image(card_id)
    if img_path is None:
        return
    await bot.send(event, MessageSegment.image(img_path))


# ── /sif2 随机 SIF2 卡牌 ──────────────────────────────

@sif2_matcher.handle()
async def handle_sif2(bot: Bot, event: Event):
    url = await fetch_sif2_random()
    if url:
        await bot.send(event, MessageSegment.image(url))
    else:
        await bot.send(event, "SIF2 图源暂时不可用")
