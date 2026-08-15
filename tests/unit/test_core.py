"""核心状态管理功能单元测试（零第三方 UI 依赖）"""

from dataclasses import field
from typing import Any, ClassVar, Dict, List

import pytest

from pystores.core.base import BaseStore
from pystores.core.manager import StoreManager, store_manager
from pystores.core.storage import MemoryStorage
from pystores.result import Result


class FakeContext:
    """可配置 client_id 的上下文 - 用于测试多用户隔离"""

    def __init__(self, client_id: str = "c1"):
        self._cid = client_id

    def get_tab_id(self) -> str:
        return f"tab_{self._cid}"

    def get_browser_id(self) -> str:
        return f"browser_{self._cid}"

    def get_client_id(self) -> str:
        return f"client_{self._cid}"

    def get_context_id(self, isolation_level: str) -> str:
        return {
            "tab": self.get_tab_id(),
            "browser": self.get_browser_id(),
            "client": self.get_client_id(),
        }[isolation_level]

    def get_ui_context(self) -> Any | None:
        return None

    def get_all_contexts(self) -> Dict[str, str]:
        return {
            "tab": self.get_tab_id(),
            "browser": self.get_browser_id(),
            "client": self.get_client_id(),
        }

    def apply_to_instance(self, instance: Any, isolation_level: str) -> None:
        instance._tab_id = self.get_tab_id()
        instance._browser_id = self.get_browser_id()
        instance._client_id = self.get_client_id()
        instance._context_id = self.get_context_id(isolation_level)

    def get_instance_specific_context_id(self, instance: Any, isolation_level: str) -> str:
        return getattr(
            instance,
            {"tab": "_tab_id", "browser": "_browser_id", "client": "_client_id"}[isolation_level],
        )

    def get_instance_primary_context_id(self, instance: Any) -> str:
        return getattr(instance, "_context_id", "")

    def get_instance_context_info(self, instance: Any) -> Dict[str, str]:
        return {
            "context_id": getattr(instance, "_context_id", ""),
            "tab_id": getattr(instance, "_tab_id", ""),
            "browser_id": getattr(instance, "_browser_id", ""),
            "client_id": getattr(instance, "_client_id", ""),
        }


# 可复用的测试状态类
class CounterStore(BaseStore):
    _state_name: ClassVar[str] = "test_counter"
    count: int = 0
    label: str = "counter"


class TestInstanceLifecycle:
    async def test_get_instance_creates_once(self):
        a = await CounterStore.get_instance()
        b = await CounterStore.get_instance()
        assert a is b

    async def test_get_instance_with_context(self):
        ctx = FakeContext("u1")
        BaseStore.configure(context=ctx)
        instance = await CounterStore.get_instance()
        assert instance._client_id == "client_u1"
        assert instance._context_id == "client_u1"

    async def test_multi_user_isolation(self):
        BaseStore.configure(context=FakeContext("user_a"))
        a = await CounterStore.get_instance()
        BaseStore.configure(context=FakeContext("user_b"))
        b = await CounterStore.get_instance()
        assert a is not b
        assert a._client_id == "client_user_a"
        assert b._client_id == "client_user_b"

    async def test_dispose_instance(self):
        instance = await CounterStore.get_instance()
        assert await CounterStore.dispose_instance()
        assert await CounterStore.get_instance() is not instance

    async def test_get_instance_context_info(self):
        """get_instance_context_info 返回实例的完整上下文信息"""
        BaseStore.configure(context=FakeContext("u1"))
        instance = await CounterStore.get_instance()
        info = BaseStore._context.get_instance_context_info(instance)
        assert info == {
            "context_id": "client_u1",
            "tab_id": "tab_u1",
            "browser_id": "browser_u1",
            "client_id": "client_u1",
        }

    async def test_dispose_all_instances(self):
        BaseStore.configure(context=FakeContext("u1"))
        instance = await CounterStore.get_instance()
        assert await instance.dispose_all_instances() >= 1


