"""
Author: Zhang Di
Email: dizflyme@qq.com
Date: 2026-08-15 14:30:00
LastEditors: Zhang Di
LastEditTime: 2026-08-15 14:30:00
Description: Result 结果对象与 handle_exceptions 异常处理装饰器（纯 Python 零依赖）
"""

import functools
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """统一结果对象 - 标准化返回格式与统一错误处理"""

    success: bool
    data: Optional[T] = None
    code: str = ""
    message: str = "操作成功"
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_success(
        cls,
        data: Optional[T] = None,
        message: Optional[str] = None,
        code: str = "",
    ) -> "Result[T]":
        """创建成功结果"""
        return cls(True, data, code, message or "操作成功")

    @classmethod
    def create_failure(
        cls,
        code: str = "UnknownError",
        message: Optional[str] = None,
        data: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
        **format_args,
    ) -> "Result[T]":
        """创建失败结果"""
        msg = message or code
        if format_args:
            try:
                msg = msg.format(**format_args)
            except (KeyError, ValueError):
                pass
        logger.warning(f"操作失败: code={code}, message={msg}")
        return cls(False, data, code, msg, details or {})

    def is_success(self) -> bool:
        """判断是否成功"""
        return self.success

    def is_failure(self) -> bool:
        """判断是否失败"""
        return not self.success

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "code": self.code or (0 if self.success else -1),
            "msg": self.message,
            "data": self.data,
        }
        if self.details:
            result["details"] = self.details
        return result


def handle_exceptions(operation: Optional[str] = None) -> Callable:
    """统一的异常处理装饰器 - 将异常转换为 Result 对象"""

    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        is_async = inspect.iscoroutinefunction(func)

        def handle_error(e: Exception) -> Result:
            logger.error(f"{op_name}失败: {e!s}", exc_info=True)
            return Result.create_failure(
                code="ExceptionOccurred",
                message=f"{op_name}失败: {e!s}",
                details={"error": str(e), "error_type": e.__class__.__name__},
            )

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return handle_error(e)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return handle_error(e)

        return async_wrapper if is_async else sync_wrapper

    return decorator
