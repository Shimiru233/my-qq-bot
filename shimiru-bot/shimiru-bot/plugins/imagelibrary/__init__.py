#!/usr/bin/python3
# _*_ coding: utf-8 _*_
#
# Copyright (C) 2024 - 2024 heihieyouheihei, Inc. All Rights Reserved
#
# @Time    : 2024/10/15 下午10:28
# @Author  : 单子叶蚕豆_DzyCd
# @File    : test.py
# @IDE     : PyCharm

from nonebot import logger
from nonebot.rule import to_me
from nonebot.plugin import on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.exception import MatcherException
from nonebot.params import CommandArg
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot import require
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
                return load_dict
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
                    f.write(json.dumps("{}"))


dataset = DataSetControl("image.json", data_path)

dataset.ensure_directory_exists("library")

dataset.ensure_file_exists("image.json")

image_library_introduce = on_command("关于图库", rule=to_me(), priority=10, block=True)
image_adder = on_command("添加", rule=to_me(), priority=10, block=True)

get_image = on_command("来只", aliases={"来点", "来个"}, priority=10, block=True)
pixiv_image = on_command("插画", priority=10, block=True)

image_deleter = on_command("删除", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER, priority=10,
                           block=True)
image_list = on_command("图片列表", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER, priority=10,
                        block=True)
open_image_permission = on_command("启用", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER, priority=10,
                                   block=True)
close_image_permission = on_command("禁用", rule=to_me(), permission=GROUP_ADMIN | GROUP_OWNER | SUPERUSER, priority=10,
                                    block=True)

disown_image_permission = on_command("取消独占", rule=to_me(), permission=SUPERUSER, priority=10,
                                     block=True)
own_image_permission = on_command("独占", rule=to_me(), permission=SUPERUSER, priority=10,
                                  block=True)


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


@image_library_introduce.handle()
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
    await image_library_introduce.finish(msg)


@own_image_permission.handle()
async def _(event: Event, args: Message = CommandArg()):
    from_info = event.get_session_id()
    key = args.extract_plain_text()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await own_image_permission.finish("此功能仅可用于群聊")
        return
    try:
        ban_list = ["ALL" + group]
        dataset.update_value(key, "ban", str(ban_list))
    except MatcherException:
        raise
    except Exception as e:
        await own_image_permission.finish(f"{key}词条不存在")
    await own_image_permission.finish(f"本群已独占{key}词条")


@disown_image_permission.handle()
async def _(event: Event, args: Message = CommandArg()):
    from_info = event.get_session_id()
    key = args.extract_plain_text()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await disown_image_permission.finish("此功能仅可用于群聊")
        return
    try:
        ban_list = '[]'
        dataset.update_value(key, "ban", ban_list)
    except MatcherException:
        raise
    except Exception as e:
        await disown_image_permission.finish(f"{key}词条不存在")
    await disown_image_permission.finish(f"已解除{key}词条的独占")


@open_image_permission.handle()
async def _(event: Event, args: Message = CommandArg()):
    from_info = event.get_session_id()
    key = args.extract_plain_text()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await open_image_permission.finish("此功能仅可用于群聊")
        return

    ban_list = ""
    try:
        ban_list = dataset.get_value(key, "ban").replace("'", '"')
    except:
        await open_image_permission.finish(f"{key}词条不存在")
    res_list = json.loads(ban_list)
    if len(res_list) == 0:
        await open_image_permission.finish(f"已启用本群的{key}词条")
        return

    if "ALL" in res_list[0]:
        await open_image_permission.finish(f"{key}词条已被独占，请联系bot主获取权限吧")
    for i in range(len(res_list)):
        if group == res_list[i]:
            del res_list[i]
    dataset.update_value(key, "ban", str(res_list))
    await open_image_permission.finish(f"已启用本群的{key}词条")


@close_image_permission.handle()
async def _(event: Event, args: Message = CommandArg()):
    from_info = event.get_session_id()
    key = args.extract_plain_text()
    group = 'personal'
    if '_' in from_info:
        group = from_info.split('_')[1]
    if group == 'personal':
        await close_image_permission.finish("此功能仅可用于群聊")
        return
    ban_list = ""
    try:
        ban_list = dataset.get_value(key, "ban").replace("'", '"')
    except:
        await close_image_permission.finish(f"{key}词条不存在")
    res_list = json.loads(ban_list)

    if len(res_list) and "ALL" in res_list[0]:
        await close_image_permission.finish(f"{key}词条已被独占，请联系bot主获取权限吧")
    res_list.append(group)
    dataset.update_value(key, "ban", str(res_list))
    await close_image_permission.finish(f"已禁用本群的{key}词条")


async def get_pixiv_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.text()
            m = random.choice(json.loads(data))
            return m


@pixiv_image.handle()
async def fetch_pixiv_data(args: Message = CommandArg()):
    url = "https://image.anosu.top/pixiv/json"
    key = args.extract_plain_text()

    url = url + f"?keyword={key}"

    try:
        m = await get_pixiv_image(url)
        msg = "pid:{}\n>>>{}\ntags:{}".format(m["pid"], m["title"], m["tags"])
        await pixiv_image.finish(msg + MessageSegment.image(m["url"]))
    except MatcherException:
        raise
    except:
        await pixiv_image.finish("没找到关键tag...\n不过你可以尝试翻译成日文或者英文再试一次")


