"""
T0 级别收集器 - 快速健康检查（10 秒内完成）

收集内容：
1. 9 个核心组件健康检查（3 Deployments + 3 DaemonSets + 3 Endpoints）
2. Controller 健康状态（kube-ovn-controller）
3. Pod 聚合统计（大规模问题）或单 Pod 概览
4. Subnet 概览（CIDR、可用 IP）
5. 节点网络配置（MTU）

T0 目标：验证核心组件是否正常启动
"""

import asyncio
import time
from typing import Dict, List, Optional
from .k8s_client import get_k8s_client
from .models import (
    DEPLOYMENTS_TO_CHECK,
    DAEMONSETS_TO_CHECK,
    ENDPOINTS_TO_CHECK,
    HealthStatus,
)


async def collect_t0(
    namespace: str = "kube-system",
    pod_name: Optional[str] = None,
    scope: str = "cluster"
) -> Dict:
    """
    T0 级别收集 - 10 秒内完成

    Args:
        namespace: 命名空间 (默认 kube-system)
        pod_name: Pod 名称（可选）
        scope: "single" | "cluster"

    Returns:
        {
            "deployments": {
                "kube-ovn-controller": ComponentStatus,
                ...
            },
            "daemonsets": {
                "kube-ovn-cni": ComponentStatus,
                ...
            },
            "endpoints": {
                "ovn-nb": ComponentStatus,
                ...
            },
            # 保留现有字段以保持兼容性
            "controller_health": {...},
            "target_pod": {...} 或 "pod_stats": {...},
            "subnet_summary": {...},
            "node_network": {...},

            # 汇总统计
            "total_components": 9,
            "healthy_components": int,
            "unhealthy_components": int,
            "missing_components": int,
            "collection_duration_seconds": float,
            "data_size_kb": float,
        }
    """
    client = get_k8s_client()
    start_time = time.time()

    data = {}
    all_statuses = []

    # 1. 并发检查所有 Deployments
    print("  📊 [T0] 检查 Deployments...")
    deployment_tasks = [
        _check_deployment(client, name, namespace)
        for name in DEPLOYMENTS_TO_CHECK
    ]
    deployment_statuses = await _execute_with_limit(deployment_tasks, max_concurrent=3)

    data["deployments"] = {
        status["name"]: status
        for status in deployment_statuses
        if status
    }
    all_statuses.extend(deployment_statuses)

    # 2. 并发检查所有 DaemonSets
    print("  📊 [T0] 检查 DaemonSets...")
    daemonset_tasks = [
        _check_daemonset(client, name, namespace)
        for name in DAEMONSETS_TO_CHECK
    ]
    daemonset_statuses = await _execute_with_limit(daemonset_tasks, max_concurrent=3)

    data["daemonsets"] = {
        status["name"]: status
        for status in daemonset_statuses
        if status
    }
    all_statuses.extend(daemonset_statuses)

    # 3. 并发检查所有 Endpoints
    print("  📊 [T0] 检查 OVN 数据库 Endpoints...")
    endpoint_tasks = [
        _check_endpoint(client, name, namespace)
        for name in ENDPOINTS_TO_CHECK
    ]
    endpoint_statuses = await _execute_with_limit(endpoint_tasks, max_concurrent=3)

    data["endpoints"] = {
        status["name"]: status
        for status in endpoint_statuses
        if status
    }
    all_statuses.extend(endpoint_statuses)

    # 4. 保留现有的收集项（向后兼容）
    print("  📊 [T0] 检查 Controller 状态...")
    data["controller_health"] = await _check_controller_health(client)

    if scope == "single" and pod_name:
        print(f"  📦 [T0] 获取 Pod 概览: {namespace}/{pod_name}")
        data["target_pod"] = await _get_pod_summary(client, namespace, pod_name)
    else:
        print("  📦 [T0] 获取集群 Pod 统计...")
        data["pod_stats"] = await _get_cluster_pod_stats(client)

    print("  🌐 [T0] 获取 Subnet 概览...")
    data["subnet_summary"] = await _get_subnet_summary(client, namespace)

    print("  🔧 [T0] 获取节点网络配置...")
    data["node_network"] = await _get_node_network_config(client)

    # 5. 汇总统计
    data["total_components"] = len(all_statuses)
    data["healthy_components"] = sum(
        1 for s in all_statuses if s and s.get("status") == HealthStatus.HEALTHY
    )
    data["unhealthy_components"] = sum(
        1 for s in all_statuses if s and s.get("status") == HealthStatus.UNHEALTHY
    )
    data["missing_components"] = sum(
        1 for s in all_statuses if s and s.get("status") == HealthStatus.MISSING
    )

    data["collection_duration_seconds"] = time.time() - start_time
    data["data_size_kb"] = len(str(data)) / 1024

    return data


