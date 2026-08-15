"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 声明式认证与生命周期示例 - token 自动注入、登录/登出、登出销毁、_before_dispose 钩子

运行: python examples/04_auth/main.py
访问: http://127.0.0.1:8083
密码: 123456
"""

import asyncio
from dataclasses import field
from typing import Any, ClassVar, Dict

from nicegui import ui
from nicegui.binding import bindable_dataclass

from pystores import BaseStore, NiceGUIStore, nicegui_backend
from pystores.result import Result

nicegui_backend()


# ========== 模拟认证服务：login 发 token，profile 校验 token ==========
class MockAuthService:
    async def execute(self, service_name: str, method_name: str, params: Dict[str, Any]) -> Result:
        if method_name == "login":
            username = params.get("username", "")
            if params.get("password") != "123456":
                return Result.create_failure("AuthFailed", "密码错误")
            return Result.create_success(
                {
                    "token": f"jwt-{username}-{abs(hash(username)) % 10000}",
                    "refresh_token": f"rt-{username}",
                    "id": f"u{abs(hash(username)) % 100000}",
                    "username": username,
                }
            )
        if method_name == "profile":
            token = params.get("token", "")
            if not token.startswith("jwt-"):
                return Result.create_failure("Unauthorized", "token 无效")
            username = token[4:].split("-")[0]
            return Result.create_success({"username": username, "role": "premium"})
        return Result.create_failure("NotFound", f"未知方法: {method_name}")


BaseStore.configure(service=MockAuthService())


# ========== 领域状态 ==========
@bindable_dataclass
class AuthStore(NiceGUIStore):
    """认证状态 - 声明式登录（token 自动合并），登出清状态 + 销毁"""

    _state_name: ClassVar[str] = "auth"
    _auth_state: ClassVar[str] = "auth"  # token 来源状态（供其他状态取 token）
    _state_share_fields: ClassVar[Dict[str, str]] = {
        "token": "client",
        "id": "client",
        "username": "client",
    }
    _state_storage_field: ClassVar[Dict[str, str]] = {
        "token": "user",
        "refresh_token": "user",
    }
    token: str = ""
    refresh_token: str = ""
    id: str = ""
    username: str = ""
    is_authenticated: bool = False

    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "login": {
            "service_name": "auth",
            "method_name": "login",
            "operation_type": "用户登录",
            "params_mapping": {"username": "username", "password": "password"},
            "requires_token": False,
            "refresh": True,
            # 登录成功后置认证态（触发 STATE_MONITORS 自动拉资料）
            "additional_updates": {"is_authenticated": True},
        },
    }

    async def logout(self) -> None:
        """登出：清空状态 + 清理持久化存储"""
        await self.update(
            {
                "token": "",
                "refresh_token": "",
                "id": "",
                "username": "",
                "is_authenticated": False,
            }
        )
        await self.__class__._storage.clear(self)

    async def _before_dispose(self) -> None:
        """生命周期钩子：实例销毁前清理（服务端日志可见）"""
        print(
            f"[04_auth] 销毁 {self._state_name} 实例，清理用户: {self.username or '(匿名)'}",
            flush=True,
        )


@bindable_dataclass
class ProfileStore(NiceGUIStore):
    """资料状态 - requires_token=True 的 action，token 由框架自动注入"""

    _state_name: ClassVar[str] = "profile"
    _auth_state: ClassVar[str] = "auth"  # 声明 token 来源状态
    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "fetch_profile": {
            "service_name": "auth",
            "method_name": "profile",
            "operation_type": "获取用户资料",
            "requires_token": True,  # ← 框架自动注入 token，无需手写
            "result_field": "profile",  # 服务返回的资料写入 profile 字段
            "refresh": True,
        },
    }
    profile: Dict[str, Any] = field(default_factory=dict)


# ========== 声明式副作用：登录拉资料 / 登出清资料 ==========
BaseStore.set_monitors(
    {
        "auth": {
            "is_authenticated": {
                True: [
                    {
                        "state": "profile",
                        "method": "fetch_profile",
                        "ui_context": True,
                        "params": {},
                    }
                ],
                False: [{"state": "profile", "method": "reset", "params": {}}],
            }
        }
    }
)


# ========== 页面 ==========
@ui.page("/")
async def index() -> None:
    auth = await AuthStore.get_instance()
    profile = await ProfileStore.get_instance()

    with ui.card().classes("w-full"):
        ui.label("pystores · 声明式认证").classes("text-2xl font-bold")
        ui.label(
            "体验：用户名任意 + 密码 123456 → 登录 → token 自动注入拉取资料 → 登出销毁实例"
        ).classes("text-xs text-blue-600")

    with ui.card().classes("w-full"):
        ui.label("🔐 登录").classes("text-lg font-bold")
        user_input = ui.input(label="用户名", placeholder="任意昵称")
        pwd_input = ui.input(label="密码", placeholder="123456", password=True)
        ui.label().bind_text_from(auth, "username", backward=lambda v: f"当前用户: {v or '未登录'}")
        with ui.row():
            ui.button(
                "登录",
                on_click=lambda: _login(auth, profile, user_input, pwd_input, profile_label),
            ).props("outline")
            ui.button(
                "登出并销毁",
                on_click=lambda: _logout(auth, profile, profile_label),
            ).props("flat color=red")

    with ui.card().classes("w-full"):
        ui.label("🎫 Token（requires_token 自动注入）").classes("text-lg font-bold")
        ui.label().bind_text_from(
            auth,
            "token",
            backward=lambda v: f"token: {v[:24] + '...' if v else '(空)'}",
        )

    with ui.card().classes("w-full"):
        ui.label("👤 用户资料（requires_token 服务）").classes("text-lg font-bold")
        profile_label = ui.label("未登录")
        _render_profile(profile, profile_label)


def _render_profile(profile: ProfileStore, label: ui.label) -> None:
    label.text = f"资料: {profile.profile}" if profile.profile else "未登录 / 无资料"


async def _login(
    auth: AuthStore,
    profile: ProfileStore,
    user_input: ui.input,
    pwd_input: ui.input,
    profile_label: ui.label,
) -> None:
    await auth.login(
        username=str(user_input.value or ""),
        password=str(pwd_input.value or ""),
    )
    await asyncio.sleep(0.1)  # 等 STATE_MONITORS 异步 fetch_profile 落库
    _render_profile(profile, profile_label)
    if auth.is_authenticated:
        ui.notify("登录成功，token 已注入并拉取资料", type="positive")
    else:
        ui.notify("登录失败（密码应为 123456）", type="negative")


async def _logout(auth: AuthStore, profile: ProfileStore, profile_label: ui.label) -> None:
    await auth.logout()
    await auth.__class__.dispose_instance()  # 销毁实例 → 触发 _before_dispose（服务端日志）
    _render_profile(profile, profile_label)
    ui.notify("已登出并销毁状态实例", type="info")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="127.0.0.1", port=8083, storage_secret="pystores-auth-secret")
