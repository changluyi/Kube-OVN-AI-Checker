"""
收集器模块 - Kube-OVN 网络诊断数据收集

提供快速健康检查和资源收集功能
"""

from .k8s_client import get_k8s_client, KubectlWrapper
from .cache import K8sCache, get_cache, reset_cache
from .resource_collector import K8sResourceCollector
from .models import (
    ComponentType,
    HealthStatus,
    DEPLOYMENTS_TO_CHECK,
    DAEMONSETS_TO_CHECK,
    ENDPOINTS_TO_CHECK,
    ALL_COMPONENTS,
)
from .t0_collector import collect_t0

__all__ = [
    # K8s 客户端
    "get_k8s_client",
    "KubectlWrapper",
    # 缓存
    "K8sCache",
    "get_cache",
    "reset_cache",
    # 收集器
    "K8sResourceCollector",
    "collect_t0",
    # 模型
    "ComponentType",
    "HealthStatus",
    "DEPLOYMENTS_TO_CHECK",
    "DAEMONSETS_TO_CHECK",
    "ENDPOINTS_TO_CHECK",
    "ALL_COMPONENTS",
]