async def _check_deployment(
    client,
    name: str,
    namespace: str
) -> Optional[Dict]:
    """
    检查单个 Deployment 的健康状态

    Returns:
        ComponentStatus Dict 或 None（如果检查失败）
    """
    start = time.time()

    try:
        # 获取 Deployment 状态
        result = await client.get_deployment(name, namespace)

        if not result.get("success"):
            # 解析错误类型
            error = result.get("error", "")

            if "not found" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "deployment",
                    "status": HealthStatus.MISSING,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            elif "forbidden" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "deployment",
                    "status": HealthStatus.PERMISSION_DENIED,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            else:
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "deployment",
                    "status": HealthStatus.UNKNOWN,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }

        # 解析 Deployment 数据
        deployment_data = result.get("data", {})
        spec = deployment_data.get("spec", {})
        status = deployment_data.get("status", {})

        ready_replicas = status.get("readyReplicas", 0)
        replicas = spec.get("replicas", 1)
        updated_replicas = status.get("updatedReplicas", 0)
        available_replicas = status.get("availableReplicas", 0)
        unavailable_replicas = status.get("unavailableReplicas", 0)

        # 判断健康状态
        is_healthy = (
            ready_replicas == replicas and
            available_replicas == replicas and
            unavailable_replicas == 0
        )

        if is_healthy:
            return {
                "name": name,
                "namespace": namespace,
                "type": "deployment",
                "status": HealthStatus.HEALTHY,
                "ready_replicas": ready_replicas,
                "total_replicas": replicas,
                "check_duration_ms": (time.time() - start) * 1000,
            }
        else:
            # 不健康：收集 describe 和异常 Pod 的 logs
            describe_result = await client.describe_deployment(name, namespace)
            describe_output = describe_result.get("data", "") if describe_result.get("success") else describe_result.get("error", "")

            # 获取异常 Pod 列表
            pods_result = await client.get_pods(
                namespace=namespace,
                selector=f"app={name}"
            )

            pod_logs = []
            if pods_result.get("success"):
                pods = pods_result.get("data", {}).get("items", [])

                # 查找重启次数 > 3 的 Pod
                unhealthy_pods = []
                for pod in pods:
                    pod_name = pod.get("metadata", {}).get("name", "")
                    restart_count = 0

                    for container in pod.get("status", {}).get("containerStatuses", []):
                        restart_count += container.get("restartCount", 0)

                    if restart_count > 3:
                        unhealthy_pods.append((pod_name, restart_count))

                # 按重启次数排序，取前 3 个
                unhealthy_pods.sort(key=lambda x: x[1], reverse=True)

                for pod_name, _ in unhealthy_pods[:3]:
                    logs_result = await client.get_pod_logs(pod_name, namespace)
                    if logs_result.get("success"):
                        pod_logs.append(f"=== Pod: {pod_name} ===\n{logs_result.get('data', '')}")

            return {
                "name": name,
                "namespace": namespace,
                "type": "deployment",
                "status": HealthStatus.UNHEALTHY,
                "ready_replicas": ready_replicas,
                "total_replicas": replicas,
                "error_message": f"Ready: {ready_replicas}/{replicas}",
                "describe_output": describe_output,
                "pod_logs": "\n\n".join(pod_logs),
                "check_duration_ms": (time.time() - start) * 1000,
            }

    except Exception as e:
        return {
            "name": name,
            "namespace": namespace,
            "type": "deployment",
            "status": HealthStatus.UNKNOWN,
            "error_message": str(e),
            "check_duration_ms": (time.time() - start) * 1000,
        }


