"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: 状态钩子管理器 - 处理状态变化触发的声明式自动化动作（框架无关）
"""

import asyncio
import logging
from typing import Any, Dict, List

from pystores.result import handle_exceptions

logger = logging.getLogger(__name__)


class StateHookManager:
    """状态钩子管理器 - 统一管理状态变化触发的自动化操作"""

    @staticmethod
    @handle_exceptions("处理状态监听")
    async def handle_state_monitor(state_instance: Any, key: str, value: Any) -> None:
        """处理状态监听配置 - 从状态类的 _state_monitors 读取"""
        state_name = getattr(state_instance.__class__, "_state_name", "")
        if not state_name:
            return

        state_monitors = getattr(state_instance.__class__, "_state_monitors", {})
        if not state_monitors:
            return
        if state_name not in state_monitors:
            return

        state_config = state_monitors[state_name]
        if key not in state_config:
            return

        value_actions = state_config[key]
        value_key = str(value) if not isinstance(value, (str, int, bool, type(None))) else value
        if value_key not in value_actions:
            return

        actions = value_actions[value_key]
        if not actions:
            return

        logger.debug(f"状态监听触发: {state_name}.{key}={value}, 执行{len(actions)}个动作")
        await StateHookManager._execute_action_list(
            state_instance,
            actions,
            f"状态监听({state_name}.{key}={value_key})",
        )

    @staticmethod
    @handle_exceptions("执行动作列表")
    async def _execute_action_list(
        state_instance: Any,
        actions: List[Dict[str, Any]],
        log_prefix: str,
    ) -> None:
        """执行动作列表 - 需要 UI 上下文的同步执行，其余并行"""
        if not actions:
            return

        ui_actions = [a for a in actions if a.get("ui_context")]
        other_actions = [a for a in actions if not a.get("ui_context")]

        # 1. 先同步执行需要 UI 上下文的动作
        if ui_actions:
            ui_context = state_instance.__class__._context.get_ui_context()
            for action in ui_actions:
                await StateHookManager._execute_single_action(
                    state_instance, action, log_prefix, ui_context
                )

        # 2. 后并行执行其他动作（不等待）
        if other_actions:
            asyncio.create_task(
                StateHookManager._execute_other_actions(state_instance, other_actions, log_prefix),
                name=f"async_actions_{log_prefix}",
            )

    @staticmethod
    async def _execute_single_action(
        state_instance: Any,
        action: Dict[str, Any],
        log_prefix: str,
        ui_context: Any = None,
    ) -> None:
        """执行单个动作"""
        from pystores.core.action import ActionExecutor

        try:
            target_state_name = action.get("state")
            method_name = action.get("method")
            params = action.get("params", {})

            if not target_state_name or not method_name:
                logger.warning(f"{log_prefix} action 配置不完整，跳过")
                return

            target_instance = await state_instance.__class__.get_state_instance_by_name(
                state_instance, target_state_name
            )
            if not target_instance:
                logger.debug(
                    f"[{log_prefix}] action={method_name}，"
                    f"获取状态实例失败：状态类不存在: {target_state_name}"
                )
                return

            if not hasattr(target_instance, method_name) or not callable(
                getattr(target_instance, method_name)
            ):
                logger.debug(
                    f"[{log_prefix}] action={method_name}，"
                    f"方法不存在：状态 {target_state_name} 没有方法 {method_name}"
                )
                return

            processed_params, param_error = await ActionExecutor._process_params(
                state_instance,
                params=params,
                params_mapping=None,
                method_name=method_name,
                check_errors=True,
            )
            if param_error:
                logger.warning(f"[{log_prefix}] action={method_name}，参数校验失败，跳过")
                return

            await StateHookManager._execute_method(
                target_instance,
                method_name,
                processed_params,
                log_prefix,
                ui_context=ui_context,
            )
        except Exception as e:
            logger.error(f"执行{log_prefix}失败, 错误: {e!s}")

    @staticmethod
    async def _execute_other_actions(
        state_instance: Any,
        actions: List[Dict[str, Any]],
        log_prefix: str,
    ) -> None:
        """并行执行不需要 UI 上下文的动作"""
        from pystores.core.action import ActionExecutor

        for action_idx, action in enumerate(actions):
            try:
                target_state_name = action.get("state")
                method_name = action.get("method")
                params = action.get("params", {})

                if not target_state_name or not method_name:
                    continue

                target_instance = await state_instance.__class__.get_state_instance_by_name(
                    state_instance, target_state_name
                )
                if not target_instance:
                    continue

                if not hasattr(target_instance, method_name) or not callable(
                    getattr(target_instance, method_name)
                ):
                    continue

                processed_params, param_error = await ActionExecutor._process_params(
                    state_instance,
                    params=params,
                    params_mapping=None,
                    method_name=method_name,
                    check_errors=True,
                )
                if param_error:
                    continue

                await StateHookManager._execute_method(
                    target_instance,
                    method_name,
                    processed_params,
                    log_prefix,
                    ui_context=None,
                )
            except Exception as e:
                logger.error(f"执行{log_prefix}失败, 错误: {e!s}")

    @staticmethod
    @handle_exceptions("执行方法")
    async def _execute_method(
        target_instance: Any,
        method_name: str,
        processed_params: Dict[str, Any],
        log_prefix: str,
        ui_context: Any = None,
    ) -> None:
        """执行单个方法的通用逻辑"""
        target_state_name = target_instance.__class__._state_name

        async def execute() -> Any:
            try:
                if hasattr(target_instance, "_state_action_methods") and method_name in getattr(
                    target_instance, "_state_action_methods", {}
                ):
                    result = await asyncio.wait_for(
                        target_instance.execute_action(
                            method_name,
                            processed_params,
                            use_processed_params=True,
                        ),
                        timeout=40.0,
                    )
                else:
                    method = getattr(target_instance, method_name)
                    if asyncio.iscoroutinefunction(method):
                        result = await asyncio.wait_for(method(**processed_params), timeout=40.0)
                    else:
                        result = method(**processed_params)
                return result
            except asyncio.TimeoutError:
                logger.warning(f"执行{log_prefix}操作超时: {target_state_name}.{method_name}")
                return None

        try:
            if ui_context is not None:
                with ui_context:
                    result = await execute()
            else:
                result = await execute()

            if result is None:
                pass
            elif hasattr(result, "success"):
                if result.success:
                    logger.debug(f"执行{log_prefix}操作成功: {target_state_name}.{method_name}")
                else:
                    logger.warning(
                        f"执行{log_prefix}操作失败: {target_state_name}.{method_name}, "
                        f"错误: {result.message}"
                    )
            else:
                logger.debug(f"执行{log_prefix}操作完成: {target_state_name}.{method_name}")
        except Exception as e:
            logger.error(f"调用方法异常: {target_state_name}.{method_name}, 错误: {e!s}")
