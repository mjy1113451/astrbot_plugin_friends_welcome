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
        """安全加载用户数据，支持异常恢复"""
        if not os.path.exists(self.data_file):
            return {}
        
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # 验证数据结构
                if not isinstance(data, dict):
                    logger.warning("数据格式错误，重置数据")
                    return {}
                
                # 安全转换数据类型
                for uid, user_data in data.items():
                    if not isinstance(user_data, dict):
                        logger.warning(f"用户 {uid} 数据格式错误")
                        data[uid] = self._get_default_user_data("未知用户")
                        continue
                    
                    # 确保必需字段存在
                    if "friends" not in user_data:
                        user_data["friends"] = set()
                    elif isinstance(user_data["friends"], list):
                        user_data["friends"] = set(user_data["friends"])
                    
                    if "inbox" not in user_data:
                        user_data["inbox"] = {}
                    
                    if "name" not in user_data:
                        user_data["name"] = "未知用户"
                        
                return data
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}，尝试恢复")
            return self._try_recover_data()
        except PermissionError as e:
            logger.error(f"权限错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return {}

    def _try_recover_data(self) -> Dict[str, Dict[str, Any]]:
        """尝试恢复损坏的数据"""
        backup_file = self.data_file.with_suffix('.bak')
        if os.path.exists(backup_file):
            try:
                with open(backup_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info("从备份恢复数据成功")
                    return data
            except:
                pass
        return {}

    def _get_default_user_data(self, name: str) -> Dict[str, Any]:
        """获取默认用户数据结构"""
        return {
            "name": name,
            "friends": set(),
            "inbox": {}
        }

    async def save_data(self, create_backup: bool = True) -> bool:
        """安全保存用户数据，支持备份"""
        async with self.lock:
            data_to_save = {}
            for uid, user_data in self.users.items():
                data_to_save[uid] = {
                    "name": user_data["name"],
                    "friends": list(user_data["friends"]),
                    "inbox": user_data["inbox"]
                }
            
            try:
                # 创建备份
                if create_backup and os.path.exists(self.data_file):
                    backup_file = self.data_file.with_suffix('.bak')
                    try:
                        import shutil
                        shutil.copy2(self.data_file, backup_file)
                    except:
                        pass
                
                # 安全写入
                os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
                temp_file = self.data_file.with_suffix('.tmp')
                
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
                temp_file.replace(self.data_file)
                return True
                
            except Exception as e:
                logger.error(f"保存数据失败: {e}")
                return False

    async def _get_or_create_user(self, uid: str, name: str) -> None:
        """安全创建或更新用户"""
        async with self.lock:
            if uid not in self.users:
                self.users[uid] = self._get_default_user_data(name)
            else:
                if self.users[uid]["name"] != name:
                    self.users[uid]["name"] = name
        # 在锁外保存，减少锁持有时间
        await self.save_data(create_backup=False)

    async def check_pending_requests(self, uid: str) -> Optional[List[Dict[str, str]]]:
        """检查待处理的好友申请，返回申请列表"""
        async with self.lock:
            if uid not in self.users:
                return None
            
            inbox = self.users[uid].get("inbox", {})
            if not inbox:
                return []
            
            pending_list = []
            for rid, req in inbox.items():
                pending_list.append({
                    "id": rid,
                    "name": req.get('from_name', '未知'),
                    "message": req.get('msg', '无'),
                    "time": req.get('time', '')
                })
            
            return pending_list

    async def send_request(self, from_id: str, to_id: str, msg: str = "") -> str:
        """发送好友申请，包含完整验证"""
        
        # 验证输入
        if not self._validate_id(from_id) or not self._validate_id(to_id):
            return "❌ 无效的用户ID"
        
        # 检查发送者是否有待处理申请
        pending = await self.check_pending_requests(from_id)
        if pending is None:
            return "❌ 发送者未注册"
        if pending:
            pending_list = [f"• {p['name']}({p['id']})" for p in pending[:3]]
            notice = f"⚠️ 您有 {len(pending)} 条好友申请待处理：\n" + "\n".join(pending_list)
            if len(pending) > 3:
                notice += f"\n...还有 {len(pending) - 3} 条"
            notice += f"\n\n使用 /friend accept <ID> 同意，/friend reject <ID> 拒绝\n💡 请处理完您的好友申请后再添加他人"
            return notice
        
        async with self.lock:
            # 再次检查（在锁内）确保并发安全
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
                "time": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            to_user["inbox"][from_id] = req
            save_success = await self.save_data(create_backup=False)
            
            if save_success:
                return f"✅ 已向 {to_user['name']}({to_id}) 发送好友申请"
            else:
                # 回滚操作
                del to_user["inbox"][from_id]
                return "❌ 发送失败，请重试"

    async def handle_request(self, uid: str, target_id: str, action: Action) -> str:
        """处理好友申请，包含完整错误处理"""
        
        if not self._validate_id(target_id):
            return "❌ 无效的目标ID"
        
        async with self.lock:
            if uid not in self.users:
                return "❌ 您还未注册，请先使用本Bot"
                
            current_user = self.users[uid]
            req = current_user["inbox"].get(target_id)
            
            if not req:
                return "❌ 未找到该好友申请，可能已过期或被取消"
                
            if target_id not in self.users:
                return "❌ 该用户已注销"
                 
            friend_user = self.users[target_id]
            
            if action == Action.ACCEPT:
                current_user["friends"].add(target_id)
                friend_user["friends"].add(uid)
                if target_id in current_user["inbox"]:
                    del current_user["inbox"][target_id]
                
                if not await self.save_data():
                    # 保存失败，回滚
                    current_user["friends"].discard(target_id)
                    friend_user["friends"].discard(uid)
                    return "❌ 操作失败，请重试"
                
                return f"✅ 已同意 {friend_user['name']} 的好友申请，现在你们是好友了！"
                
            elif action == Action.REJECT:
                if target_id in current_user["inbox"]:
                    del current_user["inbox"][target_id]
                
                if not await self.save_data():
                    return "❌ 操作失败，请重试"
                
                return f"❌ 已拒绝 {friend_user['name']} 的好友申请"
                
            return "❌ 无效的操作"

    async def remove_friend(self, uid: str, fid: str) -> str:
        """删除好友，包含完整验证"""
        
        if not self._validate_id(fid):
            return "❌ 无效的好友ID"
        
        async with self.lock:
            if uid not in self.users:
                return "❌ 您还未注册"
            
            current_user = self.users[uid]
            if fid not in current_user["friends"]:
                return "❌ 你们不是好友，无法删除"
                
            current_user["friends"].discard(fid)
            if fid in self.users:
                self.users[fid]["friends"].discard(uid)
                
            if not await self.save_data():
                # 回滚
                current_user["friends"].add(fid)
                if fid in self.users:
                    self.users[fid]["friends"].add(uid)
                return "❌ 删除失败，请重试"
                
        friend_name = self.users[fid]['name'] if fid in self.users else fid
        return f"✅ 已删除好友 {friend_name}"

    def show_info(self, uid: str) -> str:
        """显示用户信息，包含错误处理"""
        if not self._validate_id(uid):
            return "❌ 无效的用户ID"
        
        if uid not in self.users:
            return "❌ 您还未注册，请先使用本Bot"
            
        current_user = self.users[uid]
        
        # 好友列表
        friends_list = []
        for fid in current_user["friends"]:
            if fid in self.users:
                name = self.users[fid]["name"]
                friends_list.append(f"{name}({fid})")
            else:
                friends_list.append(f"已注销({fid})")
        
        # 待处理申请
        inbox = current_user.get("inbox", {})
        pending_list = []
        for rid, req in inbox.items():
            name = req.get('from_name', '未知')
            msg = req.get('msg', '无')
            pending_list.append(f"• {name}({rid}): {msg}")
        
        lines = [f"👤 {current_user['name']} 的信息:"]
        lines.append(f"\n🤝 好友列表 ({len(friends_list)}人):")
        if friends_list:
            # 每行显示3个好友
            for i in range(0, len(friends_list), 3):
                lines.append(" " + ", ".join(friends_list[i:i+3]))
        else:
            lines.append(" 无")
        
        if inbox:
            lines.append(f"\n🔔 待处理申请 ({len(inbox)}条):")
            for item in pending_list:
                lines.append(f" {item}")
            lines.append(f"\n💡 操作提示:")
            lines.append(" /friend accept <ID> - 同意申请")
            lines.append(" /friend reject <ID> - 拒绝申请")
        else:
            lines.append(f"\n📭 待处理申请: 无")
            
        return "\n".join(lines)

    def _validate_id(self, uid: str) -> bool:
        """验证用户ID格式"""
        if not uid or not isinstance(uid, str):
            return False
        return len(uid.strip()) > 0

    async def initialize(self) -> None:
        """初始化插件"""
        logger.info("好友系统插件已加载")
        # 可以在这里执行初始化操作

    async def terminate(self) -> None:
        """清理插件资源"""
        await self.save_data()  # 确保数据保存
        logger.info("好友系统插件已卸载")

    @filter.command("friend")
    async def friend(self, event: AstrMessageEvent):
        '''好友系统命令 /friend add <id> [msg] - 添加好友（id为对方用户ID，msg为附加消息） /friend accept <id> - 同意好友申请 /friend reject <id> - 拒绝好友申请 /friend remove <id> - 删除好友 /friend list - 查看好友列表和待处理申请 '''
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        try:
            await self._get_or_create_user(user_id, user_name)
        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            yield event.plain_result("❌ 系统错误，请稍后重试")
            return
        
        text = event.message_str.strip()
        
        # 安全解析参数
        args = self._parse_command_args(text)
        
        if not args:
            yield event.plain_result(self._get_help_message())
            return

        cmd = args[0].lower()
        
        try:
            if cmd == "add":
                result = await self._handle_add(user_id, args)
                yield event.plain_result(result)
            elif cmd == "accept":
                result = await self._handle_accept(user_id, args)
                yield event.plain_result(result)
            elif cmd == "reject":
                result = await self._handle_reject(user_id, args)
                yield event.plain_result(result)
            elif cmd == "remove":
                result = await self._handle_remove(user_id, args)
                yield event.plain_result(result)
            elif cmd == "list":
                result = self.show_info(user_id)
                yield event.plain_result(result)
            elif cmd in ["help", "?"]:
                yield event.plain_result(self._get_help_message())
            else:
                yield event.plain_result(f"❌ 未知命令 '{cmd}'，输入 /friend help 查看帮助")
        except Exception as e:
            logger.error(f"命令处理错误: {e}")
            yield event.plain_result("❌ 命令执行失败，请稍后重试")

    def _parse_command_args(self, text: str) -> List[str]:
        """安全解析命令参数"""
        if not text:
            return []
        
        parts = text.split()
        if not parts:
            return []
            
        # 移除命令前缀
        if parts[0].lower() in ["/friend", "friend"]:
            parts = parts[1:]
        
        # 过滤空字符串并去除多余空格
        args = [arg.strip() for arg in parts if arg.strip()]
        return args

    def _get_help_message(self) -> str:
        """获取帮助消息"""
        return """🤖 好友系统使用指南 📋 可用命令： /friend add <ID> [消息] - 发送好友申请 /friend accept <ID> - 同意好友申请 /friend reject <ID> - 拒绝好友申请 /friend remove <ID> - 删除好友 /friend list - 查看好友和申请 /friend help - 显示此帮助 💡 提示： - 对方需要先使用过本Bot才能添加 - 有待处理申请时无法添加新好友 - 输入ID时请准确复制用户ID"""

    async def _handle_add(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "❌ 用法错误\n用法: /friend add <对方ID> [备注消息]\n\n💡 提示: 对方ID可通过 /friend list 查看"
        target_id = args[1].strip()
        msg = " ".join(args[2:]).strip() if len(args) > 2 else ""
        
        if not target_id:
            return "❌ ID不能为空"
            
        return await self.send_request(user_id, target_id, msg)

    async def _handle_accept(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "❌ 用法错误\n用法: /friend accept <对方ID>"
        target_id = args[1].strip()
        
        if not target_id:
            return "❌ ID不能为空"
            
        return await self.handle_request(user_id, target_id, Action.ACCEPT)

    async def _handle_reject(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "❌ 用法错误\n用法: /friend reject <对方ID>"
        target_id = args[1].strip()
        
        if not target_id:
            return "❌ ID不能为空"
            
        return await self.handle_request(user_id, target_id, Action.REJECT)

    async def _handle_remove(self, user_id: str, args: List[str]) -> str:
        if len(args) < 2:
            return "❌ 用法错误\n用法: /friend remove <对方ID>"
        target_id = args[1].strip()
        
        if not target_id:
            return "❌ ID不能为空"
            
        return await self.remove_friend(user_id, target_id)
            
        
