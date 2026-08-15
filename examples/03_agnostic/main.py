"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: pystores 框架无关验证 - 纯核心 CLI 应用（零 NiceGUI 依赖），证明核心可脱钩

运行: python examples/03_agnostic/main.py
"""

import asyncio
from dataclasses import field
from typing import Any, ClassVar, Dict, List

from pystores import BaseStore
from pystores.core.base import ServiceExecutor
from pystores.result import Result


# ========== 自定义服务执行器（纯 Python，模拟文件存储服务） ==========
class FileTodoService(ServiceExecutor):
    """实现 ServiceExecutor 协议 - 演示声明式 Action 可对接任意服务层"""

    def __init__(self) -> None:
        self._store: List[Dict[str, Any]] = []

    async def execute(self, service_name: str, method_name: str, params: Dict[str, Any]) -> Result:
        if method_name == "list":
            return Result.create_success(self._store)
        if method_name == "create":
            item = {
                "id": len(self._store) + 1,
                "text": params.get("text", ""),
                "done": False,
            }
            self._store.append(item)
            return Result.create_success(item)
        if method_name == "toggle":
            for item in self._store:
                if item["id"] == params.get("id"):
                    item["done"] = not item["done"]
                    return Result.create_success(item)
            return Result.create_failure("NotFound", f"todo {params.get('id')} 不存在")
        return Result.create_failure("Unknown", f"未知方法: {method_name}")


# 注入服务执行器（context/storage 保持默认的内存实现）
BaseStore.configure(service=FileTodoService())


# ========== 领域状态：直接继承 BaseStore（非 NiceGUIStore） ==========
class TodoStore(BaseStore):
    """待办状态 - 不依赖任何 UI 框架，纯核心层"""

    _state_name: ClassVar[str] = "todo"
    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "fetch_todos": {
            "service_name": "todo",
            "method_name": "list",
            "result_field": "todos",  # 将服务返回的列表写入 todos 字段
            "requires_token": False,
        },
        "add_todo": {
            "service_name": "todo",
            "method_name": "create",
            "params_mapping": {"text": "text"},
            "requires_token": False,
        },
        "toggle_todo": {
            "service_name": "todo",
            "method_name": "toggle",
            "params_mapping": {"id": "id"},
            "requires_token": False,
        },
    }
    todos: List[Dict[str, Any]] = field(default_factory=list)


def _render(todos: List[Dict[str, Any]]) -> None:
    if not todos:
        print("  （暂无待办）")
        return
    for item in todos:
        mark = "✓" if item["done"] else "☐"
        print(f"  [{mark}] #{item['id']} {item['text']}")


async def main() -> None:
    store = await TodoStore.get_instance()

    print("=" * 46)
    print(" pystores · 框架无关验证（无 NiceGUI 依赖）")
    print("=" * 46)
    print(f" 状态基类       : {store.__class__.__name__}")
    print(f" 上下文提供者   : {type(store.__class__._context).__name__}")
    print(f" 存储提供者     : {type(store.__class__._storage).__name__}")
    print(f" 服务执行器     : {type(store.__class__._service).__name__}")
    print("-" * 46)

    # 声明式 Action：新增两条待办
    await store.add_todo(text="学习核心层三协议")
    await store.add_todo(text="验证框架无关")
    await store.fetch_todos()
    print("新增两条待办后：")
    _render(store.todos)

    # 切换 #1 完成状态
    await store.toggle_todo(id=1)
    await store.fetch_todos()
    print("\n切换 #1 为完成后：")
    _render(store.todos)

    print("-" * 46)
    print(" ✅ 核心层不依赖任何 UI 框架，声明式 Action 完整可用")
    print(" ✅ 未来接入 Streamlit / Reflex 等框架 = 新增一个后端")


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
