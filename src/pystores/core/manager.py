"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 状态管理器 - 提供状态类注册与统一的状态实例访问接口（框架无关）
"""

import logging
from typing import Any, Iterable, Type

from pystores.core.base import BaseStore
from pystores.result import handle_exceptions

logger = logging.getLogger(__name__)


class StoreManager:
    """状态管理器 - 统一的状态类注册与实例访问"""

    def __init__(self) -> None:
        # 状态类注册表: {state_name: state_class}
        self._state_classes: dict[str, Type[BaseStore]] = {}

    def register(self, *state_classes: Type[BaseStore]) -> None:
        """注册一个或多个状态类

        Args:
            state_classes: 状态类（需设置 _state_name 类属性）
        """
        for state_cls in state_classes:
            state_name = getattr(state_cls, "_state_name", "")
            if not state_name:
                raise ValueError(f"状态类 {state_cls.__name__} 必须设置 _state_name 类属性")
            self._state_classes[state_name] = state_cls
            logger.debug(f"注册状态类: {state_name} -> {state_cls.__name__}")

    def register_all(self, state_classes: Iterable[Type[BaseStore]]) -> None:
        """批量注册状态类"""
        self.register(*tuple(state_classes))

    def get_state_class(self, state_name: str) -> Type[BaseStore]:
        """获取状态类，未注册则抛 ValueError"""
        if state_name not in self._state_classes:
            raise ValueError(f"无效的状态名称: {state_name}")
        return self._state_classes[state_name]

    @handle_exceptions("获取状态实例")
    async def get(self, state_name: str) -> Any:
        """获取（或创建）当前上下文的状态实例"""
        state_cls = self.get_state_class(state_name)
        return await state_cls.get_instance()


# 全局单例 - 模块导入后立即可用
store_manager = StoreManager()
