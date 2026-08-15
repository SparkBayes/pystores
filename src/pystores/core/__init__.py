"""pystores.core - 框架无关的状态管理核心

本包零第三方 UI 依赖，通过 ContextProvider / StorageProvider / ServiceExecutor
三个协议与任意服务端 UI 框架解耦。未配置后端时使用内置内存实现，可独立运行。
"""

from pystores.core.action import ActionExecutor
from pystores.core.base import BaseStore, ServiceExecutor
from pystores.core.context import ContextProvider, MemoryContext
from pystores.core.hook import StateHookManager
from pystores.core.manager import StoreManager, store_manager
from pystores.core.storage import MemoryStorage, StorageProvider

__all__ = [
    "ActionExecutor",
    "BaseStore",
    "ContextProvider",
    "MemoryContext",
    "MemoryStorage",
    "ServiceExecutor",
    "StateHookManager",
    "StorageProvider",
    "StoreManager",
    "store_manager",
]
