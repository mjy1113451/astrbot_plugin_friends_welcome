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

from astrbot.api.event import filter, AstrMessageEventfrom astrbot.api.star import Context, Star, registerfrom astrbot.api import loggerimport jsonimport osfrom datetime import datetime@register("friendbot", "mjy1113451", "好友系统插件", "1.0.0")class FriendBotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_file = os.path.join(os.path.dirname(__file__), "data.json")
        self.users = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert lists back to sets for friends
                    for uid in data:
                        data[uid]["friends"] = set(data[uid]["friends"])
                    return data
            except Exception as e:
                logger.error(f"Failed to load data: {e}")
        return {}

    def save_data(self):
        # Convert sets to lists for JSON serialization
        data_to_save = {}
        for uid, user_data in self.users.items():
            data_to_save[uid] = {
                "name": user_data["name"],
                "friends": list(user_data["friends"]),
                "inbox": user_data["inbox"]
            }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    def _get_or_create_user(self, uid, name):
        if uid not in self.users:
            self.users[uid] = {"name": name, "friends": set(), "inbox": {}}
            self.save_data()
        else:
            # Update name if changed
            if self.users[uid]["name"] != name:
                self.users[uid]["name"] = name
                self.save_data()

    # Logic methods
    def send_request(self, from_id, to_id, msg=""):
        if to_id == from_id:
            return "❌ 不能加自己"
        
        if to_id not in self.users:
            return f"❌ 用户 {to_id} 未注册（对方需至少使用过一次此Bot）"
            
        f = self.users[from_id]
        t = self.users[to_id]
        
        if to_id in f["friends"]:
            return f"⚠️ {t['name']} 已经是你的好友"
            
        if from_id in t["inbox"]:
             return f"⚠️ 已发送过申请，请等待 {t['name']} 处理"
             
        req = {
            "from": from_id,
            "from_name": f["name"],
            "to": to_id,
            "msg": msg or "请求添加你为好友",
            "time": datetime.now().strftime("%m-%d %H:%M")
        }
        
        t["inbox"][from_id] = req
        self.save_data()
        return f"✅ 已向 {t['name']}({to_id}) 发送好友申请"

    def handle_request(self, uid, target_id, action):
        if uid not in self.users:
            return "❌ 你未注册"
            
        u = self.users[uid]
        req = u["inbox"].get(target_id)
        
        if not req:
            return "❌ 申请不存在或已处理"
            
        f_id = target_id
        if f_id not in self.users:
             return "❌ 申请人不存在"
             
        f = self.users[f_id]
        
        if action == "同意":
            u["friends"].add(f_id)
            f["friends"].add(uid)
            if f_id in u["inbox"]:
                del u["inbox"][f_id]
            self.save_data()
            return f"✅ 你和 {f['name']} 成为好友"
            
        elif action == "拒绝":
            if f_id in u["inbox"]:
                del u["inbox"][f_id]
            self.save_data()
            return f"❌ 你拒绝了 {f['name']} 的申请"
            
        return "❌ 无效操作"

    def remove_friend(self, uid, fid):
        if uid not in self.users:
            return "❌ 你未注册"
        
        u = self.users[uid]
        if fid not in u["friends"]:
            return "❌ 对方不是好友"
            
        u["friends"].remove(fid)
        if fid in self.users:
            self.users[fid]["friends"].discard(uid)
            
        self.save_data()
        return f"✅ 已解除与 {self.users[fid]['name'] if fid in self.users else fid} 的好友关系"

    def show_info(self, uid):
        if uid not in self.users:
            return "❌ 你未注册"
            
        u = self.users[uid]
        friends_list = []
        for fid in u["friends"]:
            name = self.users[fid]["name"] if fid in self.users else fid
            friends_list.append(f"{name}({fid})")
            
        pending_list = []
        for rid, req in u["inbox"].items():
            pending_list.append(f"{req['from_name']}({rid}): {req['msg']}")
            
        lines = [f" {u['name']}:"]
        lines.append(f" 好友: {', '.join(friends_list) if friends_list else '无'}")
        lines.append(f" 待处理申请: {', '.join(pending_list) if pending_list else '无'}")
        return "\n".join(lines)@filter.command("friend")
    async def friend(self, event: AstrMessageEvent):
        '''好友系统指令 /friend add <id> [msg] - 申请好友 /friend accept <id> - 同意申请 /friend reject <id> - 拒绝申请 /friend remove <id> - 删除好友 /friend list - 查看列表 '''
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        self._get_or_create_user(user_id, user_name)
        
        text = event.message_str.strip()
        args = text.split()
        
        # Handle case where command might be included in message_str or not
        # If the user types "/friend list", message_str might be "list" or "/friend list" depending on platform adapter
        # We will filter out the command trigger if present
        
        clean_args = []
        for arg in args:
            if arg.lower() in ["/friend", "friend"]:
                continue
            clean_args.append(arg)
            
        if not clean_args:
             yield event.plain_result("请输入子指令: add, accept, reject, remove, list")
             return

        cmd = clean_args[0].lower()
        
        if cmd == "add":
            if len(clean_args) < 2:
                yield event.plain_result("❌ 用法: /friend add <目标ID> [留言]")
                return
            target_id = clean_args[1]
            msg = " ".join(clean_args[2:]) if len(clean_args) > 2 else ""
            res = self.send_request(user_id, target_id, msg)
            yield event.plain_result(res)
            
        elif cmd == "accept":
            if len(clean_args) < 2:
                yield event.plain_result("❌ 用法: /friend accept <目标ID>")
                return
            target_id = clean_args[1]
            res = self.handle_request(user_id, target_id, "同意")
            yield event.plain_result(res)
            
        elif cmd == "reject":
            if len(clean_args) < 2:
                yield event.plain_result("❌ 用法: /friend reject <目标ID>")
                return
            target_id = clean_args[1]
            res = self.handle_request(user_id, target_id, "拒绝")
            yield event.plain_result(res)
            
        elif cmd == "remove":
            if len(clean_args) < 2:
                yield event.plain_result("❌ 用法: /friend remove <目标ID>")
                return
            target_id = clean_args[1]
            res = self.remove_friend(user_id, target_id)
            yield event.plain_result(res)
            
        elif cmd == "list":
            res = self.show_info(user_id)
            yield event.plain_result(res)
            
        else:
            yield event.plain_result(f"❌ 未知指令 '{cmd}'，可用: add, accept, reject, remove, list")
