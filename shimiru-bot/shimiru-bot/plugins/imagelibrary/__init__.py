#!/usr/bin/python3
# _*_ coding: utf-8 _*_
#
# Copyright (C) 2024 - 2024 heihieyouheihei, Inc. All Rights Reserved
#
# @Time    : 2024/10/15 下午10:28
# @Author  : 单子叶蚕豆_DzyCd
# @File    : test.py
# @IDE     : PyCharm

from nonebot import on_startswith, require, logger
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.exception import MatcherException
from nonebot.permission import SUPERUSER
require("nonebot_plugin_localstore")
from pathlib import Path
import nonebot_plugin_localstore as store
from nonebot.plugin import PluginMetadata
__plugin_meta__ = PluginMetadata(
    name="ImageLibrary",
    description="一个共享给所有人的Bot图库",
    usage="""
        ==所有人可用==
        添加[XXX]: 可以向图库中添加XXX关键词视频/图片/文字内容
        来个/来只/来点[XXX]: 抽取图库中XXX关键词下的内容
        XXX后面接@[数字]可以选择词条下的指定内容
        插画[XXX]: 从网络引擎中获取XXX的随机高清图片
        ==管理员可用==
        @bot 启用/禁用XXX: 允许/禁用群内使用某一词条
            * 设定了禁用的词条不再可以从私聊获取
        @bot 删除XXX: 删除某一词条的部分内容
            只删[数字]: 删除关键词下指定的内容
            彻底删除: 删除整个词条
        @bot 图片列表: 查看图库中的所有关键词
        ==Bot主可用==
        @bot 独占/取消独占: 让某个群聊独占/取消独占一个关键词，其他群和私聊不可用
    """,
    type="application",
    homepage="https://github.com/DZYCD/nonebot-plugin-ImageLibrary",
    supported_adapters={"~onebot.v11"},
)
import random
import aiohttp
import json
import os


data_path: Path = store.get_plugin_data_dir()


class DataSetControl:
    def __init__(self, data_path, base_path):
        self.data_file = data_path
        self.base_path = base_path

    def delete_value(self, key: str, value):
        try:
            dic = self.get_dataset()
            del dic[key][value]
            self.save_dataset(dic)
        except:
            return False

    def delete_key(self, key: str):
        dic = self.get_dataset()
        del dic[key]
        self.save_dataset(dic)

    def get_dataset(self):
        with open(os.path.join(self.base_path, self.data_file), 'r', encoding='UTF-8') as f:
            try:
                load_dict = json.load(f)
                if isinstance(load_dict, dict):
                    return load_dict
                return {}
            except:
                return {}

    def save_dataset(self, source):
        json_dict = json.dumps(source, indent=2, ensure_ascii=False)
        with open(os.path.join(self.base_path, self.data_file), 'w', encoding='UTF-8') as f:
            f.write(json_dict)

    def search(self, dic: dict, key: str):
        try:
            return dic[key]
        except:
            return False

    def update_value(self, key: str, target: str, value):
        dic = self.get_dataset()
        if not self.search(dic, key):
            dic[key] = {}
        dic[key][target] = value
        self.save_dataset(dic)

    def get_value(self, key: str, target: str):
        dic = self.get_dataset()
        if self.search(dic, key):
            try:
                return dic[key][target]
            except:
                return False
        return False

    def ensure_directory_exists(self, path):
        if not os.path.exists(os.path.join(self.base_path, path)):
            os.mkdir(os.path.join(self.base_path, path))

    def ensure_file_exists(self, path):
        if not os.path.exists(os.path.join(self.base_path, path)):
            with open(os.path.join(self.base_path, path), 'w', encoding='UTF-8')as f:
                if 'json' in path:
                    f.write(json.dumps({}))


dataset = DataSetControl("image.json", data_path)

dataset.ensure_directory_exists("library")

dataset.ensure_file_exists("image.json")

add_matcher = on_startswith("/添加")
get_matcher = on_startswith(("/来只", "/来点", "/来个"))
pixiv_matcher = on_startswith("/插画")
delete_matcher = on_startswith("/删除", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)
list_matcher = on_startswith("/图片列表", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)
enable_matcher = on_startswith("/启用", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)
disable_matcher = on_startswith("/禁用", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER)
own_matcher = on_startswith("/独占", rule=to_me(), permission=SUPERUSER)
disown_matcher = on_startswith("/取消独占", rule=to_me(), permission=SUPERUSER)
intro_matcher = on_startswith("/关于图库", rule=to_me())


