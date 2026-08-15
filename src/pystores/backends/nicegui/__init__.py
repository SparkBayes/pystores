"""pystores.backends.nicegui - NiceGUI 后端适配器

一键配置: configure(service=...) 将 NiceGUI 上下文与存储注入 BaseStore。
"""

from pystores.backends.nicegui.binding import NiceGUIStore
from pystores.backends.nicegui.bridge import Bridge
from pystores.backends.nicegui.context import NiceGUIContext
from pystores.backends.nicegui.storage import NiceGUIStorage
from pystores.core.base import BaseStore, ServiceExecutor

__all__ = [
    "Bridge",
    "NiceGUIContext",
    "NiceGUIStorage",
    "NiceGUIStore",
    "configure",
]


def configure(*, service: ServiceExecutor | None = None) -> None:
    """注入 NiceGUI 后端适配器到 BaseStore

    调用后，BaseStore 的所有子类使用 NiceGUI 上下文与存储：
    - 上下文: 基于 ui.context / app.storage 生成 tab/browser/client 隔离 ID
    - 存储: 基于 app.storage 持久化 _state_storage_field 声明的字段

    Args:
        service: 服务执行器（可选）。声明式 Action 需要注入，由用户实现。
    """
    BaseStore.configure(
        context=NiceGUIContext(),
        storage=NiceGUIStorage(),
        service=service,
    )
