"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: NiceGUI 响应式状态基类 - bindable_dataclass 响应式绑定 + PyWebView 桥接
"""

from typing import Any, ClassVar, Dict, Optional

from nicegui.binding import bindable_dataclass

from pystores.backends.nicegui.bridge import Bridge
from pystores.core.base import BaseStore
from pystores.result import Result


@bindable_dataclass
class NiceGUIStore(BaseStore):
    """NiceGUI 响应式状态基类

    与 BaseStore 的区别：
    1. 启用 nicegui 的响应式绑定，状态属性变化自动同步到绑定的 UI 组件
    2. 提供 PyWebView 桌面客户端桥接方法（execute_client_function / check_ready）

    纯逻辑 / 测试场景可继续使用 BaseStore（无 UI 依赖）。
    """

    # PyWebView 桥接单例（类级共享）
    _bridge: ClassVar[Optional[Bridge]] = None

    @classmethod
    def _get_bridge(cls) -> Bridge:
        """获取桥接实例（类级单例）"""
        if cls._bridge is None:
            cls._bridge = Bridge()
        return cls._bridge

    async def execute_client_function(
        self,
        function_name: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Result:
        """便捷方法：调用 PyWebView 客户端 JS 函数（桌面客户端场景）"""
        return await self._get_bridge().execute_client_function(function_name, data, timeout)

    async def check_ready(self) -> Result:
        """便捷方法：检查 PyWebView 是否就绪（桌面客户端场景）"""
        return await self._get_bridge().check_ready()
