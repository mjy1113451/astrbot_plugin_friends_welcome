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

# 初始化机器人，替换为你的机器人配置
bot = Bot(
    # 根据你使用的平台填写配置，例如 QQ 平台需填写 appid、token 等
    platform="qq",
    config={
        "appid": "你的应用ID",
        "token": "你的机器人令牌",
        "secret": "你的应用密钥"
    }
)

# 存储待处理的好友申请（申请ID: 申请对象信息）
pending_requests = {}

# 监听好友申请事件
@bot.on_event(EventType.FRIEND_REQUEST)
async def handle_friend_request(event):
    """处理好友申请事件，向管理员发送通知"""
    req_id = event.request_id  # 申请唯一标识
    requester_id = event.user_id  # 申请人ID
    requester_nick = event.nickname  # 申请人昵称

    # 存储申请信息，用于后续处理
    pending_requests[req_id] = {
        "user_id": requester_id,
        "nickname": requester_nick
    }

    # 向管理员发送申请通知（替换为你的管理员ID）
    admin_id = "你的管理员QQ号/账号ID"
    await bot.send_private_msg(
        user_id=admin_id,
        message=f"收到好友申请：\n申请人昵称：{requester_nick}\n申请人ID：{requester_id}\n回复【同意 {req_id}】或【拒绝 {req_id}】处理该申请"
    )

# 监听管理员的私聊消息指令
@bot.on_event(EventType.PRIVATE_MESSAGE)
async def handle_admin_command(event):
    """处理管理员的同意/拒绝指令"""
    # 仅响应管理员消息
    if event.user_id != "你的管理员QQ号/账号ID":
        return

    msg = event.message.strip()
    # 解析指令：同意 [申请ID] / 拒绝 [申请ID]
    if msg.startswith("同意 "):
        req_id = msg.split(" ")[-1]
        if req_id in pending_requests:
            # 执行同意好友申请
            await bot.set_friend_request(
                request_id=req_id,
                approve=True,  # True为同意，False为拒绝
                remark=""  # 可添加好友备注
            )
            requester = pending_requests.pop(req_id)
            await bot.send_private_msg(
                user_id=event.user_id,
                message=f"已同意【{requester['nickname']}】的好友申请"
            )
        else:
            await bot.send_private_msg(
                user_id=event.user_id,
                message="无效的申请ID，请检查后重试"
            )

    elif msg.startswith("拒绝 "):
        req_id = msg.split(" ")[-1]
        if req_id in pending_requests:
            # 执行拒绝好友申请
            await bot.set_friend_request(
                request_id=req_id,
                approve=False
            )
            requester = pending_requests.pop(req_id)
            await bot.send_private_msg(
                user_id=event.user_id,
                message=f"已拒绝【{requester['nickname']}】的好友申请"
            )
        else:
            await bot.send_private_msg(
                user_id=event.user_id,
                message="无效的申请ID，请检查后重试"
            )

# 启动机器人
async def main():
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
