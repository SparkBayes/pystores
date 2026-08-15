"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 状态操作执行器 - 声明式 Action 的参数映射、服务调用、结果处理与自动方法生成（框架无关）
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from pystores.result import Result, handle_exceptions

logger = logging.getLogger(__name__)

# 服务调用默认超时（秒）
_SERVICE_TIMEOUT = 40.0


class ActionExecutor:
    """状态操作执行器 - 声明式 Action 的静态执行器

    通过 BaseStore.configure(service=...) 注入的 ServiceExecutor 调用服务，
    核心层不直接依赖任何服务管理框架。
    """

    @staticmethod
    @handle_exceptions("解析参数引用")
    async def _resolve_param_reference(
        state_instance: Any,
        reference: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """统一的参数引用解析器

        支持格式:
        - "self.attribute": 引用当前状态属性
        - "state_name.attribute": 引用其他状态共享字段
        - 其他值视为直接值
        """
        if not isinstance(reference, str):
            return reference

        if reference.startswith("self."):
            attr_name = reference[5:]
            if hasattr(state_instance, attr_name):
                return getattr(state_instance, attr_name)
            logger.warning(f"[参数处理] 当前状态没有属性: {attr_name}")
            return None

        if "." in reference:
            state_name, field_name = reference.split(".", 1)
            state_value_result = await state_instance.get_state_value(state_name, field_name)
            if state_value_result.success:
                return state_value_result.data
            # 降级：直接访问目标状态实例（兼容未声明共享字段的场景）
            source_instance = await state_instance.__class__.get_state_instance_by_name(
                state_instance, state_name
            )
            if source_instance and hasattr(source_instance, field_name):
                return getattr(source_instance, field_name)
            logger.warning(f"[参数处理] 无法解析引用: {reference}")
            return None

        if context and reference in context:
            return context.get(reference)

        return reference

    @staticmethod
    @handle_exceptions("处理参数")
    async def _process_params(
        state_instance: Any,
        params: Dict[str, Any],
        params_mapping: Optional[Dict[str, Any]] = None,
        allow_none_values: Optional[List[str]] = None,
        method_name: str = "",
        check_errors: bool = False,
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], bool]]:
        """统一的参数处理函数 - 支持映射模式与直接模式"""
        result_params: Dict[str, Any] = {}
        allow_none_list = allow_none_values or []
        param_error = False

        targets: Dict[str, Any]
        if params_mapping:
            targets = params_mapping
        else:
            targets = {k: v for k, v in params.items()}

        for target_name, spec in targets.items():
            value: Any = None

            if params_mapping:
                if isinstance(spec, tuple):
                    # 元组形式: (参数名, 默认值)
                    param_name, default_value = spec
                    value = params.get(param_name)
                    if value is None:
                        value = await ActionExecutor._resolve_param_reference(
                            state_instance, default_value
                        )
                elif isinstance(spec, str):
                    if spec.startswith("self."):
                        value = await ActionExecutor._resolve_param_reference(state_instance, spec)
                    elif "." in spec and not params.get(spec):
                        value = await ActionExecutor._resolve_param_reference(state_instance, spec)
                    else:
                        value = params.get(spec)
                else:
                    value = spec
            else:
                value = await ActionExecutor._resolve_param_reference(state_instance, spec, params)

            if value is None and target_name not in allow_none_list:
                logger.warning(f"[参数处理] {method_name}: 参数 {target_name} 为 None 但不允许")
                if check_errors:
                    param_error = True
                    break
                continue

            result_params[target_name] = value

        return (result_params, param_error) if check_errors else result_params

    @staticmethod
    @handle_exceptions("执行状态操作")
    async def action(
        state_instance: Any,
        action_name: str,
        params: Dict[str, Any],
        use_processed_params: bool = False,
    ) -> Result:
        """执行声明式状态操作"""
        action_config = getattr(state_instance, "_state_action_methods", {}).get(action_name)
        if not action_config:
            return Result.create_failure("ActionNotFound", f"未找到操作方法: {action_name}")

        service_name = action_config.get("service_name")
        method_name = action_config.get("method_name")
        operation_type = action_config.get("operation_type", "未指定操作")
        refresh = action_config.get("refresh", False)

        if refresh:
            state_instance.is_loading = True

        if not service_name or not method_name:
            if refresh:
                state_instance.is_loading = False
            return Result.create_failure(
                "InvalidActionConfig", f"操作方法配置不完整: {action_name}"
            )

        # 保存原始 params 供 reload_state 使用
        state_instance._last_action_params = params

        if use_processed_params:
            prepared_params = params
        else:
            params_mapping = action_config.get("params_mapping", {})
            allow_none_values = action_config.get("allow_none_values", [])
            prepared_params = await ActionExecutor._process_params(
                state_instance,
                params=params,
                params_mapping=params_mapping,
                allow_none_values=allow_none_values,
                method_name=action_name,
            )

        # 获取 token（认证来源可配置）
        requires_token = action_config.get("requires_token", True)
        token = None
        if requires_token:
            auth_state = getattr(state_instance.__class__, "_auth_state", "user")
            auth_token_field = getattr(state_instance.__class__, "_auth_token_field", "token")
            token_result = await state_instance.get_state_value(auth_state, auth_token_field, "")
            if token_result.success and token_result.data:
                token = token_result.data

        # 获取服务执行器（通过协议注入）
        service_executor = getattr(state_instance.__class__, "_service", None)
        if service_executor is None:
            if refresh:
                state_instance.is_loading = False
            return Result.create_failure(
                "NoServiceExecutor",
                "未配置服务执行器，请通过 BaseStore.configure(service=...) 注入",
            )

        try:
            logger.info(f"执行操作: {operation_type} ({service_name}.{method_name})")
            if token:
                prepared_params["token"] = token

            result = await asyncio.wait_for(
                service_executor.execute(
                    service_name=service_name,
                    method_name=method_name,
                    params=prepared_params,
                ),
                timeout=_SERVICE_TIMEOUT,
            )

            processed_result = await ActionExecutor._process_action_result(
                state_instance, action_name, result
            )

            if result.success:
                await ActionExecutor._handle_auth_state_update(state_instance, action_name, True)

            return processed_result
        except asyncio.TimeoutError:
            logger.warning(f"执行操作超时: {action_name}")
            return Result.create_failure("ActionTimeout", f"执行操作超时: {action_name}")
        except Exception as e:
            logger.error(f"执行操作异常: {operation_type} ({action_name}), 错误: {e!s}")
            return Result.create_failure(
                "ActionExecutionFailed",
                f"执行操作失败: {action_name}",
                details={"error": str(e)},
            )
        finally:
            if refresh and getattr(state_instance, "is_loading", False):
                state_instance.is_loading = False

    @staticmethod
    @handle_exceptions("处理状态操作结果")
    async def _process_action_result(
        state_instance: Any, action_name: str, result: Result
    ) -> Result:
        """处理状态操作结果 - 重置、更新、reload"""
        action_config = getattr(state_instance, "_state_action_methods", {}).get(action_name, {})
        refresh = action_config.get("refresh", False)

        if not result.success and refresh and state_instance.is_loading:
            state_instance.is_loading = False
            return result

        # 重置状态（优先级最高）
        if action_config.get("reset_state", False):
            if action_config.get("clear_storage", False):
                storage = getattr(state_instance.__class__, "_storage", None)
                if storage is not None:
                    await storage.clear(state_instance)
            await state_instance.reset(refresh=True)
            return result

        # 更新状态
        updates: Dict[str, Any] = {}

        # result_field: 将服务返回数据写入指定状态字段（支持任意类型，如列表）
        result_field = action_config.get("result_field")
        if result_field and hasattr(result, "data"):
            updates[result_field] = result.data
        elif hasattr(result, "data") and isinstance(result.data, dict):
            # 向后兼容：dict 类型 data 自动合并进状态
            updates.update(result.data)

        additional_updates = action_config.get("additional_updates", {})
        if additional_updates:
            updates = {**updates, **additional_updates}

        if updates:
            await state_instance.update(updates, refresh=refresh)

        # reload_state: 操作成功后调用刷新方法
        if result.success and action_config.get("reload_state"):
            reload_method_name = action_config.get("reload_state")
            if reload_method_name and hasattr(state_instance, reload_method_name):
                reload_method = getattr(state_instance, reload_method_name)
                if callable(reload_method):
                    reload_params = action_config.get("reload_params", {})
                    if reload_params:
                        original_params = getattr(state_instance, "_last_action_params", {})
                        reload_args = {k: original_params.get(v) for k, v in reload_params.items()}
                        await reload_method(**reload_args)
                    else:
                        await reload_method()

        return result

    @classmethod
    def generate_action_methods(
        cls, target_cls: Any, action_methods: Dict[str, Dict[str, Any]]
    ) -> None:
        """为类自动生成声明式操作方法"""
        for action_name, config in action_methods.items():
            if hasattr(target_cls, action_name) and callable(getattr(target_cls, action_name)):
                logger.debug(f"方法 {action_name} 已在 {target_cls.__name__} 中存在，跳过自动生成")
                continue

            async def create_action_method(
                self: Any, *args: Any, _action_name: str = action_name, **kwargs: Any
            ) -> Result:
                """声明式服务方法 - 自动生成的方法"""
                combined_params: Dict[str, Any] = {}
                if args:
                    action_config = self._state_action_methods.get(_action_name, {})
                    params_mapping = action_config.get("params_mapping", {})
                    param_names = list(params_mapping.keys())
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            combined_params[param_names[i]] = arg
                combined_params.update(kwargs)

                return await self.execute_action(_action_name, combined_params)

            create_action_method.__name__ = action_name
            create_action_method.__doc__ = config.get(
                "description", f"执行{config.get('operation_type', action_name)}操作"
            )
            setattr(target_cls, action_name, create_action_method)

    @staticmethod
    @handle_exceptions("处理认证状态更新")
    async def _handle_auth_state_update(
        state_instance: Any, action_name: str, operation_success: bool
    ) -> None:
        """声明式认证状态更新 - 登录/登出成功后同步认证字段"""
        auth_actions = getattr(state_instance, "auth_action_methods", [])
        logout_actions = getattr(state_instance, "logout_action_methods", [])
        target_state = getattr(state_instance, "auth_target_state", "router")
        auth_field = getattr(state_instance, "auth_state_field", "is_authenticated")

        if action_name in auth_actions and operation_success:
            await ActionExecutor._set_auth_field(state_instance, target_state, auth_field, True)
        elif action_name in logout_actions and operation_success:
            await ActionExecutor._set_auth_field(state_instance, target_state, auth_field, False)

    @staticmethod
    async def _set_auth_field(
        state_instance: Any, target_state: str, auth_field: str, value: bool
    ) -> None:
        """设置目标状态的认证字段"""
        target_instance = await state_instance.__class__.get_state_instance_by_name(
            state_instance, target_state
        )
        if target_instance:
            await target_instance.update({auth_field: value})
        else:
            logger.warning(f"无法获取目标状态实例: {target_state}")