async def image_save(path, filename):
    img_src = filename
    async with aiohttp.ClientSession() as session:
        async with session.get(img_src) as response:
            content = await response.read()
            with open(os.path.join(data_path, "library", path), 'wb') as file_obj:
                file_obj.write(content)
    return os.path.join(data_path, "library", path)


def check_permission(event, key):
    from_info = event.get_session_id()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    try:
        ban_list = dataset.get_value(key, "ban").replace("'", '"')
        res_list = json.loads(ban_list)
        if "ALL" in res_list[0]:
            if group in res_list[0]:
                return True
            return False
        if len(res_list) > 0 and group == "personal":
            return False
        for i in res_list:
            if group in i:
                return False
        return True
    except:
        return True


@intro_matcher.handle()
async def _():
    msg = """Image Library 图库
一个共享给所有人的资源库

==所有人可用==
添加[XXX]: 可以向图库中添加XXX关键词视频/图片/文字内容
来个/来只/来点[XXX]: 抽取图库中XXX关键词下的内容
XXX后面接@[数字]可以选择词条下的指定内容
插画[XXX]: 从网络引擎中获取XXX的随机高清图片
==管理员可用==
启用/禁用XXX: 允许/禁用群内使用某一词条
    * 设定了禁用的词条不再可以从私聊获取
删除XXX: 删除某一词条的部分内容
    只删[数字]: 删除关键词下指定的内容
    彻底删除: 删除整个词条
图片列表: 查看图库中的所有关键词
==Bot主可用==
独占/取消独占: 让某个群聊独占/取消独占一个关键词，其他群和私聊不可用

有任何问题欢迎 @单子叶蚕豆 反馈！"""
    await intro_matcher.finish(msg)


@own_matcher.handle()
async def _(event: Event):
    from_info = event.get_session_id()
    key = event.get_plaintext().strip()[len("/独占"):].strip()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await own_matcher.finish("此功能仅可用于群聊")
        return
    try:
        ban_list = ["ALL" + group]
        dataset.update_value(key, "ban", str(ban_list))
    except MatcherException:
        raise
    except Exception as e:
        await own_matcher.finish(f"{key}词条不存在")
    await own_matcher.finish(f"本群已独占{key}词条")


@disown_matcher.handle()
async def _(event: Event):
    from_info = event.get_session_id()
    key = event.get_plaintext().strip()[len("/取消独占"):].strip()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await disown_matcher.finish("此功能仅可用于群聊")
        return
    try:
        ban_list = '[]'
        dataset.update_value(key, "ban", ban_list)
    except MatcherException:
        raise
    except Exception as e:
        await disown_matcher.finish(f"{key}词条不存在")
    await disown_matcher.finish(f"已解除{key}词条的独占")


@enable_matcher.handle()
async def _(event: Event):
    from_info = event.get_session_id()
    key = event.get_plaintext().strip()[len("/启用"):].strip()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await enable_matcher.finish("此功能仅可用于群聊")
        return

    ban_list = ""
    try:
        ban_list = dataset.get_value(key, "ban").replace("'", '"')
    except:
        await enable_matcher.finish(f"{key}词条不存在")
    res_list = json.loads(ban_list)
    if len(res_list) == 0:
        await enable_matcher.finish(f"已启用本群的{key}词条")
        return

    if "ALL" in res_list[0]:
        await enable_matcher.finish(f"{key}词条已被独占，请联系bot主获取权限吧")
    for i in range(len(res_list)):
        if group == res_list[i]:
            del res_list[i]
    dataset.update_value(key, "ban", str(res_list))
    await enable_matcher.finish(f"已启用本群的{key}词条")


@disable_matcher.handle()
async def _(event: Event):
    from_info = event.get_session_id()
    key = event.get_plaintext().strip()[len("/禁用"):].strip()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await disable_matcher.finish("此功能仅可用于群聊")
        return
    ban_list = ""
    try:
        ban_list = dataset.get_value(key, "ban").replace("'", '"')
    except:
        await disable_matcher.finish(f"{key}词条不存在")
    res_list = json.loads(ban_list)

    if len(res_list) and "ALL" in res_list[0]:
        await disable_matcher.finish(f"{key}词条已被独占，请联系bot主获取权限吧")
    res_list.append(group)
    dataset.update_value(key, "ban", str(res_list))
    await disable_matcher.finish(f"已禁用本群的{key}词条")


