"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 存储提供者协议与通用序列化 - 抽象状态持久化介质，提供框架无关的序列化工具
"""

import logging
from typing import Any, Dict, Protocol

logger = logging.getLogger(__name__)


class StorageProvider(Protocol):
    """存储提供者协议 - 负责状态字段的持久化读写

    存储键格式: {state_name}.{field_name}，例如 "user.refresh_token"。
    存储类型（tab/user/client）由状态类 `_state_storage_field` 声明。
    """

    async def save(self, state: Any) -> None:
        """将状态实例中声明了 `_state_storage_field` 的字段写入存储"""
        ...

    async def load(self, state: Any) -> None:
        """从存储加载已持久化的字段并更新到状态实例"""
        ...

    async def clear(self, state: Any) -> None:
        """清理状态实例在存储中的所有字段（登出等场景）"""
        ...


class MemoryStorage:
    """内存存储 - 无 UI 框架时的默认实现（进程内 dict）

    数据存于类属性 _data: {storage_type: {key: value}}
    """

    _data: Dict[str, Dict[str, Any]] = {}

    async def save(self, state: Any) -> None:
        """将声明了 _state_storage_field 的字段写入内存"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        if not state_name:
            return

        state_dict = await state_to_dict(state)
        for field_name, storage_type in field_mapping.items():
            if field_name in state_dict:
                key = generate_storage_key(state_name, field_name)
                self._data.setdefault(storage_type, {})[key] = state_dict[field_name]

    async def load(self, state: Any) -> None:
        """从内存恢复已持久化字段"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        if not state_name:
            return

        state_dict: Dict[str, Any] = {}
        for field_name, storage_type in field_mapping.items():
            key = generate_storage_key(state_name, field_name)
            bucket = self._data.get(storage_type, {})
            if key in bucket:
                state_dict[field_name] = bucket[key]
        if state_dict:
            await dict_to_state(state, state_dict)

    async def clear(self, state: Any) -> None:
        """清理状态在内存中的所有字段"""
        field_mapping = getattr(state.__class__, "_state_storage_field", {})
        if not field_mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")

        for field_name, storage_type in field_mapping.items():
            key = generate_storage_key(state_name, field_name)
            bucket = self._data.get(storage_type, {})
            if key in bucket:
                del bucket[key]


def generate_storage_key(state_name: str, field_name: str) -> str:
    """生成存储键名"""
    return f"{state_name}.{field_name}"


async def state_to_dict(state: Any) -> Dict[str, Any]:
    """将状态实例转换为可序列化字典（框架无关）

    规则:
    - 基本类型(str/int/float/bool/None): 直接存储
    - 列表/元组: 仅保留基本类型元素，复杂元素转为字符串
    - 字典: 键转字符串，值保持基本类型，复杂值转为字符串
    - 其他对象: 转换为字符串
    """
    data: Dict[str, Any] = {}
    annotations = getattr(state.__class__, "__annotations__", {})

    for key in annotations:
        if key.startswith("_") or key == "refresh_at":
            continue
        if not hasattr(state, key):
            continue

        value = getattr(state, key)
        if isinstance(value, (str, int, float, bool, type(None))):
            data[key] = value
        elif isinstance(value, (list, tuple)):
            data[key] = [
                item if isinstance(item, (str, int, float, bool, type(None))) else str(item)
                for item in value
            ]
        elif isinstance(value, dict):
            data[key] = {
                str(k): v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
                for k, v in value.items()
            }
        else:
            try:
                data[key] = str(value)
            except Exception as e:
                logger.warning(f"无法转换属性 {key} 为字符串: {e}")
                data[key] = f"<无法序列化的对象: {type(value).__name__}>"

    return data


async def dict_to_state(state: Any, data: Dict[str, Any]) -> Any:
    """从字典恢复状态属性（框架无关），带简单类型转换"""
    if not data:
        return state

    annotations = getattr(state.__class__, "__annotations__", {})
    updated_keys: list[str] = []

    for key, value in data.items():
        if key.startswith("_") or key == "refresh_at":
            continue
        if not hasattr(state, key) or callable(getattr(state, key)):
            continue

        attr_type = annotations.get(key)
        if attr_type is not None:
            value = _coerce_value(value, attr_type)
            if value is _COERCE_FAILED:
                continue

        setattr(state, key, value)
        updated_keys.append(key)

    if updated_keys:
        logger.debug(f"从字典初始化状态: {', '.join(updated_keys)}")
    return state


# 类型转换失败的哨兵
_COERCE_FAILED = object()


def _coerce_value(value: Any, attr_type: Any) -> Any:
    """按注解类型做简单强制转换，失败返回 _COERCE_FAILED"""
    if attr_type is bool and not isinstance(value, bool):
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "y")
        return bool(value)
    if attr_type is int and not isinstance(value, int):
        try:
            return int(value)
        except (ValueError, TypeError):
            return _COERCE_FAILED
    if attr_type is float and not isinstance(value, float):
        try:
            return float(value)
        except (ValueError, TypeError):
            return _COERCE_FAILED
    if attr_type is str and not isinstance(value, str):
        return str(value)
    return value
