"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: PyWebView JS 桥接 - 桌面客户端场景的可选插件（通过 NiceGUIStore 使用）
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from nicegui import ui

from pystores.result import Result, handle_exceptions

logger = logging.getLogger(__name__)


class Bridge:
    """PyWebView JS 桥接管理器

    面向 PyWebView 桌面客户端场景：服务端通过 ui.run_javascript 调用
    客户端注册的 JS API（window.pywebview.api.<function>）。

    使用前提：
    - 客户端以 PyWebView 加载应用（存在 window.pywebview）
    - 先调用 check_ready() 确认客户端模式，再执行客户端函数
    """

    def __init__(self) -> None:
        self._initialized = True
        self._is_client_mode = False

    @handle_exceptions("初始化桥接脚本")
    async def init_bridge(self) -> Result:
        """注入桥接 JS 脚本（监听 pywebviewready 事件）"""
        ui.add_head_html(
            """
            <script>
            (function() {
                window.addEventListener('pywebviewready', function() {
                    console.log('[pystores] PyWebView ready');
                });
            })();
            </script>
            """
        )
        return Result.create_success(True)

    @handle_exceptions("检查 PyWebView 就绪状态")
    async def check_ready(self) -> Result:
        """检查 PyWebView 是否就绪，就绪则进入客户端模式"""
        try:
            result = await ui.run_javascript(
                "typeof window.pywebview !== 'undefined'",
                timeout=10.0,
            )
            if result:
                self._is_client_mode = True
                return Result.create_success(True)
            self._is_client_mode = False
            return Result.create_failure("BridgeNotReady", "PyWebView 未就绪")
        except Exception as e:
            self._is_client_mode = False
            logger.error(f"检查 PyWebView 状态出错: {e!s}")
            return Result.create_failure("BridgeCheckFailed", f"检查失败: {e!s}")

    @handle_exceptions("执行客户端函数")
    async def execute_client_function(
        self,
        function_name: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Result:
        """执行客户端 JS 函数 window.pywebview.api.<function_name>(data)

        Args:
            function_name: 客户端注册的 JS API 函数名
            data: 传给函数的参数
            timeout: 单次执行超时（秒）

        Returns:
            Result，data 为客户端函数返回值
        """
        if not self._initialized:
            return Result.create_failure("BridgeNotInitialized", "桥接未初始化")
        if not self._is_client_mode:
            return Result.create_failure("NotClientMode", "非客户端模式，请先 check_ready")

        data = data or {}
        script = f"""
        try {{
            if (typeof window.pywebview?.api?.{function_name} === 'function') {{
                return window.pywebview.api.{function_name}({json.dumps(data)});
            }} else {{
                return {{ success: false, error: '{function_name} 方法不可用' }};
            }}
        }} catch (e) {{
            return {{ success: false, error: e.toString() }};
        }}
        """

        max_retries = 3
        retry_interval = 1.0
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                result = await ui.run_javascript(script, timeout=timeout)
                if isinstance(result, dict) and result.get("success") is False:
                    return Result.create_failure(
                        "BridgeFunctionFailed", result.get("error", "未知错误")
                    )
                # dict 时取 data 字段（Result 风格），否则直接用返回值
                return Result.create_success(
                    result.get("data") if isinstance(result, dict) else result
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"执行 {function_name} 失败，第 {attempt + 1} 次重试: {e!s}")
                    await asyncio.sleep(retry_interval)

        logger.error(f"执行 {function_name} 重试 {max_retries} 次后仍失败: {last_error!s}")
        return Result.create_failure("BridgeExecutionFailed", f"执行失败: {last_error!s}")
