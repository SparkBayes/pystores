"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: NiceGUI 存储提供者 - 实现 StorageProvider，基于 app.storage 的 tab/user/client 三级存储
"""

import logging
from typing import Any

from nicegui import app

from pystores.core.storage import dict_to_state, generate_storage_key, state_to_dict

logger = logging.getLogger(__name__)


class NiceGUIStorage:
    """NiceGUI 存储提供者 - 使用 app.storage 持久化状态字段

    存储类型对应:
    - tab: app.storage.tab（标签页级，刷新保留）
    - user: app.storage.user（浏览器级，跨标签页共享，重启保留）
    - client: app.storage.client（连接级，刷新丢失）
    """

    async def save(self, state: Any) -> None:
        """将声明了 _state_storage_field 的字段写入对应存储"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        if not state_name:
            raise ValueError(f"状态类 {state.__class__.__name__} 未配置 _state_name 属性")

        state_dict = await state_to_dict(state)
        for field_name, storage_type in field_mapping.items():
            if field_name not in state_dict:
                continue
            storage_key = generate_storage_key(state_name, field_name)
            try:
                if hasattr(app, "storage") and hasattr(app.storage, storage_type):
                    storage = getattr(app.storage, storage_type)
                    storage[storage_key] = state_dict[field_name]
                    logger.debug(f"保存字段到{storage_type}存储: {storage_key}")
            except Exception as e:
                logger.warning(f"保存到{storage_type}存储失败: {e!s}")

    async def load(self, state: Any) -> None:
        """从存储恢复已持久化的字段"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        if not state_name:
            raise ValueError(f"状态类 {state.__class__.__name__} 未配置 _state_name 属性")

        state_dict: dict[str, Any] = {}
        for field_name, storage_type in field_mapping.items():
            storage_key = generate_storage_key(state_name, field_name)
            try:
                if hasattr(app, "storage") and hasattr(app.storage, storage_type):
                    storage = getattr(app.storage, storage_type)
                    if storage_key in storage:
                        state_dict[field_name] = storage.get(storage_key)
            except Exception as e:
                logger.warning(f"从{storage_type}存储加载失败: {e!s}")
                continue

        if state_dict:
            await dict_to_state(state, state_dict)

    async def clear(self, state: Any) -> None:
        """清理状态在存储中的所有字段（登出等场景）"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        if not state_name:
            return

        for field_name, storage_type in field_mapping.items():
            storage_key = generate_storage_key(state_name, field_name)
            try:
                if hasattr(app, "storage") and hasattr(app.storage, storage_type):
                    storage = getattr(app.storage, storage_type)
                    if storage_key in storage:
                        del storage[storage_key]
                        logger.debug(f"清理存储字段: {storage_key}")
            except Exception as e:
                logger.warning(f"清理存储字段失败 {storage_key}: {e!s}")
