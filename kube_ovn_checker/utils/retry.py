"""
重试机制模块

基于 Tenacity 库提供指数退避重试功能
"""

from functools import wraps
from typing import Type, Tuple, Callable, Any
import asyncio
import logging

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    # 如果 tenacity 不可用,提供简单的重试实现
    TENACITY_AVAILABLE = False
    import time

    retry = None
    stop_after_attempt = None
    wait_exponential = None
    retry_if_exception_type = None
    before_sleep_log = None

logger = logging.getLogger(__name__)


def retry_on_k8s_error(
    max_attempts: int = 3,
    wait_min: float = 2,
    wait_max: float = 10,
    exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    )
):
    """Kubernetes API 调用重试装饰器

    对可能失败的操作进行重试,使用指数退避策略

    Args:
        max_attempts: 最大重试次数 (默认 3)
        wait_min: 最小等待时间 (秒, 默认 2)
        wait_max: 最大等待时间 (秒, 默认 10)
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数

    Example:
        @retry_on_k8s_error(max_attempts=5)
        async def collect_pod_logs(pod_name: str):
            # 可能失败的操作
            return await k8s.run(...)
    """

    if TENACITY_AVAILABLE:
        # 使用 tenacity 库
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
    else:
        # 简单实现 (备用)
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception = None

                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt == max_attempts:
                            # 最后一次尝试失败
                            logger.warning(
                                f"函数 {func.__name__} 在 {max_attempts} 次尝试后失败"
                            )
                            raise

                        # 计算等待时间 (指数退避)
                        wait_time = min(wait_min * (2 ** (attempt - 1)), wait_max)
                        logger.warning(
                            f"函数 {func.__name__} 第 {attempt} 次尝试失败: {str(e)}. "
                            f"等待 {wait_time:.1f} 秒后重试..."
                        )
                        await asyncio.sleep(wait_time)

                # 理论上不会到达这里
                raise last_exception

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                import time

                last_exception = None

                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt == max_attempts:
                            logger.warning(
                                f"函数 {func.__name__} 在 {max_attempts} 次尝试后失败"
                            )
                            raise

                        wait_time = min(wait_min * (2 ** (attempt - 1)), wait_max)
                        logger.warning(
                            f"函数 {func.__name__} 第 {attempt} 次尝试失败: {str(e)}. "
                            f"等待 {wait_time:.1f} 秒后重试..."
                        )
                        time.sleep(wait_time)

                raise last_exception

            # 根据函数类型返回合适的包装器
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator


def retry_on_llm_error(
    max_attempts: int = 2,
    wait_min: float = 3,
    wait_max: float = 10,
    exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
    )
):
    """LLM API 调用重试装饰器

    专门用于 LLM API 调用的重试,重试次数较少 (默认2次)

    Args:
        max_attempts: 最大重试次数 (默认 2)
        wait_min: 最小等待时间 (秒, 默认 3)
        wait_max: 最大等待时间 (秒, 默认 10)
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数
    """
    return retry_on_k8s_error(
        max_attempts=max_attempts,
        wait_min=wait_min,
        wait_max=wait_max,
        exceptions=exceptions
    )


async def safe_execute(
    func: Callable,
    *args: Any,
    error_message: str = "操作失败",
    error_code: Any = None,
    **kwargs: Any
) -> Any:
    """安全执行函数,捕获异常并转换为 DiagnosticError

    Args:
        func: 要执行的函数
        *args: 位置参数
        error_message: 错误消息
        error_code: 错误码
        **kwargs: 关键字参数

    Returns:
        函数执行结果

    Raises:
        DiagnosticError: 包装后的异常
    """
    from .errors import DiagnosticError, DiagnosticErrorCode

    try:
        return await func(*args, **kwargs)
    except DiagnosticError:
        # 已经是 DiagnosticError,直接抛出
        raise
    except Exception as e:
        # 转换为 DiagnosticError
        raise DiagnosticError(
            message=f"{error_message}: {str(e)}",
            code=error_code or DiagnosticErrorCode.UNKNOWN,
            details={"original_error": str(e), "error_type": type(e).__name__}
        )
