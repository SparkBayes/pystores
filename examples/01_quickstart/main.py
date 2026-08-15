"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: pystores 快速开始 demo - 展示响应式绑定、多用户隔离、声明式 Action、持久化、生命周期

运行: python examples/01_quickstart/main.py
访问: http://127.0.0.1:8080
"""

from dataclasses import field
from typing import Any, ClassVar, Dict

from nicegui import ui
from nicegui.binding import bindable_dataclass

from pystores import BaseStore, NiceGUIStore, nicegui_backend
from pystores.result import Result

# ========== 1. 注入 NiceGUI 后端（上下文 + 存储） ==========
nicegui_backend()

# ========== 2. 模拟服务层（实现 ServiceExecutor 协议） ==========
# 真实项目中，这里对接你自己的服务（如 HTTP API、数据库服务）


class MockTodoService:
    """模拟 Todo 服务 - 声明式 Action 通过它调用"""

    def __init__(self) -> None:
        self._todos: list[Dict[str, Any]] = [
            {"id": 1, "text": "了解 pystores 核心概念"},
            {"id": 2, "text": "体验多用户隔离"},
            {"id": 3, "text": "用声明式 Action 接真实服务"},
        ]

    async def execute(self, service_name: str, method_name: str, params: Dict[str, Any]) -> Result:
        if method_name == "list":
            return Result.create_success(self._todos)
        if method_name == "create":
            item = {"id": len(self._todos) + 1, "text": params.get("text", "")}
            self._todos.append(item)
            return Result.create_success(item)
        return Result.create_failure("NotFound", f"未知方法: {method_name}")


BaseStore.configure(service=MockTodoService())


# ========== 3. 定义领域状态 ==========
@bindable_dataclass
class CounterStore(NiceGUIStore):
    """计数器 - 演示响应式绑定 + 多用户隔离 + 持久化"""

    _state_name: ClassVar[str] = "counter"
    _state_storage_field: ClassVar[Dict[str, str]] = {"count": "user"}  # 刷新后恢复
    count: int = 0


@bindable_dataclass
class TodoStore(NiceGUIStore):
    """Todo - 演示声明式 Action（自动生成 fetch_todos / add_todo 方法）"""

    _state_name: ClassVar[str] = "todo"
    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "fetch_todos": {
            "service_name": "todo",
            "method_name": "list",
            "operation_type": "获取待办列表",
            "result_field": "todos",  # 将服务返回的列表写入 todos 字段
            "requires_token": False,
            "refresh": True,  # 自动管理 is_loading
        },
        "add_todo": {
            "service_name": "todo",
            "method_name": "create",
            "operation_type": "新增待办",
            "params_mapping": {"text": "text"},
            "requires_token": False,
        },
    }
    todos: list[Dict[str, Any]] = field(default_factory=list)


# ========== 4. 页面 ==========
_page_executions = 0


@ui.page("/")
async def index() -> None:
    global _page_executions
    _page_executions += 1
    print(f"[DEMO] 页面执行 # {_page_executions}", flush=True)
    counter = await CounterStore.get_instance()
    todo = await TodoStore.get_instance()

    # ---- 顶部：会话信息（多用户隔离演示） ----
    with ui.card().classes("w-full"):
        ui.label("pystores · 快速开始").classes("text-2xl font-bold")
        ui.label(
            f"隔离信息 → client: `{counter._client_id}` | "
            f"tab: `{counter._tab_id}` | browser: `{counter._browser_id}`"
        ).classes("text-xs text-gray-500")
        ui.label(
            "👉 再开一个标签页访问本页，计数是独立的（多用户隔离）；刷新本页计数会恢复（持久化）"
        ).classes("text-xs text-blue-600")

    # ---- 计数器：响应式绑定 + 隔离 + 持久化 ----
    with ui.card().classes("w-full"):
        ui.label("① 计数器 · 响应式绑定").classes("text-lg font-bold")
        ui.label().bind_text_from(counter, "count", backward=lambda v: f"当前计数: {v}")
        ui.label("注：刷新页面后计数恢复（_state_storage_field 持久化）").classes(
            "text-xs text-gray-500"
        )
        with ui.row():
            ui.button("-1", on_click=lambda: _update_counter(counter, -1)).props("flat")
            ui.button("+1", on_click=lambda: _update_counter(counter, 1)).props("outline")
            ui.button("重置", on_click=lambda: _reset_counter(counter)).props("flat")

    # ---- Todo：声明式 Action ----
    with ui.card().classes("w-full"):
        ui.label("② Todo · 声明式 Action（10 行配置代替样板代码）").classes("text-lg font-bold")
        todo_container = ui.column()
        with ui.row().classes("items-center"):
            todo_input = ui.input(label="新待办", placeholder="输入内容")
            ui.button("添加", on_click=lambda: _add_todo(todo, todo_input)).props("outline")
            ui.button("刷新列表", on_click=lambda: _fetch_todos(todo, todo_container)).props("flat")

    await _fetch_todos(todo, todo_container)


# ---- 事件处理器 ----
async def _update_counter(counter: CounterStore, delta: int) -> None:
    await counter.update({"count": counter.count + delta})


async def _reset_counter(counter: CounterStore) -> None:
    await counter.reset(refresh=True)


async def _fetch_todos(todo: TodoStore, container: ui.column) -> None:
    await todo.fetch_todos()  # 声明式方法：自动管理 is_loading、注入参数、result_field 写入状态
    print(f"[DEMO] fetch_todos 完成，todos 现有 {len(todo.todos)} 条", flush=True)
    container.clear()
    with container:
        for item in todo.todos or []:
            with ui.row().classes("items-center"):
                ui.icon("check_circle").classes("text-green-500")
                ui.label(item.get("text", ""))
    print(f"[DEMO] 渲染完成，共 {len(todo.todos)} 个 Todo 项", flush=True)


async def _add_todo(todo: TodoStore, todo_input: ui.input) -> None:
    text = str(todo_input.value or "").strip()
    if not text:
        ui.notify("请输入内容", type="warning")
        return
    await todo.add_todo(text=text)
    todo_input.value = ""
    ui.notify(f"已新增: {text}", type="positive")


if __name__ in {"__main__", "__mp_main__"}:
    # storage_secret 是使用 app.storage 持久化的必要条件
    ui.run(host="127.0.0.1", port=8080, storage_secret="pystores-demo-secret")
