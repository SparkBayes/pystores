"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 自定义 Provider 示例 - 三协议全替换（Context/Storage/Service），零 UI 框架依赖

运行: python examples/05_custom_providers/main.py
"""

import asyncio
import json
from dataclasses import field
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from pystores import BaseStore
from pystores.core.base import ServiceExecutor
from pystores.core.context import ContextProvider
from pystores.core.storage import (
    StorageProvider,
    dict_to_state,
    generate_storage_key,
    state_to_dict,
)
from pystores.result import Result


# ========== 自定义 ContextProvider：基于 session_id 的隔离 ==========
class SessionContext(ContextProvider):
    """为任意会话分配稳定隔离 ID - 演示无需依赖 UI 框架的上下文"""

    def __init__(self, session_id: str) -> None:
        self._sid = session_id

    def _ids(self) -> Dict[str, str]:
        return {
            "tab": f"tab_{self._sid}",
            "browser": f"browser_{self._sid}",
            "client": f"client_{self._sid}",
        }

    def get_tab_id(self) -> str:
        return self._ids()["tab"]

    def get_browser_id(self) -> str:
        return self._ids()["browser"]

    def get_client_id(self) -> str:
        return self._ids()["client"]

    def get_context_id(self, isolation_level: str) -> str:
        return self._ids().get(isolation_level, "")

    def get_ui_context(self) -> Any | None:
        return None

    def get_all_contexts(self) -> Dict[str, str]:
        return self._ids()

    def apply_to_instance(self, instance: Any, isolation_level: str) -> None:
        for name, value in self._ids().items():
            setattr(instance, f"_{name}_id", value)
        instance._context_id = self.get_context_id(isolation_level)

    def get_instance_specific_context_id(self, instance: Any, isolation_level: str) -> str:
        return getattr(instance, f"_{isolation_level}_id", "")

    def get_instance_primary_context_id(self, instance: Any) -> str:
        return getattr(instance, "_context_id", "")


# ========== 自定义 StorageProvider：JSON 文件持久化 ==========
class FileStorage(StorageProvider):
    """将状态字段持久化到 JSON 文件 - 演示存储介质可替换"""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._data: Dict[str, Dict[str, Any]] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def save(self, state: Any) -> None:
        mapping = getattr(state.__class__, "_state_storage_field", {})
        if not mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        state_dict = await state_to_dict(state)
        for field_name, storage_type in mapping.items():
            if field_name in state_dict:
                key = generate_storage_key(state_name, field_name)
                self._data.setdefault(storage_type, {})[key] = state_dict[field_name]
        self._flush()

    async def load(self, state: Any) -> None:
        mapping = getattr(state.__class__, "_state_storage_field", {})
        if not mapping:
            return
        state_name = getattr(state.__class__, "_state_name", "")
        restored: Dict[str, Any] = {}
        for field_name, storage_type in mapping.items():
            key = generate_storage_key(state_name, field_name)
            bucket = self._data.get(storage_type, {})
            if key in bucket:
                restored[field_name] = bucket[key]
        if restored:
            await dict_to_state(state, restored)

    async def clear(self, state: Any) -> None:
        mapping = getattr(state.__class__, "_state_storage_field", {})
        state_name = getattr(state.__class__, "_state_name", "")
        for field_name, storage_type in mapping.items():
            key = generate_storage_key(state_name, field_name)
            bucket = self._data.get(storage_type, {})
            if key in bucket:
                del bucket[key]
        self._flush()


# ========== 自定义 ServiceExecutor：库存业务 ==========
class InventoryService(ServiceExecutor):
    def __init__(self) -> None:
        self._items: Dict[str, int] = {"pen": 10, "book": 5}

    async def execute(self, service_name: str, method_name: str, params: Dict[str, Any]) -> Result:
        if method_name == "stock":
            return Result.create_success(self._items)
        if method_name == "deduct":
            name = params.get("name")
            if name in self._items and self._items[name] > 0:
                self._items[name] -= 1
                return Result.create_success({"name": name, "left": self._items[name]})
            return Result.create_failure("OutOfStock", f"{name} 库存不足")
        return Result.create_failure("NotFound", f"未知方法: {method_name}")


# ========== 注入三协议（全部自定义） ==========
STORAGE_FILE = "/tmp/pystores-05-storage.json"
BaseStore.configure(
    context=SessionContext("demo-session"),
    storage=FileStorage(STORAGE_FILE),
    service=InventoryService(),
)


# ========== 领域状态：纯核心 ==========
class CartStore(BaseStore):
    """购物车 - 持久化 + 声明式 Action + 跨状态读取"""

    _state_name: ClassVar[str] = "cart"
    _state_storage_field: ClassVar[Dict[str, str]] = {"items": "user"}
    _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
        "check_stock": {
            "service_name": "inventory",
            "method_name": "stock",
            "result_field": "stock",
            "requires_token": False,
        },
        "buy": {
            "service_name": "inventory",
            "method_name": "deduct",
            "params_mapping": {"name": "name"},
            "requires_token": False,
        },
    }
    items: List[str] = field(default_factory=list)
    stock: Dict[str, int] = field(default_factory=dict)


async def main() -> None:
    cart = await CartStore.get_instance()
    print("=" * 52)
    print(" pystores · 自定义 Provider（三协议全替换）")
    print("=" * 52)
    print(f" ContextProvider : {type(cart.__class__._context).__name__} (SessionContext)")
    print(f" StorageProvider : {type(cart.__class__._storage).__name__} (FileStorage)")
    print(f" ServiceExecutor : {type(cart.__class__._service).__name__} (InventoryService)")
    print("-" * 52)
    print(f" 隔离 ID         : {cart._client_id}")

    # 加购物车（触发持久化到 JSON 文件）
    await cart.update({"items": ["pen"]})

    # 声明式 Action：查库存
    await cart.check_stock()
    print(f" 库存           : {cart.stock}")

    # 声明式 Action：购买（扣库存）
    await cart.buy(name="pen")
    await cart.check_stock()
    print(f" 购买 pen 后库存 : {cart.stock}")

    print(f" 购物车(已持久化) : {cart.items}")

    # 演示文件持久化：销毁实例 → 从 JSON 恢复
    print("-" * 52)
    print(" 销毁实例 → 从 JSON 文件恢复状态：")
    await CartStore.dispose_instance()
    cart2 = await CartStore.get_instance()
    print(f" 恢复的购物车    : {cart2.items}")

    print("-" * 52)
    print(" ✅ 三个协议全部可替换，核心层不感知具体实现")


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
