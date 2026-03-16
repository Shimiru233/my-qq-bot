from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot,Event,Message,MessageSegment
from nonebot import on_startswith
from nonebot import on_command
from nonebot.params import EventMessage
from .card_cache import get_assetbundle_name
from nonebot.adapters.onebot.v11.exception import ActionFailed

import yaml
import sys

sys.path.insert(0, "/home/admin/Sources/nonebot/nonebot.venv/lib/python3.12/site-packages")

import aiohttp
from pathlib import Path




CONFIG_PATH = Path(__file__).parent / "my_config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)


matcher = on_startswith("kard", ignorecase=True)
@matcher.handle()

async def handle_function(bot: Bot, event: Event, msg: Message = EventMessage()):
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

 #   await bot.send(event=event, message=MessageSegment.image(url1))
 #   await bot.send(event=event, message=MessageSegment.image(url2))

matcher2 = on_command("kard")
@matcher2.handle()
async def handle_function2(bot: Bot,event: Event):
        await bot.send(event=event, message="card是{parceled_card_id}")

