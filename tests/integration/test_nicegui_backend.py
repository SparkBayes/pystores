"""NiceGUI 后端集成测试 - 验证响应式绑定、后端注入与基本功能。

本测试需要安装 nicegui（未安装时自动跳过），在 CI 的 NiceGUI 版本矩阵中运行。
"""

from typing import ClassVar

import pytest
from nicegui.binding import BindableProperty, bindable_dataclass

pytest.importorskip("nicegui")

from pystores import NiceGUIStore, nicegui_backend
from pystores.core.base import BaseStore


@bindable_dataclass
class Todo(NiceGUIStore):
    _state_name: ClassVar[str] = "it_todo"
    title: str = ""
    done: bool = False


class TestNiceGUIStore:
    def test_fields_are_bindable(self):
        """业务字段必须是 BindableProperty（响应式绑定基础）"""
        assert isinstance(Todo.__dict__.get("title"), BindableProperty)
        assert isinstance(Todo.__dict__.get("done"), BindableProperty)

    def test_backend_injection(self):
        """configure 注入 NiceGUI 上下文与存储"""
        nicegui_backend()
        assert BaseStore._context.__class__.__name__ == "NiceGUIContext"
        assert BaseStore._storage.__class__.__name__ == "NiceGUIStorage"

    async def test_get_and_update(self):
        """实例获取与状态更新"""
        nicegui_backend()
        todo = await Todo.get_instance()
        await todo.update({"title": "写 CI"})
        assert todo.title == "写 CI"

    async def test_lifecycle_dispose(self):
        """生命周期销毁"""
        nicegui_backend()
        todo = await Todo.get_instance()
        assert await Todo.dispose_instance()
        assert await Todo.get_instance() is not todo
