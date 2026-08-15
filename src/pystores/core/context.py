"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 上下文提供者协议 - 抽象 tab/browser/client 三级隔离上下文的来源（框架无关）
"""

from typing import Any, Dict, Protocol


class ContextProvider(Protocol):
    """上下文提供者协议 - 负责生成三级隔离 ID 与 UI 上下文

    服务端 UI 框架（NiceGUI/Streamlit 等）各自持有客户端连接的 ID 体系，
    通过实现本协议注入 BaseStore，核心层不感知具体框架。

    隔离级别说明:
    - tab: 标签页级，每个浏览器标签页独立
    - browser: 浏览器级，同浏览器所有标签页共享
    - client: 客户端级，基于连接，断开后仍可访问
    """

    def get_tab_id(self) -> str:
        """生成标签页级 ID"""
        ...

    def get_browser_id(self) -> str:
        """生成浏览器级 ID"""
        ...

    def get_client_id(self) -> str:
        """生成客户端级 ID"""
        ...

    def get_context_id(self, isolation_level: str) -> str:
        """根据隔离级别生成对应 context_id"""
        ...

    def get_ui_context(self) -> Any | None:
        """获取当前 UI 上下文（用于副作用在稳定 slot 中执行），无则返回 None"""
        ...

    def get_all_contexts(self) -> Dict[str, str]:
        """获取当前环境的所有上下文 ID（tab/browser/client）"""
        ...

    def apply_to_instance(self, instance: Any, isolation_level: str) -> None:
        """为实例设置所有上下文 ID 与主 context_id"""
        ...

    def get_instance_specific_context_id(self, instance: Any, isolation_level: str) -> str:
        """根据隔离级别获取实例的特定上下文 ID"""
        ...

    def get_instance_primary_context_id(self, instance: Any) -> str:
        """获取实例的主上下文 ID"""
        ...


class MemoryContext:
    """内存上下文 - 无 UI 框架时的默认实现

    所有 ID 返回空字符串，使核心可在无连接体系的环境（CLI、测试）单实例运行。
    """

    def get_tab_id(self) -> str:
        return ""

    def get_browser_id(self) -> str:
        return ""

    def get_client_id(self) -> str:
        return ""

    def get_context_id(self, isolation_level: str) -> str:
        return ""

    def get_ui_context(self) -> Any | None:
        return None

    def get_all_contexts(self) -> Dict[str, str]:
        return {"tab": "", "browser": "", "client": ""}

    def apply_to_instance(self, instance: Any, isolation_level: str) -> None:
        for name in ("_tab_id", "_browser_id", "_client_id", "_context_id"):
            setattr(instance, name, "")

    def get_instance_specific_context_id(self, instance: Any, isolation_level: str) -> str:
        return ""

    def get_instance_primary_context_id(self, instance: Any) -> str:
        return ""