async def _check_daemonset(
    client,
    name: str,
    namespace: str
) -> Optional[Dict]:
    """
    检查单个 DaemonSet 的健康状态

    Returns:
        ComponentStatus Dict 或 None（如果检查失败）
    """
    start = time.time()

    try:
        # 获取 DaemonSet 状态
        result = await client.get_daemonset(name, namespace)

        if not result.get("success"):
            # 解析错误类型
            error = result.get("error", "")

            if "not found" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "daemonset",
                    "status": HealthStatus.MISSING,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            elif "forbidden" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "daemonset",
                    "status": HealthStatus.PERMISSION_DENIED,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            else:
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "daemonset",
                    "status": HealthStatus.UNKNOWN,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }

        # 解析 DaemonSet 数据
        daemonset_data = result.get("data", {})
        status = daemonset_data.get("status", {})

        number_ready = status.get("numberReady", 0)
        desired_number_scheduled = status.get("desiredNumberScheduled", 0)
        current_number_scheduled = status.get("currentNumberScheduled", 0)
        number_unavailable = status.get("numberUnavailable", 0)

        # 判断健康状态
        is_healthy = (
            number_ready == desired_number_scheduled and
            current_number_scheduled == desired_number_scheduled and
            number_unavailable == 0
        )

        if is_healthy:
            return {
                "name": name,
                "namespace": namespace,
                "type": "daemonset",
                "status": HealthStatus.HEALTHY,
                "ready_replicas": number_ready,
                "total_replicas": desired_number_scheduled,
                "check_duration_ms": (time.time() - start) * 1000,
            }
        else:
            # 不健康：收集 describe 和异常 Pod 的日志
            describe_result = await client.describe_daemonset(name, namespace)
            describe_output = describe_result.get("data", "") if describe_result.get("success") else describe_result.get("error", "")

            # 获取异常 Pod 列表
            pods_result = await client.get_pods(
                namespace=namespace,
                selector=f"app={name}"
            )

            unhealthy_pods = []
            pod_logs = []

            if pods_result.get("success"):
                pods = pods_result.get("data", {}).get("items", [])

                for pod in pods:
                    pod_name = pod.get("metadata", {}).get("name", "")
                    phase = pod.get("status", {}).get("phase", "")
                    restart_count = 0

                    for container in pod.get("status", {}).get("containerStatuses", []):
                        restart_count += container.get("restartCount", 0)

                    # 查找异常 Pod：不是 Running 或重启次数 > 3
                    if phase != "Running" or restart_count > 3:
                        unhealthy_pods.append(pod_name)

                # 取前 3 个异常 Pod
                for pod_name in unhealthy_pods[:3]:
                    # 获取 Pod describe
                    pod_describe_result = await client.describe_pod(namespace, pod_name)
                    pod_describe = pod_describe_result.get("data", "") if pod_describe_result.get("success") else pod_describe_result.get("error", "")

                    # 获取 Pod logs
                    logs_result = await client.get_pod_logs(pod_name, namespace)
                    pod_log = logs_result.get("data", "") if logs_result.get("success") else logs_result.get("error", "")

                    pod_logs.append(f"=== Pod: {pod_name} ===\n{pod_describe}\n\n{pod_log}")

            return {
                "name": name,
                "namespace": namespace,
                "type": "daemonset",
                "status": HealthStatus.UNHEALTHY,
                "ready_replicas": number_ready,
                "total_replicas": desired_number_scheduled,
                "unhealthy_pods": unhealthy_pods,
                "error_message": f"Ready: {number_ready}/{desired_number_scheduled}",
                "describe_output": describe_output,
                "pod_logs": "\n\n".join(pod_logs),
                "check_duration_ms": (time.time() - start) * 1000,
            }

    except Exception as e:
        return {
            "name": name,
            "namespace": namespace,
            "type": "daemonset",
            "status": HealthStatus.UNKNOWN,
            "error_message": str(e),
            "check_duration_ms": (time.time() - start) * 1000,
        }


