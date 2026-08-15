"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 状态基类与服务执行器协议 - 生命周期、隔离、跨状态通信与声明式 Action
"""

import dataclasses
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Generic, Literal, Optional, Protocol, TypeVar

from pystores.core.context import ContextProvider, MemoryContext
from pystores.core.storage import MemoryStorage, StorageProvider
from pystores.result import Result, handle_exceptions

logger = logging.getLogger(__name__)

# 状态生命周期状态
StateLifecycle = Literal["active", "deactivating"]

# 状态错误码（包内常量）
STATE_DISPOSING = "STATE_DISPOSING"
STATE_UPDATE_FAILED = "STATE_UPDATE_FAILED"

T = TypeVar("T")
S = TypeVar("S", bound="BaseStore")


class ServiceExecutor(Protocol):
    """服务执行器协议 - 对接任意服务层的抽象接口

    用户实现本协议并注入 BaseStore，声明式 Action 即通过它调用服务：
    - 注册: BaseStore.configure(service=MyExecutor())
    - 服务调用: await executor.execute(service_name, method_name, params)
    """

    async def execute(
        self,
        service_name: str,
        method_name: str,
        params: dict[str, Any],
    ) -> Result:
        """执行服务调用"""
        ...


@dataclass
class BaseStore(Generic[T]):
    """状态基类 - 提供核心状态管理功能

    框架无关设计：依赖 ContextProvider / StorageProvider / ServiceExecutor
    三个协议，通过 `configure()` 注入后端实现。未配置时使用内置的内存实现，
    核心可脱离任何 UI 框架独立运行。

    状态实例生命周期:
    active → deactivating → 从 _instances 移除 → disposed（GC 回收）
    """

    # ========== 类级注入配置（后端适配器） ==========
    _context: ClassVar[ContextProvider] = MemoryContext()
    _storage: ClassVar[StorageProvider] = MemoryStorage()
    _service: ClassVar[Optional[ServiceExecutor]] = None

    # ========== 类级配置字段（子类声明） ==========
    # 实例字典: {context_id: {state_name: instance}}
    _instances: ClassVar[dict[str, dict[str, Any]]] = {}
    # 状态名称，全局唯一标识
    _state_name: ClassVar[str] = ""
    # 隔离级别: tab / browser / client
    _state_isolation_level: ClassVar[str] = "client"
    # 状态名到隔离级别的映射缓存 - O(1) 查找
    _state_name_to_isolation_level: ClassVar[dict[str, str]] = {}
    # 可对外共享的字段白名单: {field_name: 说明}
    _state_share_fields: ClassVar[dict[str, str]] = {}
    # 需持久化的字段: {field_name: storage_type}
    _state_storage_field: ClassVar[dict[str, str]] = {}
    # 声明式服务方法配置: {action_name: config}
    _state_action_methods: ClassVar[dict[str, dict[str, Any]]] = {}
    # 统一状态监听配置: {field_name: {value: [actions]}}
    _state_monitors: ClassVar[dict[str, dict[str, list[dict[str, Any]]]]] = {}
    # 类方法生成标记 - 防止重复生成
    _methods_generated: ClassVar[dict[str, bool]] = {}

    # 认证相关配置（声明式 Action 提取 token 与更新认证状态用）
    _auth_state: ClassVar[str] = "user"  # 提取 token 的状态名
    _auth_token_field: ClassVar[str] = "token"  # token 字段名
    auth_action_methods: ClassVar[list[str]] = []  # 认证操作（成功置 True）
    logout_action_methods: ClassVar[list[str]] = []  # 登出操作（成功置 False）
    auth_target_state: ClassVar[str] = "router"  # 认证状态所在状态
    auth_state_field: ClassVar[str] = "is_authenticated"  # 认证状态字段

    # ========== 实例级字段 ==========
    _initialized: bool = False
    _is_updating: bool = False
    _is_disposing: bool = False
    _last_access_time: float = field(default_factory=time.time)
    _context_id: str = ""
    _tab_id: str = ""
    _browser_id: str = ""
    _client_id: str = ""
    lifecycle_state: StateLifecycle = "active"
    is_loading: bool = False
    refresh_at: float = field(default_factory=lambda: datetime.now().timestamp())

    # ========== 配置注入 ==========
    # 用于区分"未提供该参数"与"显式传入 None"（显式 None 表示清除注入）
    _UNSET = object()

    @classmethod
    def configure(
        cls,
        *,
        context: Optional[ContextProvider] | object = _UNSET,
        storage: Optional[StorageProvider] | object = _UNSET,
        service: Optional[ServiceExecutor] | object = _UNSET,
    ) -> None:
        """注入后端适配器（类级，对全部子类生效）

        Args:
            context: 上下文提供者（三级隔离 ID 来源）
            storage: 存储提供者（状态持久化）
            service: 服务执行器（声明式 Action 的服务调用入口）

        省略参数表示保持现状；显式传 None 表示清除对应注入（回退默认实现）。
        """
        if context is not BaseStore._UNSET:
            cls._context = context or MemoryContext()
        if storage is not BaseStore._UNSET:
            cls._storage = storage or MemoryStorage()
        if service is not BaseStore._UNSET:
            cls._service = service

    @classmethod
    def set_monitors(cls, monitors: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
        """设置全局状态监听配置（声明式副作用）"""
        cls._state_monitors = monitors

    # ========== 1. 实例生命周期管理 ==========
    @classmethod
    @handle_exceptions("创建状态实例")
    async def _create_instance(cls, context_id: str, state_name: str) -> "BaseStore":
        """创建状态实例并设置默认值（不标记已初始化，由 initialize() 完成）"""
        instance = cls()

        # 确保实例状态标记被正确初始化
        instance._is_disposing = False
        instance._is_updating = False
        instance._initialized = False

        # 设置上下文信息
        cls._context.apply_to_instance(instance, cls._state_isolation_level)

        # 设置默认值
        default_values: dict[str, Any] = {}
        await instance._set_default_values_to_dict(default_values)
        for attr_name, value in default_values.items():
            setattr(instance, attr_name, value)

        # 激活
        instance.lifecycle_state = "active"

        # 存储实例到双层嵌套字典
        context_instances = cls._instances.setdefault(context_id, {})
        context_instances[state_name] = instance

        return instance

    @classmethod
    @handle_exceptions("获取状态实例")
    async def get_instance(cls, context_id: Optional[str] = None) -> "BaseStore":
        """获取或创建当前上下文的状态实例（双层嵌套字典 O(1) 查找）"""
        if not cls._state_name:
            raise ValueError(f"状态类 {cls.__name__} 必须设置 _state_name 类属性")
        state_name = cls._state_name

        if context_id is None:
            context_id = cls._context.get_context_id(cls._state_isolation_level)

        context_instances = cls._instances.get(context_id)
        if context_instances and state_name in context_instances:
            instance = context_instances[state_name]
            instance.update_last_access_time()
            return instance

        # 新建实例并自动初始化（恢复存储数据）
        instance = await cls._create_instance(context_id, state_name)
        await instance.initialize()
        return instance

    @classmethod
    @handle_exceptions("释放状态实例")
    async def dispose_instance(cls, context_id: Optional[str] = None) -> bool:
        """释放特定上下文的状态实例"""
        if context_id is None:
            context_id = cls._context.get_context_id(cls._state_isolation_level)

        context_instances = cls._instances.get(context_id)
        if not context_instances:
            logger.warning(f"上下文不存在: {context_id}")
            return False

        state_name = cls._state_name
        if state_name not in context_instances:
            logger.warning(f"状态实例不存在: {state_name} in {context_id}")
            return False

        instance = context_instances[state_name]
        if getattr(instance, "_is_disposing", False):
            logger.warning(f"状态实例 {state_name} 正在销毁中，跳过重复销毁")
            return False

        try:
            instance._is_disposing = True
            instance.lifecycle_state = "deactivating"

            # 先从字典移除（原子化，让并发 get_instance 创建新实例）
            del context_instances[state_name]
            if not context_instances:
                del cls._instances[context_id]

            # 执行销毁前清理钩子
            if hasattr(instance, "_before_dispose") and callable(instance._before_dispose):
                await instance._before_dispose()

            return True
        except Exception as e:
            logger.error(f"销毁状态实例出错: {context_id}, 错误: {e!s}")
            instance._is_disposing = False
            return False

    @classmethod
    def get_isolation_level_by_state_name(cls, state_name: str) -> str:
        """通过状态名快速获取隔离级别 - O(1)"""
        return cls._state_name_to_isolation_level.get(state_name, "tab")

    @classmethod
    @handle_exceptions("通过状态名获取目标状态实例")
    async def get_state_instance_by_name(
        cls, current_instance: "BaseStore", target_state_name: str
    ) -> Optional["BaseStore"]:
        """通过状态名获取目标状态实例（跨状态访问入口）"""
        isolation_level = cls.get_isolation_level_by_state_name(target_state_name)
        context_id = cls._context.get_instance_specific_context_id(
            current_instance, isolation_level
        )
        return cls._instances.get(context_id, {}).get(target_state_name)

    # ========== 2. 类方法自动生成 ==========
    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """子类定义时自动注册隔离级别映射与生成声明式方法"""
        super().__init_subclass__(**kwargs)

        state_name = getattr(cls, "_state_name", "")
        if state_name:
            isolation_level = getattr(cls, "_state_isolation_level", "tab")
            BaseStore._state_name_to_isolation_level[state_name] = isolation_level

        cls_name = cls.__name__
        if BaseStore._methods_generated.get(cls_name):
            return

        if getattr(cls, "_state_action_methods", None):
            from pystores.core.action import ActionExecutor

            BaseStore._methods_generated[cls_name] = True
            ActionExecutor.generate_action_methods(cls, cls._state_action_methods)

    # ========== 3. 初始化与更新 ==========
    @handle_exceptions("初始化状态实例")
    async def initialize(self, initial_data: Optional[dict[str, Any]] = None) -> "BaseStore":
        """初始化状态实例，可选加载初始数据与从存储恢复"""
        if self._initialized:
            return self

        await self._set_default_values_to_dict({})
        if initial_data:
            await self.update(initial_data)
        await self.__class__._storage.load(self)

        self._initialized = True
        return self

    @handle_exceptions("执行状态操作")
    async def execute_action(
        self,
        action_name: str,
        params: dict[str, Any],
        use_processed_params: bool = False,
    ) -> Result:
        """执行声明式状态操作"""
        from pystores.core.action import ActionExecutor

        return await ActionExecutor.action(self, action_name, params, use_processed_params)

    def update_last_access_time(self) -> None:
        """更新实例最后访问时间"""
        self._last_access_time = time.time()

    def get_ui_context(self) -> Any | None:
        """获取当前 UI 上下文（由 ContextProvider 提供），无则返回 None"""
        return self.__class__._context.get_ui_context()

    @handle_exceptions("更新状态")
    async def update(self, data: dict[str, Any], refresh: bool = False) -> Result:
        """更新状态属性，可选触发 UI 刷新与持久化"""
        if getattr(self, "_is_disposing", False):
            logger.warning(f"{self.__class__.__name__} 实例正在销毁中，拒绝更新")
            return Result.create_failure(STATE_DISPOSING, STATE_DISPOSING)

        try:
            self._is_updating = True
            if refresh:
                self.is_loading = True

            from pystores.core.hook import StateHookManager

            updated_keys: list[str] = []
            for key, value in data.items():
                if hasattr(self, key) and not key.startswith("_"):
                    if callable(getattr(self, key)):
                        continue

                    old_value = getattr(self, key)
                    should_update = old_value != value
                    if should_update:
                        setattr(self, key, value)
                        updated_keys.append(key)

                    # 始终触发监听器（即使值未变），确保断开连接等关键操作不被跳过
                    await StateHookManager.handle_state_monitor(self, key, value)

            # 持久化有变动的存储字段
            field_mapping = getattr(self.__class__, "_state_storage_field", {})
            if field_mapping and any(key in field_mapping for key in updated_keys):
                await self.__class__._storage.save(self)

            if refresh:
                self.refresh_at = datetime.now().timestamp()
                self.is_loading = False

            self.update_last_access_time()
            return Result.create_success(True)
        except Exception as e:
            logger.error(f"{self.__class__.__name__} 更新发生异常: {e!s}")
            return Result.create_failure(STATE_UPDATE_FAILED, str(e))
        finally:
            self._is_updating = False
            if refresh and getattr(self, "is_loading", False):
                self.is_loading = False

    @handle_exceptions("重置状态")
    async def reset(self, refresh: bool = False) -> Result:
        """重置状态为类型注解默认值"""
        default_values: dict[str, Any] = {}
        await self._set_default_values_to_dict(default_values)
        return await self.update(default_values, refresh)

    @handle_exceptions("获取默认值字典")
    async def _set_default_values_to_dict(self, values_dict: dict[str, Any]) -> None:
        """将状态字段的默认值写入字典

        默认值优先级: dataclass 字段默认值 → 类属性声明的默认值 → 类型推断
        这样普通子类（未用 dataclass 装饰）与 dataclass 子类行为一致。
        """
        annotations = getattr(self.__class__, "__annotations__", {})
        for attr_name, attr_type in annotations.items():
            if attr_name.startswith("_") or attr_name == "refresh_at":
                continue

            field_def = self.__class__.__dataclass_fields__.get(attr_name)
            if field_def is not None:
                if field_def.default is not dataclasses.MISSING:
                    values_dict[attr_name] = field_def.default
                elif field_def.default_factory is not dataclasses.MISSING:
                    values_dict[attr_name] = field_def.default_factory()
                else:
                    values_dict[attr_name] = _infer_default(attr_type)
                continue

            # 普通类字段: 读取类属性声明的默认值
            class_default = self.__class__.__dict__.get(attr_name, dataclasses.MISSING)
            if isinstance(class_default, dataclasses.Field):
                # 普通子类用 field() 声明（dataclass 机制不处理），解析其默认值
                if class_default.default_factory is not dataclasses.MISSING:
                    values_dict[attr_name] = class_default.default_factory()
                elif class_default.default is not dataclasses.MISSING:
                    values_dict[attr_name] = class_default.default
                else:
                    values_dict[attr_name] = _infer_default(attr_type)
            elif class_default is not dataclasses.MISSING:
                values_dict[attr_name] = class_default
            else:
                values_dict[attr_name] = _infer_default(attr_type)

    # ========== 4. 跨状态通信 ==========
    @handle_exceptions("获取状态属性值")
    async def get_state_value(
        self, state_name: str, field_name: str, default: Any = None
    ) -> Result:
        """获取其他状态属性值 - 仅限 _state_share_fields 白名单字段"""
        target_instance = await self.__class__.get_state_instance_by_name(self, state_name)
        if not target_instance:
            logger.warning(f"未找到状态实例: {state_name}")
            return Result.create_success(default)

        share_fields = getattr(target_instance.__class__, "_state_share_fields", {})
        if not share_fields or field_name not in share_fields:
            logger.warning(f"属性未声明为共享字段: {field_name}")
            return Result.create_failure("NotShareField", f"属性未声明为共享字段: {field_name}")

        if not hasattr(target_instance, field_name):
            return Result.create_success(default)

        return Result.create_success(getattr(target_instance, field_name))

    # ========== 5. 实例销毁 ==========
    @handle_exceptions("释放所有相关状态实例")
    async def dispose_all_instances(self) -> int:
        """销毁与当前实例关联的所有上下文实例"""
        count = 0
        for context_id in [self._client_id, self._tab_id, self._browser_id]:
            if context_id:
                instances = self.__class__._instances.pop(context_id, None)
                if instances:
                    count += len(instances)
        logger.debug(f"已销毁 {count} 个状态实例")
        return count

    @handle_exceptions("基于实例和状态名销毁目标实例")
    async def dispose_target_instance(self, target_state_name: str) -> bool:
        """销毁目标状态实例"""
        target_instance = await self.__class__.get_state_instance_by_name(self, target_state_name)
        if not target_instance:
            logger.debug(f"目标状态 {target_state_name} 实例不存在，无需销毁")
            return False

        target_context_id = getattr(target_instance, "_context_id", None)
        if not target_context_id:
            logger.warning(f"目标状态 {target_state_name} 实例缺少上下文信息")
            return False

        return await target_instance.__class__.dispose_instance(target_context_id)


def _infer_default(attr_type: Any) -> Any:
    """根据类型注解推断默认值"""
    if attr_type is str:
        return ""
    if attr_type is int:
        return 0
    if attr_type is float:
        return 0.0
    if attr_type is bool:
        return False
    if attr_type is list:
        return []
    if attr_type is dict:
        return {}
    return None
