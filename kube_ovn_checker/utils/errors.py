"""
诊断错误类型定义

提供结构化的错误处理机制
"""

from enum import Enum
from typing import Dict, Any, Optional


class DiagnosticErrorCode(Enum):
    """诊断错误码枚举"""

    # 超时类错误
    TIMEOUT = "TIMEOUT"
    COLLECTION_TIMEOUT = "COLLECTION_TIMEOUT"

    # 权限类错误
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"

    # 资源类错误
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_DEPLETED = "RESOURCE_DEPLETED"

    # API 类错误
    API_ERROR = "API_ERROR"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # 配置类错误
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # 网络类错误
    NETWORK_ERROR = "NETWORK_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"

    # 未知错误
    UNKNOWN = "UNKNOWN"


class DiagnosticError(Exception):
    """诊断异常基类

    提供结构化的错误信息,便于日志记录和错误处理

    Attributes:
        message: 错误消息
        code: 错误码
        details: 额外的错误详情
    """

    def __init__(
        self,
        message: str,
        code: DiagnosticErrorCode = DiagnosticErrorCode.UNKNOWN,
        details: Optional[Dict[str, Any]] = None
    ):
        """初始化诊断错误

        Args:
            message: 错误描述信息
            code: 错误码
            details: 额外的错误详情 (如资源名、命令等)
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式

        Returns:
            包含完整错误信息的字典
        """
        return {
            "error": self.message,
            "code": self.code.value,
            "details": self.details
        }

    def __str__(self) -> str:
        """友好的字符串表示"""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[{self.code.value}] {self.message} ({details_str})"
        return f"[{self.code.value}] {self.message}"


class CollectionError(DiagnosticError):
    """数据收集错误

    用于数据收集过程中的异常
    """

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """初始化收集错误

        Args:
            message: 错误描述
            resource_type: 资源类型 (如 Pod, Node)
            resource_name: 资源名称
            details: 额外详情
        """
        all_details = details or {}
        if resource_type:
            all_details["resource_type"] = resource_type
        if resource_name:
            all_details["resource_name"] = resource_name

        super().__init__(message, DiagnosticErrorCode.API_ERROR, all_details)


class LLMError(DiagnosticError):
    """LLM 相关错误

    用于 LLM 调用和解析过程中的异常
    """

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """初始化 LLM 错误

        Args:
            message: 错误描述
            model: 使用的模型名称
            details: 额外详情
        """
        all_details = details or {}
        if model:
            all_details["model"] = model

        super().__init__(message, DiagnosticErrorCode.API_ERROR, all_details)


class ValidationError(DiagnosticError):
    """数据验证错误

    用于输入参数或返回数据的验证失败
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """初始化验证错误

        Args:
            message: 错误描述
            field: 出错的字段名
            value: 错误的值
            details: 额外详情
        """
        all_details = details or {}
        if field:
            all_details["field"] = field
        if value is not None:
            all_details["value"] = str(value)

        super().__init__(message, DiagnosticErrorCode.INVALID_PARAMETER, all_details)
