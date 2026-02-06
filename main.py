from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Set, Any, Optional
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger

class Action(Enum):
    ACCEPT = "accept"
    REJECT = "reject"

class FriendBotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_file = StarTools.get_data_dir() / "friend_data.json"
        self.lock = asyncio.Lock()
        self.users: Dict[str, Dict[str, Any]] = self.load_data()

    def load_data(self) -> Dict[str, Dict[str, Any]]:
        """从JSON文件加载用户数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 确保每个用户都有完整的字段
                    for uid in data:
                        user_data = data[uid]
                        if "name" not in user_data:
                            user_data["name"] = ""
                        if "friends" in user_data and isinstance(user_data["friends"], list):
                            user_data["friends"] = set(user_data["friends"])
                        else:
                            user_data["friends"] = set()
                        if "inbox" not in user_data:
                            user_data["inbox"] = {}
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"数据文件解析失败: {e}，使用空数据启动")
            except Exception as e:
                logger.error(f"加载数据失败: {e}")
        return {}

    async def save_data(self) -> None:
        """保存用户数据到JSON文件（调用者必须持有self.lock锁）"""
        # 注意：此函数假设调用者已经持有self.lock锁
        data_to_save = {}
        for uid, user_data in self.users.items():
            data_to_save[uid] = {
                "name": user_data["name"],
                "friends": list(user_data["friends"]),
                "inbox": user_data["inbox"]
            }
        
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.data_file)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            raise

    async def _get_or_create_user(self, uid: str, name: str) -> None:
        """注册新用户或更新现有用户名"""
        async with self.lock:
            if uid not in self.users:
                self.users[uid] = {"name": name, "friends": set(), "inbox": {}}
            else:
                if self.users[uid]["name"] != name:
                    self.users[uid]["name"] = name
        await self.save_data()

    async def send_request(self, from_id: str, to_id: str, msg: str = "") -> str:
        """发送好友申请"""
        async with self.lock:
            # 检查发送者是否有待处理的好友申请
            if from_id in self.users:
                inbox = self.users[from_id].get("inbox", {})
                if inbox:
                    pending_list = []
                    for rid, req in inbox.items():
                        pending_list.append(f"• {req['from_name']}({rid}): {req['msg']}")
                    notice = f"⚠️ 您有 {len(inbox)} 条好友申请待处理：\n" + "\n".join(pending_list)
                    notice += f"\n\n💡 请处理完您的好友申请后再添加他人"
                    return notice

            if to_id == from_id:
                return "❌ 不能添加自己为好友"
            
            if to_id not in self.users:
                return f"❌ 用户 {to_id} 不存在或未使用过本Bot"
                
            from_user = self.users[from_id]
            to_user = self.users[to_id]
            
            if to_id in from_user["friends"]:
                return f"✅ 你们已经是好友了"
                
            if from_id in to_user["inbox"]:
                return f"⏳ 您已经向 {to_user['name']} 发送过好友申请了"
                 
            req = {
                "from": from_id,
                "from_name": from_user["name"],
                "to": to_id,
                "msg": msg or "请求添加您为好友",
                "time": datetime.now().strftime("%m-%d %H:%M")
            }
            
            to_user["inbox"][from_id] = req
        await self.save_data()
        return f"✅ 已向 {to_user['name']}({to_id}) 发送好友申请"

    async def handle_request(self, uid: str, target_id: str, action: Action) -> str:
        """处理好友申请（同意/拒绝）"""
        async with self.lock:
            if uid not in self.users:
                return "❌ 您还未注册"
                
            current_user = self.users[uid]
            req = current_user["inbox"].get(target_id)
            
            if not req:
                return "❌ 未找到该好友申请"
                
            friend_id = target_id
            if friend_id not in self.users:
                return "❌ 该用户已不存在"
                 
            friend_user = self.users[friend_id]
            
            if action == Action.ACCEPT:
                current_user["friends"].add(friend_id)
                friend_user["friends"].add(uid)
                if friend_id in current_user["inbox"]:
                    del current_user["inbox"][friend_id]
                await self.save_data()
                return f"✅ 已同意 {friend_user['name']} 的好友申请"
                
            elif action == Action.REJECT:
                if friend_id in current_user["inbox"]:
                    del current_user["inbox"][friend_id]
                await self.save_data()
                return f"❌ 已拒绝 {friend_user['name']} 的好友申请"
                
            return "❌ 无效的操作"

    async def remove_friend(self, uid: str, fid: str) -> str:
        """删除好友"""
        async with self.lock:
            if uid not in self.users:
                return "❌ 您还未注册"
            
            current_user = self.users[uid]
            if fid not in current_user["friends"]:
                return "❌ 你们不是好友"
                
            current_user["friends"].remove(fid)
            if fid in self.users:
                self.users[fid]["friends"].discard(uid)
                
        await self.save_data()
        friend_name = self.users[fid]['name'] if fid in self.users else fid
        return f"✅ 已删除好友 {friend_name}"

    async def show_info(self, uid: str) -> str:
        """显示用户信息"""
        async with self.lock:
            if uid not in self.users:
                return "❌ 您还未注册"
                
            current_user = self.users[uid]
            
            # 好友列表
            friends_list = []
            for fid in current_user["friends"]:
                name = self.users[fid]["name"] if fid in self.users else fid
                friends_list.append(f"{name}({fid})")
            
            # 待处理申请
            pending_list = []
            inbox_count = len(current_user["inbox"])
            for rid, req in current_user["inbox"].items():
                pending_list.append(f"• {req['from_name']}({rid}): {req['msg']}")
            
            lines = [f"👤 {current_user['name']} 的信息:"]
            lines.append(f"\n🤝 好友({len(friends_list)}): {', '.join(friends_list) if friends_list else '无'}")
            
            if inbox_count > 0:
                lines.append(f"\n🔔 待处理申请({inbox_count}): \n" + "\n".join(pending_list))
                lines.append(f"\n💡 提示: 使用 /friend accept <ID> 同意申请")
            else:
                lines.append(f"\n📭 待处理申请: 无")
                
            return "\n".join(lines)

    async def initialize(self) -> None:
        pass

    async def terminate(self) -> None:
        pass

@filter.command("friend")
    async def friend(self, event: AstrMessageEvent):
        '''好友系统命令 /friend add <id> [msg] - 添加好友 /friend accept <id> - 同意好友申请 /friend reject <id> - 拒绝好友申请 /friend remove <id> - 删除好友 /friend list - 查看好友列表和待处理申请 '''
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        await self._get_or_create_user(user_id, user_name)
        
        text = event.message_str.strip()
        args = text.split()
        
        # 移除命令前缀
        clean_args = args
        if args and args[0].lower() in ["/friend", "friend"]:
            clean_args = args[1:]
            
        if not clean_args:
            yield event.plain_result("可用命令: add, accept, reject, remove, list")
            return

        cmd = clean_args[0].lower()
        
        if cmd == "add":
            yield event.plain_result(await self._handle_add(user_id, clean_args))
        elif cmd == "accept":
            yield event.plain_result(await self._handle_accept(user_id, clean_args))
        elif cmd == "reject":
            yield event.plain_result(await self._handle_reject(user_id, clean_args))
        elif cmd == "remove":
            yield event.plain_result(await self._handle_remove(user_id, clean_args))
        elif cmd == "list":
            yield event.plain_result(await self.show_info(user_id))
        else:
            yield event.plain_result(f"❌ 未知命令 '{cmd}'，可用: add, accept, reject, remove, list")

    async def _handle_add(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "用法: /friend add <对方ID> [备注消息]"
        target_id = args[1]
        msg = " ".join(args[2:]) if len(args) > 2 else ""
        return await self.send_request(user_id, target_id, msg)

    async def _handle_accept(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "用法: /friend accept <对方ID>"
        target_id = args[1]
        return await self.handle_request(user_id, target_id, Action.ACCEPT)

    async def _handle_reject(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "用法: /friend reject <对方ID>"
        target_id = args[1]
        return await self.handle_request(user_id, target_id, Action.REJECT)

    async def _handle_remove(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "用法: /friend remove <对方ID>"
        target_id = args[1]
        return await self.remove_friend(user_id, target_id)
                        

            
                    
