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

""" 好友申请处理 Bot 系统 功能：接收好友申请 -> 通知用户 -> 处理用户回复（同意/拒绝） """from dataclasses import dataclass, asdictfrom datetime import datetimefrom enum import Enumfrom typing import Dict, List, Optional, Callable, Anyimport random
class FriendRequestStatus(Enum):
    PENDING = "pending"      # 待处理
    ACCEPTED = "accepted"    # 已同意
    REJECTED = "rejected"    # 已拒绝
    EXPIRED = "expired"      # 已过期
@dataclassclass FriendRequest:
    """好友申请数据类"""
    request_id: str          # 申请ID
    from_user_id: str        # 申请人ID
    from_user_name: str      # 申请人昵称
    to_user_id: str          # 目标用户ID
    message: str             # 申请留言
    status: FriendRequestStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['processed_at'] = self.processed_at.isoformat() if self.processed_at else None
        return data
class User:
    """用户类"""
    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.friends: List[str] = []  # 好友ID列表
        self.pending_requests: Dict[str, FriendRequest] = {}  # 待处理申请
        
    def add_friend(self, friend_id: str):
        if friend_id not in self.friends:
            self.friends.append(friend_id)
            return True
        return False
    
    def has_friend(self, friend_id: str) -> bool:
        return friend_id in self.friends
class FriendRequestBot:
    """ 好友申请处理 Bot 核心流程： 1. 收到好友申请 -> 存储并通知目标用户 2. 等待用户回复（同意/拒绝） 3. 执行相应操作 """
    
    def __init__(self):
        self.users: Dict[str, User] = {}  # 用户池
        self.requests: Dict[str, FriendRequest] = {}  # 所有申请记录
        # 修复：回调函数应接受三个参数
        self.message_callbacks: List[Callable[[str, str, FriendRequest], Any]] = []
        
    def register_user(self, user_id: str, name: str) -> User:
        """注册用户"""
        if user_id not in self.users:
            self.users[user_id] = User(user_id, name)
            print(f"✅ 用户注册成功: {name}({user_id})")
        return self.users[user_id]
    
    def on_message(self, callback: Callable[[str, str, FriendRequest], Any]):
        """注册消息通知回调"""
        self.message_callbacks.append(callback)
        
    def _notify_user(self, user_id: str, message: str, request: FriendRequest):
        """通知用户（触发回调）"""
        user = self.users.get(user_id)
        if not user:
            print(f"❌ 用户 {user_id} 不存在")
            return
            
        # 存储待处理申请
        user.pending_requests[request.request_id] = request
        
        # 触发通知
        for callback in self.message_callbacks:
            try:
                callback(user_id, message, request)
            except Exception as e:
                print(f"通知失败: {e}")
    
    async def receive_friend_request(self, from_user_id: str, to_user_id: str, message: str = "") -> Optional[FriendRequest]:
        """ 接收好友申请（核心入口） """
        # 验证用户
        from_user = self.users.get(from_user_id)
        to_user = self.users.get(to_user_id)
        
        if not from_user or not to_user:
            print("❌ 用户不存在")
            return None
            
        # 检查是否已经是好友
        if to_user.has_friend(from_user_id):
            print(f"⚠️ {to_user.name} 已经是 {from_user.name} 的好友")
            return None
        
        # 创建申请记录
        request_id = f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}"
        request = FriendRequest(
            request_id=request_id,
            from_user_id=from_user_id,
            from_user_name=from_user.name,
            to_user_id=to_user_id,
            message=message or "请求添加你为好友",
            status=FriendRequestStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.requests[request_id] = request
        
        # 构造通知消息
        notify_msg = (
            f"
            f"来自: {from_user.name}({from_user_id})\n"
            f"留言: {request.message}\n"
            f"━━━━━━━━━━━━━━\n"
            f"回复【同意 {request_id}】或【拒绝 {request_id}】进行处理"
        )
        
        # 发送通知
        self._notify_user(to_user_id, notify_msg, request)
        
        print(f"\n {request_id} 给用户 {to_user.name}")
        return request
    
    async def process_user_response(self, user_id: str, request_id: str, action: str) -> bool:
        """ 处理用户回复（核心处理逻辑） action: "同意" 或 "拒绝" """
        user = self.users.get(user_id)
        if user is None:  # 修复：使用 is None 而不是 == None
            print(f"❌ 用户 {user_id} 不存在")
            return False
            
        # 查找待处理申请
        request = user.pending_requests.get(request_id)
        if not request:
            print(f"❌ 申请 {request_id} 不存在或已处理")
            return False
            
        if request.status != FriendRequestStatus.PENDING:
            print(f"⚠️ 该申请已处理，当前状态: {request.status.value}")
            return False
        
        from_user = self.users.get(request.from_user_id)

        if from_user is None:
            print(f"❌ 用户 {request.from_user_id} 不存在""")
            return False
        
        if action == "同意":
            # ===== 同意添加好友 =====
            request.status = FriendRequestStatus.ACCEPTED
            request.processed_at = datetime.now()
            
            # 双向添加好友关系
            user.add_friend(request.from_user_id)
            from_user.add_friend(user_id)
            
            # 从待处理列表移除
            del user.pending_requests[request_id]
            
            # 通知双方
            print(f"\n✅ {user.name} 同意了 {from_user.name} 的好友申请")
            print(f" {user.name} 和 {from_user.name} 成为好友")
            
            # 可选：通知申请人
            await self._notify_requester_accepted(request)
            
        elif action == "拒绝":
            # ===== 拒绝添加好友 =====
            request.status = FriendRequestStatus.REJECTED
            request.processed_at = datetime.now()
            
            # 从待处理列表移除
            del user.pending_requests[request_id]
            
            print(f"\n❌ {user.name} 拒绝了 {from_user.name} 的好友申请")
            print(f")
            
            # 可选：通知申请人被拒绝（根据业务需求）
            await self._notify_requester_rejected(request)
            
        else:
            print(f"⚠️ 无效的操作: {action}，请回复【同意】或【拒绝】")
            return False
            
        return True
    
    async def _notify_requester_accepted(self, request: FriendRequest):
        """通知申请人被同意"""
        print(f" {request.from_user_name}: {self.users[request.to_user_id].name} 已接受你的好友申请")
    
    async def _notify_requester_rejected(self, request: FriendRequest):
        """通知申请人被拒绝（可选，有些场景不通知）"""
        print(f" {request.from_user_name}: {request.to_user_id} 暂时无法添加你为好友")
    
    def get_user_pending_requests(self, user_id: str) -> List[FriendRequest]:
        """获取用户的待处理申请"""
        user = self.users.get(user_id)
        if user:
            return list(user.pending_requests.values())
        return []
    
    def list_friends(self, user_id: str) -> List[Any]:
        """列出用户好友"""
        user = self.users.get(user_id)
        if not user:
            return []
        return [self.users[uid].name for uid in user.friends if uid in self.users]
