"""
T0 收集器数据模型定义

使用枚举和类型常量（而非 Pydantic）以保持与现有代码风格一致
"""

from enum import Enum
from typing import Dict, List, Optional


class ComponentType(str, Enum):
    """组件类型枚举"""
    DEPLOYMENT = "deployment"
    DAEMONSET = "daemonset"
    ENDPOINT = "endpoint"


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    MISSING = "missing"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# 核心组件列表
DEPLOYMENTS_TO_CHECK = [
    "kube-ovn-controller",
    "kube-ovn-monitor",
    "ovn-central",
]

DAEMONSETS_TO_CHECK = [
    "kube-ovn-cni",
    "kube-ovn-pinger",
    "ovs-ovn",
]

ENDPOINTS_TO_CHECK = [
    "ovn-nb",
    "ovn-northd",
    "ovn-sb",
]

ALL_COMPONENTS = DEPLOYMENTS_TO_CHECK + DAEMONSETS_TO_CHECK + ENDPOINTS_TO_CHECK
