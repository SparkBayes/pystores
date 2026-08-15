"""pystores - 服务端 UI 状态管理

面向服务端 UI 框架的结构化状态管理库，解决多用户状态隔离、声明式服务调用、
响应式副作用三大痛点。

- 核心（pystores.core）：框架无关，零第三方 UI 依赖，可独立运行
- 后端（pystores.backends.nicegui）：NiceGUI 响应式绑定与持久化适配
"""

from pystores.core.base import BaseStore, ServiceExecutor
from pystores.core.context import ContextProvider, MemoryContext
from pystores.core.manager import StoreManager, store_manager
from pystores.core.storage import MemoryStorage, StorageProvider
from pystores.result import Result, handle_exceptions

try:
    from pystores.backends.nicegui import NiceGUIStore
    from pystores.backends.nicegui import configure as nicegui_backend

    _HAS_NICEGUI = True
except ImportError:
    NiceGUIStore = None  # type: ignore[assignment, misc]
    nicegui_backend = None  # type: ignore[assignment]
    _HAS_NICEGUI = False

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BaseStore",
    "ContextProvider",
    "handle_exceptions",
    "MemoryContext",
    "MemoryStorage",
    "NiceGUIStore",
    "nicegui_backend",
    "Result",
    "ServiceExecutor",
    "StorageProvider",
    "StoreManager",
    "store_manager",
]
