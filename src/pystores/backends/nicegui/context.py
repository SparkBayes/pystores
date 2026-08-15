"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: NiceGUI 上下文提供者 - 基于 ui.context/app.storage 生成三级隔离 ID
"""

from typing import Any, Dict

from nicegui import app, ui


class NiceGUIContext:
    """NiceGUI 上下文提供者 - 三级隔离 ID 生成

    - tab: 基于 ui.context.client.tab_id（标签页级）
    - browser: 基于 app.storage.browser["id"]（浏览器级）
    - client: 基于 ui.context.client.id（客户端连接级）
    """

    def get_tab_id(self) -> str:
        """生成标签页级 ID"""
        try:
            if hasattr(ui, "context") and hasattr(ui.context, "client"):
                tab_id = getattr(ui.context.client, "tab_id", None)
                return f"tab_{tab_id}" if tab_id else ""
        except RuntimeError:
            # NiceGUI 2.x 在无 UI 上下文（测试/后台）时抛 RuntimeError
            pass
        return ""

    def get_browser_id(self) -> str:
        """生成浏览器级 ID"""
        try:
            if hasattr(app, "storage") and hasattr(app.storage, "browser"):
                browser_id = app.storage.browser.get("id")
                return f"browser_{browser_id}" if browser_id else ""
        except RuntimeError:
            # UI 上下文不存在时返回空串
            pass
        return ""

    def get_client_id(self) -> str:
        """生成客户端级 ID"""
        try:
            if hasattr(ui, "context") and hasattr(ui.context, "client"):
                client_id = getattr(ui.context.client, "id", None)
                return f"client_{client_id}" if client_id else ""
        except RuntimeError:
            # NiceGUI 2.x 在无 UI 上下文（测试/后台）时抛 RuntimeError
            pass
        return ""

    def get_context_id(self, isolation_level: str) -> str:
        """根据隔离级别生成对应 context_id"""
        if isolation_level == "tab":
            return self.get_tab_id()
        if isolation_level == "browser":
            return self.get_browser_id()
        if isolation_level == "client":
            return self.get_client_id()
        return ""

    def get_ui_context(self) -> Any | None:
        """获取当前 UI 上下文（NiceGUI Slot），无则返回 None"""
        try:
            return ui.context.slot
        except (ImportError, RuntimeError):
            return None

    def get_all_contexts(self) -> Dict[str, str]:
        """获取当前环境的所有上下文 ID"""
        return {
            "tab": self.get_tab_id(),
            "browser": self.get_browser_id(),
            "client": self.get_client_id(),
        }

    def apply_to_instance(self, instance: Any, isolation_level: str) -> None:
        """为实例设置所有上下文 ID 与主 context_id"""
        all_contexts = self.get_all_contexts()
        instance._tab_id = all_contexts.get("tab", "")
        instance._browser_id = all_contexts.get("browser", "")
        instance._client_id = all_contexts.get("client", "")
        instance._context_id = all_contexts.get(isolation_level, "")

    def get_instance_specific_context_id(self, instance: Any, isolation_level: str) -> str:
        """根据隔离级别获取实例的特定上下文 ID"""
        if isolation_level == "tab":
            return getattr(instance, "_tab_id", "")
        if isolation_level == "browser":
            return getattr(instance, "_browser_id", "")
        if isolation_level == "client":
            return getattr(instance, "_client_id", "")
        return ""

    def get_instance_primary_context_id(self, instance: Any) -> str:
        """获取实例的主上下文 ID"""
        return getattr(instance, "_context_id", "")

    def get_instance_context_info(self, instance: Any) -> Dict[str, str]:
        """获取实例的完整上下文信息（context_id/tab_id/browser_id/client_id）"""
        return {
            "context_id": getattr(instance, "_context_id", ""),
            "tab_id": getattr(instance, "_tab_id", ""),
            "browser_id": getattr(instance, "_browser_id", ""),
            "client_id": getattr(instance, "_client_id", ""),
        }
