"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: pystores 完整 Todo 应用 - 多用户隔离、声明式 Action、跨状态引用、STATE_MONITORS

运行: python examples/02_todo_app/main.py
访问: http://127.0.0.1:8081
"""

import asyncio

from dataclasses import field
from typing import Any, ClassVar, Dict, List

from nicegui import ui
from nicegui.binding import bindable_dataclass

from pystores import BaseStore, NiceGUIStore, nicegui_backend, store_manager
from pystores.result import Result

# ========== 1. 注入 NiceGUI 后端 ==========
nicegui_backend()


# ========== 2. 模拟服务层：按用户隔离的 Todo 数据 ==========
class MockTodoService:
    """每个 user_id 拥有独立的 todo 列表"""

    def __init__(self) -> None:
        self._data: Dict[str, List[Dict[str, Any]]] = {}

    def _todos_of(self, user_id: str) -> List[Dict[str, Any]]:
        return self._data.setdefault(user_id, [])

    async def execute(self, service_name: str, method_name: str, params: Dict[str, Any]) -> Result:
        user_id = params.get("user_id", "anonymous")
        todos = self._todos_of(user_id)

        if method_name == "list":
            return Result.create_success(todos)
        if method_name == "create":
            item = {
                "id": len(todos) + 1,
                "text": params.get("text", ""),
                "done": False,
            }
            todos.append(item)
            return Result.create_success(item)
        if method_name == "toggle":
            for item in todos:
                if item["id"] == params.get("id"):
                    item["done"] = not item["done"]
                    return Result.create_success(item)
            return Result.create_failure("NotFound", f"todo {params.get('id')} 不存在")
        if method_name == "delete":
            for i, item in enumerate(todos):
                if item["id"] == params.get("id"):
                    del todos[i]
                    return Result.create_success(True)
            return Result.create_failure("NotFound", f"todo {params.get('id')} 不存在")
        return Result.create_failure("NotFound", f"未知方法: {method_name}")


BaseStore.configure(service=MockTodoService())


# ========== 3. 定义领域状态 ==========
@bindable_dataclass
class UserStore(NiceGUIStore):
    """用户状态 - 演示持久化 + 跨状态共享字段"""

    _state_name: ClassVar[str] = "user"
    # 可被其他状态访问的共享字段白名单
    _state_share_fields: ClassVar[Dict[str, str]] = {
        "id": "client",
        "username": "client",
    }
    # 刷新后恢复用户名（browser 级持久化）
    _state_storage_field: ClassVar[Dict[str, str]] = {"username": "user"}
    id: str = ""
    username: str = ""
    is_authenticated: bool = False

    async def login(self, username: str) -> None:
        """模拟登录：设置用户信息并触发认证状态变化"""
        await self.update(
            {
                "id": f"u{abs(hash(username)) % 100000}",
                "username": username,
                "is_authenticated": True,
            }
        )

    async def logout(self) -> None:
        await self.update({"id": "", "username": "", "is_authenticated": False})


@bindable_dataclass
class TodoStore(NiceGUIStore):
    """待办状态 - 演示声明式 Action + 跨状态引用"""

    _state_name: ClassVar[str] = "todo"
    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "fetch_todos": {
            "service_name": "todo",
            "method_name": "list",
            "operation_type": "获取待办",
            "params_mapping": {"user_id": "user.id"},  # 跨状态引用：从 user 状态取 id
            "result_field": "todos",  # 将服务返回的列表写入 todos 字段
            "requires_token": False,
            "refresh": True,
        },
        "add_todo": {
            "service_name": "todo",
            "method_name": "create",
            "operation_type": "新增待办",
            "params_mapping": {"user_id": "user.id", "text": "text"},
            "requires_token": False,
        },
        "toggle_todo": {
            "service_name": "todo",
            "method_name": "toggle",
            "operation_type": "切换完成",
            "params_mapping": {"user_id": "user.id", "id": "id"},
            "requires_token": False,
        },
        "delete_todo": {
            "service_name": "todo",
            "method_name": "delete",
            "operation_type": "删除待办",
            "params_mapping": {"user_id": "user.id", "id": "id"},
            "requires_token": False,
        },
    }
    todos: List[Dict[str, Any]] = field(default_factory=list)


# ========== 4. 注册状态类到全局管理器（统一访问入口） ==========
store_manager.register(UserStore, TodoStore)


# ========== 5. 声明式副作用：登录自动加载 / 登出自动清空 ==========
BaseStore.set_monitors(
    {
        "user": {
            "is_authenticated": {
                True: [
                    {
                        "state": "todo",
                        "method": "fetch_todos",
                        "ui_context": True,
                        "params": {"user_id": "user.id"},
                    }
                ],
                False: [{"state": "todo", "method": "reset", "params": {"refresh": True}}],
            }
        }
    }
)


# ========== 6. 页面 ==========
@ui.page("/")
async def index() -> None:
    user = await store_manager.get("user")
    todo = await store_manager.get("todo")

    with ui.card().classes("w-full"):
        ui.label("pystores · 多用户 Todo").classes("text-2xl font-bold")
        ui.label(f"隔离信息 → client: `{user._client_id}` | browser: `{user._browser_id}`").classes(
            "text-xs text-gray-500"
        )
        ui.label("👉 开多个标签页，用不同用户名登录，各自拥有独立待办（多用户隔离）").classes(
            "text-xs text-blue-600"
        )

    # 登录区
    with ui.card().classes("w-full"):
        ui.label("👤 登录").classes("text-lg font-bold")
        name_input = ui.input(label="用户名", placeholder="输入昵称后点登录")
        ui.label().bind_text_from(user, "username", backward=lambda v: f"当前用户: {v or '未登录'}")
        with ui.row():
            ui.button(
                "登录", on_click=lambda: _do_login(user, todo, name_input, todo_container)
            ).props("outline")
            ui.button("登出", on_click=lambda: _do_logout(user, todo, todo_container)).props("flat")

    # 跨状态安全通信演示（白名单）
    with ui.card().classes("w-full"):
        ui.label("🔒 跨状态安全通信（白名单）").classes("text-lg font-bold")
        ui.label("user.id 已声明为共享字段 → 可读；user.password（未声明）→ 被拒").classes(
            "text-xs text-gray-500"
        )
        share_ok_label = ui.label()
        share_blocked_label = ui.label()
        ui.button(
            "测试白名单",
            on_click=lambda: asyncio.create_task(
                _demo_share(todo, share_ok_label, share_blocked_label)
            ),
        ).props("flat")

    # Todo 区
    with ui.card().classes("w-full"):
        ui.label("📋 我的待办").classes("text-lg font-bold")
        todo_container = ui.column()
        with ui.row().classes("items-center"):
            todo_input = ui.input(label="新待办", placeholder="输入内容")
            ui.button("添加", on_click=lambda: _do_add(todo, todo_input, todo_container)).props(
                "outline"
            )
            ui.button("刷新", on_click=lambda: _do_fetch(user, todo, todo_container)).props("flat")

    # 若已登录（刷新页面恢复），自动加载
    if user.is_authenticated:
        await _render_todos(todo, todo_container)


# ---- 事件处理器 ----
async def _do_login(
    user: UserStore,
    todo: TodoStore,
    name_input: ui.input,
    container: ui.column,
) -> None:
    name = str(name_input.value or "").strip()
    if not name:
        ui.notify("请输入用户名", type="warning")
        return
    await user.login(name)  # is_authenticated=True 会触发 STATE_MONITORS 异步自动 fetch
    await todo.fetch_todos()  # 主动加载保证渲染时序（monitor 为声明式副作用演示）
    await _render_todos(todo, container)
    ui.notify(f"已登录: {name}", type="positive")


async def _do_logout(user: UserStore, todo: TodoStore, container: ui.column) -> None:
    await user.logout()
    container.clear()
    ui.notify("已登出", type="info")


async def _do_fetch(user: UserStore, todo: TodoStore, container: ui.column) -> None:
    if not user.is_authenticated:
        ui.notify("请先登录", type="warning")
        return
    await todo.fetch_todos()
    await _render_todos(todo, container)


async def _demo_share(
    todo: TodoStore,
    ok_label: ui.label,
    blocked_label: ui.label,
) -> None:
    """演示跨状态白名单安全通信：共享字段可读，未声明字段被拒"""
    ok = await todo.get_state_value("user", "id", "")
    blocked = await todo.get_state_value("user", "password", "")
    ok_label.text = f"读取 user.id → success={ok.success}, data={ok.data!r}"
    blocked_label.text = f"读取 user.password → success={blocked.success}, code={blocked.code}"


async def _do_add(todo: TodoStore, todo_input: ui.input, container: ui.column) -> None:
    text = str(todo_input.value or "").strip()
    if not text:
        ui.notify("请输入内容", type="warning")
        return
    await todo.add_todo(text=text)
    todo_input.value = ""
    await _render_todos(todo, container)
    ui.notify(f"已新增: {text}", type="positive")


async def _render_todos(todo: TodoStore, container: ui.column) -> None:
    container.clear()
    if not todo.todos:
        with container:
            ui.label("（暂无待办，添加一个吧）").classes("text-gray-400")
        return
    with container:
        for item in todo.todos:
            with ui.row().classes("items-center"):
                ui.button(
                    "✓" if item["done"] else "○",
                    on_click=lambda i=item: _toggle(todo, i, container),
                ).props("flat round dense")
                ui.label(item["text"]).classes("line-through text-gray-400" if item["done"] else "")
                ui.button(
                    "删除",
                    on_click=lambda i=item: _delete(todo, i, container),
                ).props("flat dense color=red")


async def _toggle(todo: TodoStore, item: Dict[str, Any], container: ui.column) -> None:
    await todo.toggle_todo(id=item["id"])
    await _render_todos(todo, container)


async def _delete(todo: TodoStore, item: Dict[str, Any], container: ui.column) -> None:
    await todo.delete_todo(id=item["id"])
    await _render_todos(todo, container)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="127.0.0.1", port=8081, storage_secret="pystores-todo-secret")