async def get_pixiv_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.text()
            m = random.choice(json.loads(data))
            return m


@pixiv_matcher.handle()
async def fetch_pixiv_data(event: Event):
    url = "https://image.anosu.top/pixiv/json"
    key = event.get_plaintext().strip()[len("/插画"):].strip()

    url = url + f"?keyword={key}"

    try:
        m = await get_pixiv_image(url)
        msg = "pid:{}\n>>>{}\ntags:{}".format(m["pid"], m["title"], m["tags"])
        await pixiv_matcher.finish(msg + MessageSegment.image(m["url"]))
    except MatcherException:
        raise
    except:
        await pixiv_matcher.finish("没找到关键tag...\n不过你可以尝试翻译成日文或者英文再试一次")


def _extract_images(message: Message) -> list[str]:
    """从消息中提取所有图片 URL"""
    urls = []
    for seg in message:
        if seg.type == "image":
            url = seg.data.get("url", "")
            if url:
                urls.append(url)
    return urls


async def _save_images(name: str, urls: list[str]) -> int:
    """把图片 URL 存到词条下，返回实际存了多少张"""
    p = dataset.get_value(name, "using")
    if not p:
        p = 0
    else:
        p = int(p)

    saved = 0
    for url in urls:
        p += 1
        path = await image_save(f"{name}{p}.png", url)
        dataset.update_value(name, str(p), path)
        saved += 1

    dataset.update_value(name, "using", p)
    if not dataset.get_value(name, "ban"):
        dataset.update_value(name, "ban", "[]")
    return saved


_adding_sessions: dict[str, str] = {}  # user_id → keyword


async def _get_replied_images(bot: Bot, event: Event) -> list[str]:
    """获取被引用消息中的图片 URL"""
    # LLOneBot / napcat 直接把被引消息放在 event.reply 里
    reply_info = getattr(event, "reply", None)
    if reply_info and isinstance(reply_info, dict):
        msg_content = reply_info.get("message")
        if msg_content:
            if isinstance(msg_content, Message):
                return _extract_images(msg_content)
            # 可能是 list[dict] 格式
            return _extract_images(Message(msg_content))

    # 回退：通过 bot.get_msg() 获取
    for seg in event.get_message():
        if seg.type == "reply":
            msg_id = seg.data.get("id")
            if msg_id:
                try:
                    replied = await bot.get_msg(message_id=int(msg_id))
                    msg_content = replied["message"]
                    if isinstance(msg_content, Message):
                        return _extract_images(msg_content)
                    return _extract_images(Message(msg_content))
                except Exception:
                    pass
            break
    return []


@add_matcher.handle()
async def _(bot: Bot, event: Event):
    name = event.get_plaintext().strip()[len("/添加"):].strip()
    if not check_permission(event, name):
        await add_matcher.finish(f"词条{name}被禁止使用")

    msg = event.get_message()
    # 当前消息或引用消息里有图片就直接存
    images = _extract_images(msg) + await _get_replied_images(bot, event)
    if images:
        saved = await _save_images(name, images)
        await add_matcher.finish(f"添加成功！已收录 {saved} 张图片")

    _adding_sessions[event.get_user_id()] = name
    await add_matcher.pause("添加什么图片？")


@add_matcher.handle()
async def _(bot: Bot, event: Event):
    user_id = event.get_user_id()
    name = _adding_sessions.pop(user_id, None)
    if name is None:
        return

    msg = event.get_message()
    images = _extract_images(msg) + await _get_replied_images(bot, event)
    if not images:
        await add_matcher.finish("请发送图片！")

    saved = await _save_images(name, images)
    await add_matcher.finish(f"添加成功！已收录 {saved} 张图片")