class MonitoredStore(BaseStore):
    _state_name: ClassVar[str] = "test_monitored"
    count: int = 0
    fired: int = 0

    async def on_count_two(self) -> None:
        """自定义方法 - 由 monitor 触发"""
        self.fired += 1


class TestStateData:
    async def test_update_and_get(self):
        instance = await CounterStore.get_instance()
        await instance.update({"count": 5})
        assert instance.count == 5

    async def test_update_triggers_monitor(self):
        import asyncio

        BaseStore.set_monitors(
            {
                "test_monitored": {
                    "count": {2: [{"state": "test_monitored", "method": "on_count_two"}]}
                }
            }
        )

        instance = await MonitoredStore.get_instance()
        await instance.update({"count": 2})
        # monitor 动作经 asyncio.create_task 异步执行，短暂等待
        await asyncio.sleep(0.05)
        assert instance.fired == 1

        # 非配置值不触发
        await instance.update({"count": 3})
        await asyncio.sleep(0.05)
        assert instance.fired == 1

    async def test_reset(self):
        instance = await CounterStore.get_instance()
        await instance.update({"count": 9, "label": "x"})
        await instance.reset()
        assert instance.count == 0
        assert instance.label == "counter"  # 恢复为声明的默认值

    async def test_update_rejected_when_disposing(self):
        instance = await CounterStore.get_instance()
        instance._is_disposing = True
        result = await instance.update({"count": 1})
        assert result.is_failure()


class TestShareFields:
    class TokenStore(BaseStore):
        _state_name: ClassVar[str] = "test_token"
        _state_share_fields: ClassVar[Dict[str, str]] = {"token": "client"}
        token: str = ""

    class NeedyStore(BaseStore):
        _state_name: ClassVar[str] = "test_needy"
        needs_token: str = ""

    async def test_get_state_value_shared(self):
        BaseStore.configure(context=FakeContext("u1"))
        token = await self.TokenStore.get_instance()
        await token.update({"token": "secret"})

        needy = await self.NeedyStore.get_instance()
        result = await needy.get_state_value("test_token", "token")
        assert result.success
        assert result.data == "secret"

    async def test_get_state_value_blocked_not_shared(self):
        BaseStore.configure(context=FakeContext("u1"))
        needy = await self.NeedyStore.get_instance()
        result = await needy.get_state_value("test_needy", "needs_token")
        assert result.is_failure()
        assert result.code == "NotShareField"


