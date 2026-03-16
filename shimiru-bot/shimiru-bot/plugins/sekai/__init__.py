from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot,Event,Message,MessageSegment
from nonebot import on_startswith
from nonebot import on_command
from nonebot.params import EventMessage
from .card_cache import get_assetbundle_name
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.rule import to_me


import yaml
import sys
import db

sys.path.insert(0, "/home/admin/Sources/nonebot/nonebot.venv/lib/python3.12/site-packages")

import aiohttp
from pathlib import Path


busying = False

CONFIG_PATH = Path(__file__).parent / "my_config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)


kardMatcher = on_startswith("kard", ignorecase=True)

@kardMatcher.handle_card()
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

    # 假设 data['asset_api_url'] 类似 "https://sekai-assets-bdf29c81.seiunx.net"
    url1 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_normal.png"
    url2 = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_after_training.png"

    msgs = (
        MessageSegment.image(url1)
        + MessageSegment.image(url2)
    )

    try:
        await bot.send(event=event, message=msgs)
    except ActionFailed:
        # 发送多图失败就降级只发第一张
        await bot.send(event=event, message=MessageSegment.image(url1))


guessChartMatcher = on_command("gc", aliases={"猜图"}, ignorecase=True)
@guessChartMatcher.handle_guess_chart()

async def handle_guess_chart(bot: Bot, event: Event, msg: Message = EventMessage()):
    plain_text = msg.extract_plain_text().strip()
    parceled_card_id_str = plain_text.replace(" ", "")[2:]

    try:
        n = int(parceled_card_id_str)
    except ValueError:
        await bot.send(event=event, message="不知道。")
        return

    asset_name = get_assetbundle_name(n)
    if not asset_name:
        await bot.send(event=event, message="没找到这个卡。")
        return

    url = f"{data['asset_api_url'].rstrip('/')}/startapp/character/member/{asset_name}/card_guess.png"

    try:
        await bot.send(event=event, message=MessageSegment.image(url))
    except ActionFailed:
        await bot.send(event=event, message="发送图片失败了。")


to_meMatcher = to_me()
@to_meMatcher.handle_to_me()
async def handle_to_me(bot: Bot, event: Event, msg: Message = EventMessage()):
    plain_text = msg.extract_plain_text().strip()
    if busying:
        await bot.send(event=event, message="忙不过来了。")
        return
    if plain_text == "help":
        await bot.send(event=event, message="不帮助。")
        return
    if db.check_song_exists(plain_text):
        await bot.send(event=event, message="有这首歌。")
    else:
        await bot.send(event=event, message="没有这首歌。")
    
    

    