@get_matcher.handle()
async def _(event: Event):
    raw = event.get_plaintext().strip()
    for prefix in ("/来只", "/来点", "/来个"):
        if raw.startswith(prefix):
            msg = raw[len(prefix):].strip()
            break
    else:
        msg = raw

    if not check_permission(event, msg):
        await get_matcher.finish(f"词条{msg}被禁止使用")

    code = 0
    out_msg = ""
    try:
        if '@' in msg:
            code = msg.split("@")[1]
            try:
                int(code)
            except:
                await get_matcher.finish("@后面需要跟一个数字！")
            msg = msg.split("@")[0]
        else:
            p = dataset.get_value(msg, "using")
            if type(p) is bool:
                await get_matcher.finish("他貌似还没有被添加")
            if int(p) == 0:
                await get_matcher.finish("关键词存在，但是关键词下面没有可用词条欸，是不是被删除了？")
            code = str(random.randint(1, 100000) % int(p) + 1)

        p = dataset.get_value(msg, "using")
        if type(p) is bool:
            await get_matcher.finish("他貌似还没有被添加")
        if int(p) == 0:
            await get_matcher.finish("关键词存在，但是关键词下面没有可用词条欸，是不是被删除了？")
        if int(code) < 1 or int(p) < int(code):
            await get_matcher.finish(f"标号不对哦，现在此关键词下只有{p}个条目")

        out_msg = str(dataset.get_value(msg, code))
        logger.success("Get File:{}".format(out_msg))
    except MatcherException:
        raise
    except:
        await get_matcher.finish("他貌似还没有被添加")
    if 'mp4' in out_msg[-3:]:
        try:
            await get_matcher.finish(MessageSegment.video(out_msg))
        except MatcherException:
            raise
        except:
            p = dataset.get_value(msg, "using")
            del_value(msg, code)
            await get_matcher.finish(f'这个词条好像资源出问题了,我来清理掉，应该还剩{p - 1}个内容')
    if 'png' in out_msg[-3:]:
        try:
            await get_matcher.finish(MessageSegment.image(out_msg))
        except MatcherException:
            raise
        except:
            p = dataset.get_value(msg, "using")
            del_value(msg, code)
            await get_matcher.finish(f'这个词条好像资源出问题了,我来清理掉，应该还剩{p - 1}个内容')

    if 'False' == out_msg:
        await get_matcher.finish('没有这个编号...')
    await get_matcher.finish(MessageSegment.text(out_msg))


@delete_matcher.handle()
async def _(event: Event):
    name = event.get_plaintext().strip()[len("/删除"):].strip()

    if not check_permission(event, name):
        await delete_matcher.finish(f"词条{name}被禁止使用")
    else:
        dataset.update_value("deleting", "target", name)
        left = dataset.get_value(name, "using")
        if not left:
            await delete_matcher.finish(f"词条不存在")
        await delete_matcher.pause(f"{name}词条总共有{left}个内容，确定删除吗？")


def del_value(key, value):
    dataset.delete_value(key, value)
    node = dataset.get_dataset()[key]
    new_dic = {}
    count = 0
    for i in node:
        if i == "using":
            new_dic[i] = node[i] - 1
        elif i == "ban":
            new_dic[i] = node[i]
        else:
            count += 1
            new_dic[count] = node[i]
    dataset.delete_key(key)
    for i in new_dic:
        dataset.update_value(key, i, new_dic[i])


@delete_matcher.handle()
async def _(event: Event):
    msg = str(event.get_message())
    if msg == "确定":
        name = dataset.get_value("deleting", "target")
        dataset.update_value(name, "using", 0)
        await delete_matcher.finish("删除成功！")
    elif msg == "彻底删除":
        name = dataset.get_value("deleting", "target")
        dataset.delete_key(name)
        await delete_matcher.finish("它已经不复存在了！")
    elif "只删" in msg:
        p = msg.split('只删')[1]
        name = dataset.get_value("deleting", "target")
        del_value(name, p)
        left = dataset.get_value(name, "using")
        await delete_matcher.finish(f"好啦，我只删除了{p}，现在应该还有{left}个条目!")
    else:
        await delete_matcher.finish("好吧...如果你确定好了，告诉我一声")


@list_matcher.handle()
async def _():
    try:
        note = dataset.get_dataset()
        title_list = []
        for i in note:
            title_list.append(i)
        title_list.remove("adding")
        msg = MessageSegment.text("Bot总共记录了{}个关键词，分别为：".format(len(title_list)) + "\n" + str(title_list))
        await list_matcher.finish(msg)
    except MatcherException:
        raise
    except:
        await list_matcher.finish("出错了...")