class TestDeclarativeAction:
    class AuthStore(BaseStore):
        _state_name: ClassVar[str] = "test_auth"
        _state_share_fields: ClassVar[Dict[str, str]] = {"token": "client"}
        token: str = "my-token"
        last_result: str = ""

    class OrderStore(BaseStore):
        _state_name: ClassVar[str] = "test_order"
        _auth_state: ClassVar[str] = "test_auth"  # token 来源状态
        _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
            "fetch_orders": {
                "service_name": "order",
                "method_name": "list",
                "params_mapping": {"page": "page", "limit": ("limit", 10)},
                "requires_token": True,
                "refresh": True,
                "additional_updates": {"last_result": "ok"},
            }
        }
        orders: List[Dict[str, Any]] = field(default_factory=list)
        last_result: str = ""

    class FakeService:
        """实现 ServiceExecutor 协议的假服务"""

        def __init__(self):
            self.calls = []

        async def execute(
            self, service_name: str, method_name: str, params: Dict[str, Any]
        ) -> Result:
            self.calls.append((service_name, method_name, params))
            return Result.create_success([{"id": 1}])

    async def test_action_calls_service_with_token(self):
        svc = self.FakeService()
        BaseStore.configure(
            context=FakeContext("u1"),
            service=svc,
        )
        # 先创建 token 来源状态实例
        auth = await self.AuthStore.get_instance()
        await auth.update({"token": "my-token"})

        order = await self.OrderStore.get_instance()
        result = await order.fetch_orders(page=1)

        assert result.success
        assert svc.calls[0][0] == "order"
        assert svc.calls[0][1] == "list"
        # token 被自动注入
        assert svc.calls[0][2]["token"] == "my-token"
        # params_mapping 处理
        assert svc.calls[0][2]["page"] == 1
        assert svc.calls[0][2]["limit"] == 10

    async def test_action_without_service_injected(self):
        BaseStore.configure(context=FakeContext("u1"), service=None)
        order = await self.OrderStore.get_instance()
        result = await order.fetch_orders(page=1)
        assert result.is_failure()
        assert result.code == "NoServiceExecutor"

    class MultiActionStore(BaseStore):
        """多 action 状态类 - 回归测试闭包绑定"""

        _state_name: ClassVar[str] = "test_multi"
        _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
            "list_items": {
                "service_name": "svc",
                "method_name": "list",
                "requires_token": False,
            },
            "create_item": {
                "service_name": "svc",
                "method_name": "create",
                "params_mapping": {"name": "name"},
                "requires_token": False,
            },
        }

    class MultiActionService:
        def __init__(self):
            self.method_calls: List[str] = []

        async def execute(
            self, service_name: str, method_name: str, params: Dict[str, Any]
        ) -> Result:
            self.method_calls.append(method_name)
            return Result.create_success(True)

    async def test_multiple_actions_no_closure_bug(self):
        """每个 action 方法必须调用各自的服务方法（防闭包捕获循环变量的 bug）"""
        svc = self.MultiActionService()
        BaseStore.configure(context=FakeContext("u1"), service=svc)
        store = await self.MultiActionStore.get_instance()

        await store.list_items()
        await store.create_item(name="x")

        assert svc.method_calls == ["list", "create"]

    class ListStore(BaseStore):
        _state_name: ClassVar[str] = "test_list"
        _state_action_methods: ClassVar[Dict[str, Dict[str, Any]]] = {
            "load_items": {
                "service_name": "svc",
                "method_name": "items",
                "result_field": "items",
                "requires_token": False,
            },
        }
        items: List[Dict[str, Any]] = field(default_factory=list)

    class ListService:
        def __init__(self):
            self.items = [{"id": 1, "text": "a"}]

        async def execute(
            self, service_name: str, method_name: str, params: Dict[str, Any]
        ) -> Result:
            return Result.create_success(self.items)

    async def test_action_result_field_writes_list(self):
        """result_field 配置：服务返回的列表数据写入指定状态字段"""
        svc = self.ListService()
        BaseStore.configure(context=FakeContext("u1"), service=svc)
        store = await self.ListStore.get_instance()

        await store.load_items()

        assert store.items == [{"id": 1, "text": "a"}]


class TestMemoryStorage:
    class StoredStore(BaseStore):
        _state_name: ClassVar[str] = "test_stored"
        _state_storage_field: ClassVar[Dict[str, str]] = {"theme": "user"}
        theme: str = "dark"
        dirty: int = 0

    async def test_save_and_load(self):
        BaseStore.configure(context=FakeContext("u1"))
        s1 = await self.StoredStore.get_instance()
        await s1.update({"theme": "light"})

        # 重新创建实例模拟刷新，从存储恢复
        await self.StoredStore.dispose_instance()
        s2 = await self.StoredStore.get_instance()
        await s2.initialize()
        assert s2.theme == "light"

    async def test_clear(self):
        BaseStore.configure(context=FakeContext("u1"))
        s = await self.StoredStore.get_instance()
        await s.update({"theme": "blue"})
        await MemoryStorage().clear(s)
        assert "test_stored.theme" not in MemoryStorage._data.get("user", {})


class TestStoreManager:
    async def test_register_and_get(self):
        mgr = StoreManager()
        mgr.register(CounterStore)
        assert mgr.get_state_class("test_counter") is CounterStore

        instance = await mgr.get("test_counter")
        assert isinstance(instance, CounterStore)

    async def test_register_requires_state_name(self):
        class NoName(BaseStore):
            pass

        mgr = StoreManager()
        with pytest.raises(ValueError):
            mgr.register(NoName)

    def test_global_manager(self):
        assert isinstance(store_manager, StoreManager)
