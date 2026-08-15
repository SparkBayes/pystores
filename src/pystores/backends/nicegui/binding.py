"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: NiceGUI 响应式状态基类 - 继承 BaseStore 并启用 nicegui 的 bindable_dataclass 响应式绑定
"""

from nicegui.binding import bindable_dataclass

from pystores.core.base import BaseStore


@bindable_dataclass
class NiceGUIStore(BaseStore):
    """NiceGUI 响应式状态基类

    与 BaseStore 的区别：启用 nicegui 的响应式绑定，状态属性变化会自动同步到
    绑定的 UI 组件（ui.label().bind_text_from(...) 等）。

    纯逻辑 / 测试场景可继续使用 BaseStore（无 UI 依赖）。
    """