@image_adder.handle()
async def _(event: Event, args: Message = CommandArg()):
    name = args.extract_plain_text()
    if not check_permission(event, name):
        await image_adder.finish(f"词条{name}被禁止使用")
    else:
        dataset.update_value("adding", "target", name)
        await image_adder.pause("添加什么？")


@image_adder.handle()
async def _(event: Event):
    msg = str(event.get_message())

    msg = msg.replace("&#91;", "[")
    msg = msg.replace("&#93;", "]")
    msg = msg.replace("&amp;", "&")
    if "url=" in msg:
        msg = msg.split("url=")[1]
        msg = msg.split(']')[0]
    name = dataset.get_value("adding", "target")
    p = dataset.get_value(name, "using")

    if "cn:443/" in msg:
        msg = await image_save(f"{name}{p + 1}.mp4", msg)
    elif "download?" in msg:
        msg = await image_save(f"{name}{p + 1}.png", msg)
    if not p:
        dataset.update_value(name, "using", 1)
        dataset.update_value(name, "ban", "[]")
        dataset.update_value(name, "1", msg)
    else:
        dataset.update_value(name, "using", p + 1)
        dataset.update_value(name, str(p + 1), msg)
    await image_adder.finish("添加成功！")


@get_image.handle()
async def _(event: Event, args: Message = CommandArg()):
    msg = args.extract_plain_text()

    if not check_permission(event, msg):
        await get_image.finish(f"词条{msg}被禁止使用")

    code = 0
    out_msg = ""
    try:
        if '@' in msg:
            code = msg.split("@")[1]
            try:
                int(code)
            except:
                await get_image.finish("@后面需要跟一个数字！")
            msg = msg.split("@")[0]
        else:
            p = dataset.get_value(msg, "using")
            if type(p) is bool:
                await get_image.finish("他貌似还没有被添加")
            if int(p) == 0:
                await get_image.finish("关键词存在，但是关键词下面没有可用词条欸，是不是被删除了？")
            code = str(random.randint(1, 100000) % int(p) + 1)

        p = dataset.get_value(msg, "using")
        if type(p) is bool:
            await get_image.finish("他貌似还没有被添加")
        if int(p) == 0:
            await get_image.finish("关键词存在，但是关键词下面没有可用词条欸，是不是被删除了？")
        if int(code) < 1 or int(p) < int(code):
            await get_image.finish(f"标号不对哦，现在此关键词下只有{p}个条目")

        out_msg = str(dataset.get_value(msg, code))
        logger.success("Get File:{}".format(out_msg))
    except MatcherException:
        raise
    except:
        await get_image.finish("他貌似还没有被添加")
    if 'mp4' in out_msg[-3:]:
        try:
            await get_image.finish(MessageSegment.video(out_msg))
        except MatcherException:
            raise
        except:
            p = dataset.get_value(msg, "using")
            del_value(msg, code)
            await get_image.finish(f'这个词条好像资源出问题了,我来清理掉，应该还剩{p - 1}个内容')
    if 'png' in out_msg[-3:]:
        try:
            await get_image.finish(MessageSegment.image(out_msg))
        except MatcherException:
            raise
        except:
            p = dataset.get_value(msg, "using")
            del_value(msg, code)
            await get_image.finish(f'这个词条好像资源出问题了,我来清理掉，应该还剩{p - 1}个内容')

    if 'False' == out_msg:
        await get_image.finish('没有这个编号...')
    await get_image.finish(MessageSegment.text(out_msg))


@image_deleter.handle()
async def _(event: Event, args: Message = CommandArg()):
    name = args.extract_plain_text()

    if not check_permission(event, name):
        await image_deleter.finish(f"词条{name}被禁止使用")
    else:
        dataset.update_value("deleting", "target", name)
        left = dataset.get_value(name, "using")
        if not left:
            await image_deleter.finish(f"词条不存在")
        await image_deleter.pause(f"{name}词条总共有{left}个内容，确定删除吗？")


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


@image_deleter.handle()
async def _(event: Event):
    msg = str(event.get_message())
    if msg == "确定":
        name = dataset.get_value("deleting", "target")
        dataset.update_value(name, "using", 0)
        await image_deleter.finish("删除成功！")
    elif msg == "彻底删除":
        name = dataset.get_value("deleting", "target")
        dataset.delete_key(name)
        await image_deleter.finish("它已经不复存在了！")
    elif "只删" in msg:
        p = msg.split('只删')[1]
        name = dataset.get_value("deleting", "target")
        del_value(name, p)
        left = dataset.get_value(name, "using")
        await image_deleter.finish(f"好啦，我只删除了{p}，现在应该还有{left}个条目!")
    else:
        await image_deleter.finish("好吧...如果你确定好了，告诉我一声")


@image_list.handle()
async def _():
    try:
        note = dataset.get_dataset()
        title_list = []
        for i in note:
            title_list.append(i)
        title_list.remove("adding")
        msg = MessageSegment.text("Bot总共记录了{}个关键词，分别为：".format(len(title_list)) + "\n" + str(title_list))
        await image_list.finish(msg)
    except MatcherException:
        raise
    except:
        await image_list.finish("出错了...")