async def _check_endpoint(
    client,
    name: str,
    namespace: str
) -> Optional[Dict]:
    """
    检查单个 Endpoint 的健康状态

    Returns:
        ComponentStatus Dict 或 None（如果检查失败）
    """
    start = time.time()

    try:
        # 获取 Endpoint 状态
        result = await client.get_endpoints(name, namespace)

        if not result.get("success"):
            # 解析错误类型
            error = result.get("error", "")

            if "not found" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "endpoint",
                    "status": HealthStatus.MISSING,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            elif "forbidden" in error.lower():
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "endpoint",
                    "status": HealthStatus.PERMISSION_DENIED,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }
            else:
                return {
                    "name": name,
                    "namespace": namespace,
                    "type": "endpoint",
                    "status": HealthStatus.UNKNOWN,
                    "error_message": error,
                    "check_duration_ms": (time.time() - start) * 1000,
                }

        # 解析 Endpoint 数据
        endpoint_data = result.get("data", {})
        subsets = endpoint_data.get("subsets", [])

        addresses = []
        not_ready_addresses = []

        for subset in subsets:
            # 可用地址
            for addr in subset.get("addresses", []):
                ip = addr.get("ip", "")
                port = subset.get("ports", [{}])[0].get("port", "") if subset.get("ports") else ""
                if ip and port:
                    addresses.append(f"{ip}:{port}")
                elif ip:
                    addresses.append(ip)

            # 未就绪地址
            for addr in subset.get("notReadyAddresses", []):
                ip = addr.get("ip", "")
                port = subset.get("ports", [{}])[0].get("port", "") if subset.get("ports") else ""
                if ip and port:
                    not_ready_addresses.append(f"{ip}:{port}")
                elif ip:
                    not_ready_addresses.append(ip)

        # 判断健康状态
        is_healthy = (
            len(addresses) >= 1 and  # 至少有1个可用地址
            len(not_ready_addresses) == 0  # 没有未就绪的地址
        )

        if is_healthy:
            return {
                "name": name,
                "namespace": namespace,
                "type": "endpoint",
                "status": HealthStatus.HEALTHY,
                "addresses": addresses,
                "check_duration_ms": (time.time() - start) * 1000,
            }
        else:
            # 不健康：收集 describe
            describe_result = await client.describe_endpoints(name, namespace)
            describe_output = describe_result.get("data", "") if describe_result.get("success") else describe_result.get("error", "")

            return {
                "name": name,
                "namespace": namespace,
                "type": "endpoint",
                "status": HealthStatus.UNHEALTHY,
                "addresses": addresses,
                "not_ready_addresses": not_ready_addresses,
                "error_message": f"Addresses: {len(addresses)}, NotReady: {len(not_ready_addresses)}",
                "describe_output": describe_output,
                "check_duration_ms": (time.time() - start) * 1000,
            }

    except Exception as e:
        return {
            "name": name,
            "namespace": namespace,
            "type": "endpoint",
            "status": HealthStatus.UNKNOWN,
            "error_message": str(e),
            "check_duration_ms": (time.time() - start) * 1000,
        }


async def _execute_with_limit(
    tasks: List,
    max_concurrent: int = 3
) -> List:
    """限制并发数执行任务"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_with_semaphore(task):
        async with semaphore:
            return await task

    return await asyncio.gather(
        *[run_with_semaphore(task) for task in tasks],
        return_exceptions=True
    )


# === 保留原有函数（向后兼容）===

async def _check_controller_health(client) -> Dict:
    """检查 kube-ovn-controller 健康状态"""
    try:
        result = await client.get_pods(
            namespace="kube-system",
            selector="app=kube-ovn-controller"
        )

        if not result.get("success"):
            return {
                "health": "error",
                "error": result.get("error", "Unknown error")
            }

        pods = result["data"].get("items", [])

        total = len(pods)
        ready = sum(1 for p in pods if p.get("status", {}).get("phase") == "Running")

        restarts = 0
        for pod in pods:
            for container in pod.get("status", {}).get("containerStatuses", []):
                restarts += container.get("restartCount", 0)

        if ready == total:
            health = "ok"
        elif ready > 0:
            health = "degraded"
        else:
            health = "error"

        return {
            "total_pods": total,
            "ready_pods": ready,
            "health": health,
            "restarts": restarts
        }

    except Exception as e:
        return {
            "health": "error",
            "error": str(e)
        }


async def _get_pod_summary(client, namespace: str, pod_name: str) -> Dict:
    """获取单个 Pod 概览"""
    try:
        result = await client.get_pod(namespace, pod_name)

        if not result.get("success"):
            return {
                "name": pod_name,
                "namespace": namespace,
                "error": result.get("error", "Unknown error")
            }

        pod = result["data"]
        status = pod.get("status", {})
        spec = pod.get("spec", {})

        return {
            "name": pod.get("metadata", {}).get("name"),
            "namespace": pod.get("metadata", {}).get("namespace"),
            "phase": status.get("phase"),
            "node": spec.get("nodeName"),
            "ip": status.get("podIP"),
            "start_time": status.get("startTime")
        }

    except Exception as e:
        return {
            "name": pod_name,
            "namespace": namespace,
            "error": str(e)
        }


async def _get_cluster_pod_stats(client) -> Dict:
    """获取集群 Pod 统计"""
    try:
        import subprocess

        result = subprocess.run([
            "kubectl", "get", "pods", "-A",
            "-o", "jsonpath={range .items[*]}{.metadata.namespace}{','}{.status.phase}{'\\n'}{end}"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return {
                "total": 0,
                "error": result.stderr
            }

        lines = result.stdout.strip().split('\n') if result.stdout else []

        stats = {
            "total": len(lines),
            "by_phase": {},
            "by_namespace": {}
        }

        for line in lines:
            if not line:
                continue

            parts = line.split(',')
            if len(parts) >= 2:
                ns, phase = parts[0], parts[1]

                stats["by_namespace"][ns] = stats["by_namespace"].get(ns, 0) + 1
                stats["by_phase"][phase] = stats["by_phase"].get(phase, 0) + 1

        return stats

    except Exception as e:
        return {
            "total": 0,
            "error": str(e)
        }


async def _get_subnet_summary(client, namespace: Optional[str]) -> Dict:
    """获取 Subnet 概览"""
    try:
        result = await client.get_subnets()

        if not result.get("success"):
            return {
                "subnets": [],
                "error": result.get("error", "Unknown error")
            }

        subnets = result["data"].get("items", [])

        summary = []
        for subnet in subnets:
            spec = subnet.get("spec", {})
            metadata = subnet.get("metadata", {})

            summary.append({
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "cidr": spec.get("cidr"),
                "available_ips": spec.get("availableIPs", 0),
                "gateway": spec.get("gateway"),
                "gateway_type": spec.get("gatewayType"),
                "status": subnet.get("status", {}).get("conditions", [])
            })

        return {"subnets": summary}

    except Exception as e:
        return {
            "subnets": [],
            "error": str(e)
        }


async def _get_node_network_config(client) -> Dict:
    """获取节点网络配置（MTU）"""
    try:
        import subprocess

        result = subprocess.run([
            "kubectl", "get", "nodes",
            "-o", "jsonpath={range .items[*]}{.metadata.name}{','}{.metadata.annotations.ovn\\.kubernetes\\.io/mtu}{'\\n'}{end}"
        ], capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return {
                "nodes": [],
                "error": result.stderr
            }

        lines = result.stdout.strip().split('\n') if result.stdout else []

        nodes = []
        for line in lines:
            if not line:
                continue

            parts = line.split(',')
            if len(parts) >= 1:
                node_name = parts[0]
                mtu = parts[1] if len(parts) > 1 and parts[1] else None

                nodes.append({
                    "name": node_name,
                    "mtu": int(mtu) if mtu and mtu.isdigit() else None
                })

        return {"nodes": nodes}

    except Exception as e:
        return {
            "nodes": [],
            "error": str(e)
        }
