"""
K8s 资源收集器 - 统一接口

设计理念：
- 供 LLM 动态调用的资源收集工具
- 每个方法专注于一种资源的收集
- 返回结构化数据，便于 LLM 理解
"""

import json
from typing import Dict, List, Optional
from .k8s_client import get_k8s_client


class K8sResourceCollector:
    """K8s 资源收集器 - 统一接口"""

    def __init__(self, context: Optional[str] = None):
        """
        初始化收集器

        Args:
            context: kubeconfig context (可选)
        """
        self.client = get_k8s_client(context=context)
        # ⭐ 新增：缓存节点到 Pod 的映射关系，避免重复查找
        self._node_to_pod_cache: Dict[str, str] = {}

    # === Pod 资源收集 ===

    async def collect_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        tail: int = 100,
        container: Optional[str] = None,
        filter_errors: bool = True
    ) -> Dict:
        """
        收集 Pod 日志

        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            tail: 返回最后 N 行 (默认 100)
            container: 容器名称 (多容器 Pod 必需)
            filter_errors: 是否只保留错误/警告 (默认 True)

        Returns:
            {
                "pod_name": str,
                "namespace": str,
                "logs": List[str],
                "filtered_logs": List[str],
                "error_count": int,
                "warning_count": int,
                "total_lines": int
            }
        """
        result = await self.client.get_pod_logs(
            pod_name=pod_name,
            namespace=namespace,
            tail=tail,
            container=container
        )

        if not result["success"]:
            return {
                "pod_name": pod_name,
                "namespace": namespace,
                "error": result["error"]
            }

        # 解析日志
        logs_text = result["data"]
        logs = logs_text.split('\n') if logs_text else []

        # 过滤日志
        if filter_errors:
            filtered_logs = self._filter_logs(logs)
        else:
            filtered_logs = logs

        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "logs": logs,
            "filtered_logs": filtered_logs,
            "error_count": self._count_errors(filtered_logs),
            "warning_count": self._count_warnings(filtered_logs),
            "total_lines": len(logs)
        }

    async def collect_pod_describe(
        self,
        pod_name: str,
        namespace: str
    ) -> Dict:
        """
        收集 Pod 详细信息 (describe)

        Args:
            pod_name: Pod 名称
            namespace: 命名空间

        Returns:
            {
                "pod_name": str,
                "namespace": str,
                "describe": str,
                "key_info": {
                    "phase": str,
                    "node": str,
                    "ip": str,
                    "start_time": str,
                    "labels": Dict,
                    "annotations": Dict
                }
            }
        """
        # 获取 Pod JSON
        pod_result = await self.client.get_pod(namespace, pod_name)

        if not pod_result["success"]:
            return {
                "pod_name": pod_name,
                "namespace": namespace,
                "error": pod_result["error"]
            }

        pod_data = pod_result["data"]

        # 提取关键信息
        metadata = pod_data.get("metadata", {})
        spec = pod_data.get("spec", {})
        status = pod_data.get("status", {})

        key_info = {
            "phase": status.get("phase"),
            "node": spec.get("nodeName"),
            "ip": status.get("podIP"),
            "start_time": status.get("startTime"),
            "labels": metadata.get("labels", {}),
            "annotations": metadata.get("annotations", {}),
            "restarts": sum(
                cs.get("restartCount", 0)
                for cs in status.get("containerStatuses", [])
            )
        }

        # 获取 describe 文本
        describe_result = await self.client.describe_pod(namespace, pod_name)

        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "describe": describe_result["data"] if describe_result["success"] else "",
            "key_info": key_info
        }

    async def collect_pod_events(
        self,
        pod_name: str,
        namespace: str,
        limit: int = 20,
        filter_warnings: bool = True
    ) -> Dict:
        """
        收集 Pod 事件

        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            limit: 返回最近 N 个事件 (默认 20)
            filter_warnings: 是否只保留警告/错误 (默认 True)

        Returns:
            {
                "pod_name": str,
                "namespace": str,
                "events": List[Dict],
                "warning_count": int,
                "error_count": int,
                "total_events": int
            }
        """
        # 获取事件
        result = await self.client.get_events(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}"
        )

        if not result["success"]:
            return {
                "pod_name": pod_name,
                "namespace": namespace,
                "error": result["error"]
            }

        events_data = result["data"]
        items = events_data.get("items", [])

        # 解析事件
        events = []
        for item in items[:limit]:
            event = {
                "type": item.get("type"),
                "reason": item.get("reason"),
                "message": item.get("message"),
                "timestamp": item.get("lastTimestamp"),
                "count": item.get("count", 1)
            }
            events.append(event)

        # 过滤
        if filter_warnings:
            filtered_events = [
                e for e in events
                if e.get("type") in ["Warning", "Error"]
            ]
        else:
            filtered_events = events

        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "events": filtered_events,
            "warning_count": sum(1 for e in filtered_events if e.get("type") == "Warning"),
            "error_count": sum(1 for e in filtered_events if e.get("type") == "Error"),
            "total_events": len(events)
        }

    # === Subnet 资源收集 ===

    async def collect_subnet_status(
        self,
        subnet_name: Optional[str] = None
    ) -> Dict:
        """
        收集 Subnet CR 状态

        Args:
            subnet_name: 指定子网名称，如果为 None 则收集所有子网

        Returns:
            {
                "subnets": {
                    "subnet_name": {
                        "name": str,
                        "ready": bool,
                        "available_ips": int,
                        "using_ips": int,
                        "status": "healthy" | "warning" | "error",
                        "cidr": str,
                        "gateway": str,
                        "gateway_type": str
                    }
                }
            }
        """
        if subnet_name:
            result = await self.client.get_subnet(subnet_name)
        else:
            result = await self.client.get_subnets()

        if not result["success"]:
            return {"error": result["error"]}

        # 处理单个或多个 Subnet
        if subnet_name:
            items = [result["data"]]
        else:
            items = result["data"].get("items", [])

        subnets = {}
        for item in items:
            name = item["metadata"]["name"]
            spec = item.get("spec", {})
            status = item.get("status", {})

            # 检查 Ready condition
            ready = False
            for cond in status.get("conditions", []):
                if cond.get("type") == "Ready" and cond.get("status") == "True":
                    ready = True
                    break

            # 判断状态
            available = status.get("availableIPs", 0)
            using = status.get("usingIPs", 0)

            if not ready:
                state = "error"
            elif available == 0:
                state = "error"  # IP 耗尽
            elif available < 10:
                state = "warning"  # IP 快耗尽
            else:
                state = "healthy"

            subnets[name] = {
                "name": name,
                "ready": ready,
                "available_ips": available,
                "using_ips": using,
                "status": state,
                "cidr": spec.get("cidr"),
                "gateway": spec.get("gateway"),
                "gateway_type": spec.get("gatewayType"),
                "private": spec.get("private", False),
                "nat_outgoing": spec.get("natOutgoing", False)
            }

        return {"subnets": subnets}

    async def collect_pod_veth_interface(
        self,
        pod_name: str,
        namespace: str
    ) -> Dict:
        """
        查找 Pod 在宿主机上的 veth 网卡

        通过 ovs-vsctl 查找 Pod 对应的 OVS interface，
        然后获取宿主机上的网卡名（xxx_h 格式）。

        Args:
            pod_name: Pod 名称
            namespace: 命名空间

        Returns:
            {
                "pod_name": str,
                "namespace": str,
                "node_name": str,
                "veth_host": str,      # 宿主机上的网卡名，如 "veth_mac1_h"
                "veth_ovs": str,       # OVS 中的网卡名，如 "veth_mac1"
                "ovs_pod": str,        # ovs-ovn Pod 名称
                "pod_nic_type": str,   # Pod 网卡类型
                "success": bool,
                "error": str (如果失败)
            }
        """
        # 1. 获取 Pod 所在节点
        cmd = self.client.kubectl_cmd + [
            "get", "pod", pod_name, "-n", namespace,
            "-o", "jsonpath={.spec.nodeName}"
        ]

        result = await self.client.run(cmd, timeout=10)

        if not result["success"]:
            return {
                "success": False,
                "error": f"获取 Pod 节点失败: {result.get('error', 'Unknown error')}",
                "hint": f"请检查 Pod {namespace}/{pod_name} 是否存在"
            }

        node_name = result["data"].strip()

        if not node_name:
            return {
                "success": False,
                "error": "Pod 节点名称为空",
                "hint": "Pod 可能不在运行状态"
            }

        # 2. 查找 ovs-ovn Pod
        ovs_pod = await self._find_ovs_ovn_pod(node_name)
        if not ovs_pod:
            return {
                "success": False,
                "error": f"在节点 {node_name} 上找不到 ovs-ovn Pod",
                "hint": "检查：1) ovs-ovn DaemonSet 是否正常运行 2) 节点名称是否正确",
                "troubleshooting": f"kubectl get pods -n kube-system -l app=ovs -o wide | grep {node_name}"
            }

        # 3. 获取 Pod 的网卡类型
        cmd = self.client.kubectl_cmd + [
            "get", "pod", pod_name, "-n", namespace,
            "-o", "jsonpath={.metadata.annotations.ovn\\.kubernetes\\.io/pod_nic_type}"
        ]

        result = await self.client.run(cmd, timeout=10)
        pod_nic_type = result["data"].strip() if result["success"] and result["data"] else "veth-pair"

        # 4. 使用 ovs-vsctl 查找 interface
        # 根据 iface-id 查找：iface-id 格式为 podname.namespace
        cmd = self.client.kubectl_cmd + [
            "exec", "-n", "kube-system", ovs_pod, "--",
            "ovs-vsctl", "--data=bare", "--no-heading",
            "--columns=name", "find", "interface",
            f"external-ids:iface-id={pod_name}.{namespace}"
        ]

        result = await self.client.run(cmd, timeout=10)

        if not result["success"]:
            return {
                "success": False,
                "error": f"执行 ovs-vsctl 失败: {result.get('error', 'Unknown error')}",
                "hint": "检查 ovs-ovn Pod 是否正常运行",
                "ovs_pod": ovs_pod,
                "node_name": node_name
            }

        veth_ovs = result["data"].strip()

        if not veth_ovs:
            return {
                "success": False,
                "error": f"未找到 Pod {namespace}/{pod_name} 对应的 OVS interface",
                "hint": "可能原因：1) Pod 网卡未创建 2) Pod 使用 hostNetwork 3) ovs-vsctl 查询条件不匹配",
                "ovs_pod": ovs_pod,
                "node_name": node_name,
                "expected_iface_id": f"{pod_name}.{namespace}"
            }

        # 5. 确定宿主机上的网卡名
        # 在 Kube-OVN 中，OVS interface 名通常已经包含 _h 后缀
        # 例如：OVS 中是 "veth_mac1_h"，宿主机上也是 "veth_mac1_h"
        # 如果 OVS interface 名不以 _h 结尾，则需要添加 _h
        if veth_ovs.endswith("_h"):
            veth_host = veth_ovs
        else:
            veth_host = f"{veth_ovs}_h"

        return {
            "success": True,
            "pod_name": pod_name,
            "namespace": namespace,
            "node_name": node_name,
            "veth_host": veth_host,
            "veth_ovs": veth_ovs,
            "ovs_pod": ovs_pod,
            "pod_nic_type": pod_nic_type,
            "iface_id": f"{pod_name}.{namespace}"
        }

    async def collect_pod_ip(
        self,
        pod_name: str,
        namespace: str
    ) -> Dict:
        """
        收集单个 Pod 的 IP 信息（通过 IP CR）

        IP CR 的命名格式: podname.namespace

        Args:
            pod_name: Pod 名称
            namespace: 命名空间

        Returns:
            {
                "success": True,
                "pod_name": "coredns-674b8bbfcf-5qj4d",
                "namespace": "kube-system",
                "ip": "10.16.0.4",
                "mac": "5a:0a:bd:a2:86:ba",
                "subnet": "ovn-default",
                "node_name": "kube-ovn-control-plane",
                "ip_cr_name": "coredns-674b8bbfcf-5qj4d.kube-system",
                "pod_type": "",  # StatefulSet/VirtualMachine/空
                "container_id": ""
            }

            或失败时:
            {
                "success": False,
                "pod_name": pod_name,
                "namespace": namespace,
                "error": "IP CR not found",
                "error_type": "resource_not_found"
            }
        """
        # IP CR 的命名格式
        ip_cr_name = f"{pod_name}.{namespace}"

        # 获取 IP CR
        result = await self.client.get_ip(ip_cr_name)

        if not result.get("success"):
            error = result.get("error", "")

            # 判断错误类型
            if "not found" in error.lower():
                return {
                    "success": False,
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "ip_cr_name": ip_cr_name,
                    "error": f"IP CR '{ip_cr_name}' 不存在，Pod 可能未分配 IP 或已删除",
                    "error_type": "resource_not_found"
                }
            else:
                return {
                    "success": False,
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "ip_cr_name": ip_cr_name,
                    "error": error,
                    "error_type": "unknown_error"
                }

        # 解析 IP CR 数据
        ip_cr = result.get("data", {})
        spec = ip_cr.get("spec", {})
        metadata = ip_cr.get("metadata", {})

        return {
            "success": True,
            "pod_name": pod_name,
            "namespace": namespace,
            "ip": spec.get("ipAddress"),
            "mac": spec.get("macAddress"),
            "subnet": spec.get("subnet"),
            "node_name": spec.get("nodeName"),
            "ip_cr_name": ip_cr_name,
            "pod_type": spec.get("podName", ""),  # StatefulSet/VirtualMachine
            "container_id": spec.get("containerID", ""),
            "create_time": metadata.get("creationTimestamp")
        }

    # === Node 资源收集 ===

    async def collect_node_info(
        self,
        node_name: Optional[str] = None
    ) -> Dict:
        """
        收集节点信息

        Args:
            node_name: 指定节点名称，如果为 None 则收集所有节点

        Returns:
            {
                "nodes": {
                    "node_name": {
                        "name": str,
                        "ready": bool,
                        "capacity": Dict,
                        "allocatable": Dict,
                        "conditions": List[Dict],
                        "annotations": Dict,
                        "kernel_version": str,
                        "os_image": str
                    }
                }
            }
        """
        result = await self.client.get_nodes()

        if not result["success"]:
            return {"error": result["error"]}

        items = result["data"].get("items", [])

        nodes = {}
        for item in items:
            name = item["metadata"]["name"]

            # 如果指定了节点名称，只返回该节点
            if node_name and name != node_name:
                continue

            status = item.get("status", {})
            metadata = item.get("metadata", {})

            # 检查 Ready 状态
            ready = False
            for cond in status.get("conditions", []):
                if cond.get("type") == "Ready":
                    ready = cond.get("status") == "True"
                    break

            nodes[name] = {
                "name": name,
                "ready": ready,
                "capacity": status.get("capacity", {}),
                "allocatable": status.get("allocatable", {}),
                "conditions": status.get("conditions", []),
                "annotations": metadata.get("annotations", {}),
                "kernel_version": status.get("nodeInfo", {}).get("kernelVersion"),
                "os_image": status.get("nodeInfo", {}).get("osImage"),
                "kubelet_version": status.get("nodeInfo", {}).get("kubeletVersion")
            }

            # 如果只查询单个节点，直接返回
            if node_name:
                return {"nodes": nodes}

        return {"nodes": nodes}

    # === 节点网络配置收集 ===

    async def _find_ovs_ovn_pod(
        self,
        node_name: str
    ) -> Optional[str]:
        """
        查找节点上运行的 ovs-ovn Pod

        通过 kubectl 查找指定节点上的 ovs-ovn Pod，
        支持动态 Pod 命名，不依赖硬编码的命名规则。

        Args:
            node_name: 节点名称

        Returns:
            Pod 名称，找不到返回 None
        """
        # 通过标签选择器和 nodeName 过滤查找
        cmd = self.client.kubectl_cmd + [
            "get", "pods", "-n", "kube-system",
            "-l", "app=ovs",
            "-o", "jsonpath={.items[?(@.spec.nodeName=='" + node_name + "')].metadata.name}"
        ]

        result = await self.client.run(cmd, timeout=10)

        if result["success"] and result["data"]:
            pod_names = result["data"].strip().split()
            if pod_names:
                return pod_names[0]  # 返回第一个匹配的 Pod

        return None

    async def _exec_on_node(
        self,
        node_name: str,
        command: List[str]
    ) -> Dict:
        """
        在节点的 ovs-ovn Pod 上执行命令

        Args:
            node_name: 节点名称
            command: 要执行的命令（列表）

        Returns:
            {
                "success": True,
                "output": str,
                "error": str
            }
        """
        # ⭐ 改进：动态查找 ovs-ovn Pod，支持任意 Pod 命名规则
        # 1. 先尝试从缓存获取
        if node_name not in self._node_to_pod_cache:
            pod_name = await self._find_ovs_ovn_pod(node_name)
            if not pod_name:
                return {
                    "success": False,
                    "error": f"在节点 {node_name} 上找不到 ovs-ovn Pod",
                    "hint": "检查：1) ovs-ovn DaemonSet 是否正常运行 2) 节点名称是否正确",
                    "troubleshooting": "kubectl get pods -n kube-system -l app=ovs -o wide"
                }
            # 缓存 Pod 名称
            self._node_to_pod_cache[node_name] = pod_name

        pod_name = self._node_to_pod_cache[node_name]

        # 2. 使用 kubectl exec 在 Pod 中执行命令
        cmd = self.client.kubectl_cmd + ["exec", "-n", "kube-system", pod_name, "--"] + command

        result = await self.client.run(cmd, timeout=15)

        if not result["success"]:
            # ⭐ 改进：提供更详细的错误信息
            error_msg = result.get("error", "")
            return {
                "success": False,
                "error": error_msg,
                "command": " ".join(cmd),
                "hint": self._get_error_hint(error_msg)
            }

        return {
            "success": True,
            "output": result.get("data", ""),
            "error": result.get("error", "")
        }

    def _get_error_hint(self, error_msg: str) -> str:
        """
        根据错误信息提供故障排除建议

        Args:
            error_msg: 错误信息

        Returns:
            故障排除建议
        """
        if "NotFound" in error_msg:
            return "Pod 不存在或已被删除"
        elif "Connection refused" in error_msg:
            return "Pod 可能正在重启"
        elif "timeout" in error_msg.lower():
            return "命令执行超时，可能系统负载高"
        else:
            return "请检查集群状态和 Pod 日志"

    async def collect_node_ip_addr(
        self,
        node_name: str,
        interface: Optional[str] = None
    ) -> Dict:
        """
        收集节点网络接口信息（ip addr）

        在节点的 ovs-ovn Pod 上执行: ip addr [show dev <interface>]

        Args:
            node_name: 节点名称
            interface: 指定接口（如 ovn0, eth0），留空则显示所有接口

        Returns:
            {
                "success": True,
                "node_name": str,
                "command": "ip addr",
                "output": str,  # 原始输出
                "interfaces": [  # 解析后的接口列表
                    {
                        "name": "eth0",
                        "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
                        "mtu": 1500,
                        "inet": "192.168.1.10/24",
                        "inet6": "fe80::/64"
                    }
                ]
            }
        """
        cmd = ["ip", "addr"]
        if interface:
            cmd.extend(["show", interface])

        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "success": False,
                "node_name": node_name,
                "command": " ".join(cmd),
                "error": result["error"]
            }

        # 解析 ip addr 输出（简化版）
        output = result["output"]
        interfaces = self._parse_ip_addr(output)

        return {
            "success": True,
            "node_name": node_name,
            "command": " ".join(cmd),
            "output": output,
            "interfaces": interfaces
        }

    async def collect_node_ip_route(
        self,
        node_name: str
    ) -> Dict:
        """
        收集节点路由表（ip route）

        在节点的 ovs-ovn Pod 上执行: ip route show

        Args:
            node_name: 节点名称

        Returns:
            {
                "success": True,
                "node_name": str,
                "command": "ip route",
                "output": str,
                "routes": [  # 解析后的路由列表
                    {
                        "destination": "10.16.0.0/16",
                        "gateway": None,
                        "dev": "ovn0",
                        "scope": "link"
                    }
                ]
            }
        """
        cmd = ["ip", "route", "show"]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "success": False,
                "node_name": node_name,
                "command": " ".join(cmd),
                "error": result["error"]
            }

        output = result["output"]
        routes = self._parse_ip_route(output)

        return {
            "success": True,
            "node_name": node_name,
            "command": " ".join(cmd),
            "output": output,
            "routes": routes
        }

    async def collect_node_iptables(
        self,
        node_name: str,
        table: str = "filter"
    ) -> Dict:
        """
        收集节点 iptables/nftables 规则

        在节点的 ovs-ovn Pod 上执行: iptables-save -t <table>

        Args:
            node_name: 节点名称
            table: 表名（filter/nat/mangle/raw）

        Returns:
            {
                "success": True,
                "node_name": str,
                "table": str,
                "backend": "iptables" | "nftables",
                "command": str,
                "output": str,
                "rules_count": int
            }
        """
        # 先检测是 iptables 还是 nftables
        check_cmd = ["which", "iptables"]
        check_result = await self._exec_on_node(node_name, check_cmd)

        if check_result["success"]:
            # 使用 iptables
            cmd = ["iptables-save", "-t", table]
            backend = "iptables"
        else:
            # 使用 nftables
            cmd = ["nft", "list", "table", "ip", table]
            backend = "nftables"

        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "success": False,
                "node_name": node_name,
                "table": table,
                "command": " ".join(cmd),
                "error": result["error"]
            }

        output = result["output"]
        rules_count = len([line for line in output.split("\n") if line.startswith("-A")])

        return {
            "success": True,
            "node_name": node_name,
            "table": table,
            "backend": backend,
            "command": " ".join(cmd),
            "output": output,
            "rules_count": rules_count
        }

    async def collect_node_ipvs(
        self,
        node_name: str
    ) -> Dict:
        """
        收集节点 IPVS 配置

        在节点的 ovs-ovn Pod 上执行: ipvsadm -Ln

        Args:
            node_name: 节点名称

        Returns:
            {
                "success": True,
                "node_name": str,
                "command": "ipvsadm -Ln",
                "output": str,
                "virtual_servers": int  # IP 虚拟服务器数量
            }
        """
        cmd = ["ipvsadm", "-Ln"]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "success": False,
                "node_name": node_name,
                "command": " ".join(cmd),
                "error": result["error"]
            }

        output = result["output"]
        # 简单统计（以 TCP/UDP 开头的行）
        virtual_servers = len([line for line in output.split("\n") if line.strip().startswith(("TCP", "UDP"))])

        return {
            "success": True,
            "node_name": node_name,
            "command": " ".join(cmd),
            "output": output,
            "virtual_servers": virtual_servers
        }

    async def collect_node_sysctl(
        self,
        node_name: str,
        parameters: Optional[List[str]] = None
    ) -> Dict:
        """
        收集节点内核参数（sysctl）

        在节点的 ovs-ovn Pod 上执行: sysctl <param>

        常用网络参数:
        - net.ipv4.ip_forward
        - net.ipv4.conf.all.rp_filter
        - net.bridge.bridge-nf-call-iptables
        - net.ipv4.conf.all.forwarding

        Args:
            node_name: 节点名称
            parameters: 参数列表，留空则收集常用网络参数

        Returns:
            {
                "success": True,
                "node_name": str,
                "parameters": {
                    "net.ipv4.ip_forward": "1",
                    "net.ipv4.conf.all.rp_filter": "0"
                }
            }
        """
        # 默认收集的网络参数
        if not parameters:
            parameters = [
                "net.ipv4.ip_forward",
                "net.ipv4.conf.all.rp_filter",
                "net.ipv4.conf.all.forwarding",
                "net.bridge.bridge-nf-call-iptables",
                "net.bridge.bridge-nf-call-ip6tables",
                "net.ipv4.neigh.default.gc_thresh1",
                "net.ipv4.neigh.default.gc_thresh2",
                "net.ipv4.neigh.default.gc_thresh3"
            ]

        sysctl_results = {}
        for param in parameters:
            cmd = ["sysctl", param]
            result = await self._exec_on_node(node_name, cmd)

            if result["success"]:
                # 解析输出: net.ipv4.ip_forward = 1
                output = result["output"].strip()
                if "=" in output:
                    key, value = output.split("=", 1)
                    sysctl_results[key.strip()] = value.strip()
            else:
                sysctl_results[param] = f"<error: {result['error']}>"

        return {
            "success": True,
            "node_name": node_name,
            "parameters": sysctl_results
        }

    def _parse_ip_addr(self, output: str) -> List[Dict]:
        """
        解析 ip addr 输出

        简化版解析，提取关键字段
        """
        import re

        interfaces = []
        current_interface = None

        for line in output.split("\n"):
            # 匹配接口行: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ..."
            match = re.match(r'^\d+:\s+(\S+):\s+<([^>]+)>\s+mtu\s+(\d+)', line)
            if match:
                if current_interface:
                    interfaces.append(current_interface)

                current_interface = {
                    "name": match.group(1),
                    "flags": match.group(2).split(","),
                    "mtu": int(match.group(3)),
                    "inet": None,
                    "inet6": None
                }
            elif current_interface:
                # 匹配 IP 地址: "    inet 192.168.1.10/24 brd ..."
                if "inet" in line and current_interface["inet"] is None:
                    inet_match = re.search(r'inet\s+([\d./]+)', line)
                    if inet_match:
                        current_interface["inet"] = inet_match.group(1)

                # 匹配 IPv6 地址: "    inet6 fe80::/64 ..."
                if "inet6" in line and current_interface["inet6"] is None:
                    inet6_match = re.search(r'inet6\s+([\d./]+)', line)
                    if inet6_match:
                        current_interface["inet6"] = inet6_match.group(1)

        if current_interface:
            interfaces.append(current_interface)

        return interfaces

    def _parse_ip_route(self, output: str) -> List[Dict]:
        """
        解析 ip route 输出

        简化版解析
        """
        import re

        routes = []
        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 解析路由行: "10.16.0.0/16 dev ovn0 scope link src 10.16.0.2"
            route = {
                "raw": line
            }

            # 提取目标网络
            match = re.match(r'^([\d./]+|default)', line)
            if match:
                route["destination"] = match.group(1)

            # 提取网关
            gw_match = re.search(r'via\s+([\d.]+)', line)
            if gw_match:
                route["gateway"] = gw_match.group(1)

            # 提取设备
            dev_match = re.search(r'dev\s+(\S+)', line)
            if dev_match:
                route["dev"] = dev_match.group(1)

            # 提取 scope
            scope_match = re.search(r'scope\s+(\S+)', line)
            if scope_match:
                route["scope"] = scope_match.group(1)

            routes.append(route)

        return routes

    # === Controller 资源收集 ===

    async def collect_kube_ovn_controller_logs(
        self,
        tail: int = 100
    ) -> Dict:
        """
        收集 kube-ovn-controller 日志 (通过 kubectl logs)

        kube-ovn-controller 是 Deployment,运行在 kube-system namespace

        Args:
            tail: 返回最后 N 行 (默认 100)

        Returns:
            {
                "component": "kube-ovn-controller",
                "type": "pod_logs",
                "logs": List[str],
                "filtered_logs": List[str],
                "error_count": int,
                "warning_count": int
            }
        """
        result = await self.client.get_controller_logs(tail=tail)

        if not result["success"]:
            return {
                "component": "kube-ovn-controller",
                "type": "pod_logs",
                "error": result["error"]
            }

        logs_text = result["data"]
        logs = logs_text.split('\n') if logs_text else []

        filtered_logs = self._filter_logs(logs)

        return {
            "component": "kube-ovn-controller",
            "type": "pod_logs",
            "logs": logs,
            "filtered_logs": filtered_logs,
            "error_count": self._count_errors(filtered_logs),
            "warning_count": self._count_warnings(filtered_logs)
        }

    async def collect_kube_ovn_cni_logs(
        self,
        node_name: str,
        tail: int = 100
    ) -> Dict:
        """
        收集 kube-ovn-cni 日志 (从节点 /var/log/kube-ovn/)

        kube-ovn-cni 是 DaemonSet,日志在节点文件系统中
        日志路径: /var/log/kube-ovn/*.log

        Args:
            node_name: 节点名称
            tail: 返回每个日志文件的最后 N 行 (默认 100)

        Returns:
            {
                "component": "kube-ovn-cni",
                "type": "node_file_logs",
                "node_name": str,
                "log_files": {
                    "kube-ovn-cni.log": {
                        "path": "/var/log/kube-ovn/kube-ovn-cni.log",
                        "tail_lines": List[str],
                        "error_count": int,
                        "warning_count": int
                    },
                    ...
                }
            }
        """
        # 日志目录
        log_dir = "/var/log/kube-ovn"

        # 获取日志文件列表
        cmd = ["ls", log_dir]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "component": "kube-ovn-cni",
                "type": "node_file_logs",
                "node_name": node_name,
                "error": f"无法访问日志目录 {log_dir}: {result.get('error')}"
            }

        log_files = result["output"].strip().split('\n')
        log_files = [f for f in log_files if f.endswith('.log')]

        if not log_files:
            return {
                "component": "kube-ovn-cni",
                "type": "node_file_logs",
                "node_name": node_name,
                "error": f"日志目录 {log_dir} 中没有找到 .log 文件"
            }

        # 收集每个日志文件的 tail
        logs_data = {}
        for log_file in log_files:
            log_path = f"{log_dir}/{log_file}"

            # tail -n <tail> <log_path>
            cmd = ["tail", "-n", str(tail), log_path]
            file_result = await self._exec_on_node(node_name, cmd)

            if file_result["success"]:
                lines = file_result["output"].strip().split('\n')
                filtered = self._filter_logs(lines)

                logs_data[log_file] = {
                    "path": log_path,
                    "tail_lines": lines,
                    "filtered_logs": filtered,
                    "error_count": self._count_errors(filtered),
                    "warning_count": self._count_warnings(filtered)
                }
            else:
                logs_data[log_file] = {
                    "path": log_path,
                    "error": file_result.get("error")
                }

        return {
            "component": "kube-ovn-cni",
            "type": "node_file_logs",
            "node_name": node_name,
            "log_directory": log_dir,
            "log_files": logs_data
        }

    async def collect_ovn_controller_logs(
        self,
        node_name: str,
        tail: int = 100
    ) -> Dict:
        """
        收集 ovn-controller 日志 (从节点 /var/log/ovn/)

        ovn-controller 是 OVN 主控制进程,日志在节点文件系统中
        日志路径: /var/log/ovn/ovn-controller.log

        Args:
            node_name: 节点名称
            tail: 返回最后 N 行 (默认 100)

        Returns:
            {
                "component": "ovn-controller",
                "type": "node_file_logs",
                "node_name": str,
                "log_path": str,
                "tail_lines": List[str],
                "error_count": int,
                "warning_count": int
            }
        """
        log_path = "/var/log/ovn/ovn-controller.log"

        cmd = ["tail", "-n", str(tail), log_path]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "component": "ovn-controller",
                "type": "node_file_logs",
                "node_name": node_name,
                "log_path": log_path,
                "error": result.get("error")
            }

        lines = result["output"].strip().split('\n')
        filtered = self._filter_logs(lines)

        return {
            "component": "ovn-controller",
            "type": "node_file_logs",
            "node_name": node_name,
            "log_path": log_path,
            "tail_lines": lines,
            "filtered_logs": filtered,
            "error_count": self._count_errors(filtered),
            "warning_count": self._count_warnings(filtered)
        }

    async def collect_ovn_northd_logs(
        self,
        node_name: str,
        tail: int = 100
    ) -> Dict:
        """
        收集 ovn-northd 日志 (从节点 /var/log/ovn/)

        ovn-northd 是 OVN Northbound 守护进程,日志在节点文件系统中
        日志路径: /var/log/ovn/ovn-northd.log

        Args:
            node_name: 节点名称
            tail: 返回最后 N 行 (默认 100)

        Returns:
            {
                "component": "ovn-northd",
                "type": "node_file_logs",
                "node_name": str,
                "log_path": str,
                "tail_lines": List[str],
                "error_count": int,
                "warning_count": int
            }
        """
        log_path = "/var/log/ovn/ovn-northd.log"

        cmd = ["tail", "-n", str(tail), log_path]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "component": "ovn-northd",
                "type": "node_file_logs",
                "node_name": node_name,
                "log_path": log_path,
                "error": result.get("error")
            }

        lines = result["output"].strip().split('\n')
        filtered = self._filter_logs(lines)

        return {
            "component": "ovn-northd",
            "type": "node_file_logs",
            "node_name": node_name,
            "log_path": log_path,
            "tail_lines": lines,
            "filtered_logs": filtered,
            "error_count": self._count_errors(filtered),
            "warning_count": self._count_warnings(filtered)
        }

    async def collect_ovs_vswitchd_logs(
        self,
        node_name: str,
        tail: int = 100
    ) -> Dict:
        """
        收集 ovs-vswitchd 日志 (从节点 /var/log/openvswitch/)

        ovs-vswitchd 是 Open vSwitch 交换机守护进程,日志在节点文件系统中
        日志路径: /var/log/openvswitch/ovs-vswitchd.log

        Args:
            node_name: 节点名称
            tail: 返回最后 N 行 (默认 100)

        Returns:
            {
                "component": "ovs-vswitchd",
                "type": "node_file_logs",
                "node_name": str,
                "log_path": str,
                "tail_lines": List[str],
                "error_count": int,
                "warning_count": int
            }
        """
        log_path = "/var/log/openvswitch/ovs-vswitchd.log"

        cmd = ["tail", "-n", str(tail), log_path]
        result = await self._exec_on_node(node_name, cmd)

        if not result["success"]:
            return {
                "component": "ovs-vswitchd",
                "type": "node_file_logs",
                "node_name": node_name,
                "log_path": log_path,
                "error": result.get("error")
            }

        lines = result["output"].strip().split('\n')
        filtered = self._filter_logs(lines)

        return {
            "component": "ovs-vswitchd",
            "type": "node_file_logs",
            "node_name": node_name,
            "log_path": log_path,
            "tail_lines": lines,
            "filtered_logs": filtered,
            "error_count": self._count_errors(filtered),
            "warning_count": self._count_warnings(filtered)
        }

    # === OVN/OVS 诊断命令 ===

    async def collect_ovn_nbctl(
        self,
        command: str
    ) -> Dict:
        """
        执行 ovn-nbctl 命令 (OVN Northbound 数据库操作)

        ⭐ 增强：自动纠正常见的表名错误，提供友好的错误提示

        常用命令:
        - list Logical_Router: 列出所有逻辑路由器（可简写为 LR，会自动纠正）
        - list Logical_Switch: 列出所有逻辑交换机（可简写为 LS，会自动纠正）
        - list NAT: 列出所有 NAT 规则
        - show <resource>: 显示资源详情

        执行方式: kubectl-ko nbctl <options>

        Args:
            command: ovn-nbctl 命令参数 (例如: "list Logical_Router" 或 "list LR")

        Returns:
            {
                "component": "ovn-nbctl",
                "command": str,
                "original_command": str,  # 原始命令（如果自动纠正）
                "output": str,
                "success": bool,
                "error": str (如果失败),
                "suggestion": str (如果表名错误),
                "valid_tables": list (列出有效的表名)
            }
        """
        import re

        # 表名映射：简写 -> 完整名称
        table_aliases = {
            "LR": "Logical_Router",
            "LS": "Logical_Switch",
            "LSP": "Logical_Switch_Port",
            "LRP": "Logical_Router_Port",
            "ACL": "ACL",
            "NAT": "NAT",
            "LB": "Load_Balancer",
            "LBF": "Load_Balancer_Flow",
            "PG": "Port_Group",
            "CG": "Chassis_Group",
            "BFD": "BFD",
        }

        # 有效的表名列表（用于错误提示）
        valid_tables = [
            "Logical_Router", "Logical_Switch", "Logical_Switch_Port",
            "Logical_Router_Port", "ACL", "NAT", "Load_Balancer",
            "Load_Balancer_Flow", "Port_Group", "Chassis_Group",
            "BFD", "Connection", "DNS", "DHCP_Options", "DHCPv6_Options",
            "Meter", "Meter_Band", "Static_MAC_Binding", "Gateway_Chassis"
        ]

        original_command = command

        # 自动替换简写表名
        for alias, full_name in table_aliases.items():
            # 使用单词边界匹配，避免部分匹配
            pattern = r"\b" + alias + r"\b"
            if re.search(pattern, command):
                command = re.sub(pattern, full_name, command)
                break

        cmd = self.client.ko_cmd + ["nbctl"] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            error_msg = result.get("error", "")

            # 检测 "unknown table" 错误
            if "unknown table" in error_msg:
                # 提取错误的表名
                match = re.search(r'unknown table "([^"]+)"', error_msg)
                if match:
                    wrong_table = match.group(1)

                    # 尝试提供正确的表名建议
                    suggestion = None

                    # 检查是否是常见的简写错误
                    for alias, full_name in table_aliases.items():
                        if wrong_table == alias:
                            suggestion = f"表名 '{wrong_table}' 是简写，应该使用完整名称 '{full_name}'"
                            corrected_command = original_command.replace(wrong_table, full_name)
                            break

                    if not suggestion:
                        # 查找相似的表名
                        import difflib
                        similar_tables = difflib.get_close_matches(
                            wrong_table,
                            valid_tables,
                            n=3,
                            cutoff=0.6
                        )

                        if similar_tables:
                            suggestion = f"表名 '{wrong_table}' 不正确，您是否想使用：{', '.join(similar_tables)}"
                            corrected_command = original_command.replace(wrong_table, similar_tables[0])
                        else:
                            suggestion = f"表名 '{wrong_table}' 不存在，请检查表名拼写"
                            corrected_command = None

                    return {
                        "component": "ovn-nbctl",
                        "command": command,
                        "original_command": original_command,
                        "error": error_msg,
                        "success": False,
                        "hint": suggestion,
                        "suggestion": corrected_command,
                        "valid_tables": valid_tables
                    }

            # 其他错误
            return {
                "component": "ovn-nbctl",
                "command": command,
                "original_command": original_command,
                "error": error_msg,
                "success": False,
                "valid_tables": valid_tables
            }

        return {
            "component": "ovn-nbctl",
            "command": command,
            "original_command": original_command if command != original_command else None,
            "output": result.get("data", ""),
            "success": True,
            "auto_corrected": command != original_command  # 是否自动纠正
        }

    async def collect_ovn_sbctl(
        self,
        command: str
    ) -> Dict:
        """
        执行 ovn-sbctl 命令 (OVN Southbound 数据库操作)

        常用命令:
        - list Chassis: 列出所有机箱
        - list datapath: 列出所有数据路径
        - show <resource>: 显示资源详情

        执行方式: kubectl-ko sbctl <options>

        Args:
            command: ovn-sbctl 命令参数 (例如: "list Chassis" 或 "show datapath1")

        Returns:
            {
                "component": "ovn-sbctl",
                "command": str,
                "output": str,
                "success": bool,
                "error": str (如果失败)
            }
        """
        cmd = self.client.ko_cmd + ["sbctl"] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            return {
                "component": "ovn-sbctl",
                "command": command,
                "error": result.get("error"),
                "success": False
            }

        return {
            "component": "ovn-sbctl",
            "command": command,
            "output": result.get("data", ""),
            "success": True
        }

    async def collect_ovs_vsctl(
        self,
        node_name: str,
        command: str
    ) -> Dict:
        """
        执行 ovs-vsctl 命令 (OVS 交换机配置)

        常用命令:
        - show: 显示 OVS 配置摘要
        - list bridge: 列出所有网桥
        - list port: 列出所有端口

        执行方式: kubectl-ko vsctl {nodeName} [options]

        Args:
            node_name: 节点名称
            command: ovs-vsctl 命令参数 (例如: "show" 或 "list bridge")

        Returns:
            {
                "component": "ovs-vsctl",
                "node_name": str,
                "command": str,
                "output": str,
                "success": bool,
                "error": str (如果失败)
            }
        """
        cmd = self.client.ko_cmd + ["vsctl", node_name] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            return {
                "component": "ovs-vsctl",
                "node_name": node_name,
                "command": command,
                "error": result.get("error"),
                "success": False
            }

        return {
            "component": "ovs-vsctl",
            "node_name": node_name,
            "command": command,
            "output": result.get("data", ""),
            "success": True
        }

    async def collect_ovs_ofctl(
        self,
        node_name: str,
        command: str
    ) -> Dict:
        """
        执行 ovs-ofctl 命令 (OpenFlow 协议诊断)

        常用命令:
        - dump-flows: 转储流表
        - dump-ports: 转储端口统计
        - show: 显示交换机信息

        执行方式: kubectl-ko ofctl {nodeName} [options]

        Args:
            node_name: 节点名称
            command: ovs-ofctl 命令参数 (例如: "dump-flows br-int")

        Returns:
            {
                "component": "ovs-ofctl",
                "node_name": str,
                "command": str,
                "output": str,
                "success": bool,
                "error": str (如果失败)
            }
        """
        cmd = self.client.ko_cmd + ["ofctl", node_name] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            return {
                "component": "ovs-ofctl",
                "node_name": node_name,
                "command": command,
                "error": result.get("error"),
                "success": False
            }

        return {
            "component": "ovs-ofctl",
            "node_name": node_name,
            "command": command,
            "output": result.get("data", ""),
            "success": True
        }

    async def collect_ovs_dpctl(
        self,
        node_name: str,
        command: str
    ) -> Dict:
        """
        执行 ovs-dpctl 命令 (OVS 数据路径诊断)

        常用命令:
        - show: 显示数据路径统计
        - dump-flows: 转储数据路径流表
        - dump-conntrack: 转储连接跟踪表

        执行方式: kubectl-ko dpctl {nodeName} [options]

        Args:
            node_name: 节点名称
            command: ovs-dpctl 命令参数 (例如: "show" 或 "dump-flows")

        Returns:
            {
                "component": "ovs-dpctl",
                "node_name": str,
                "command": str,
                "output": str,
                "success": bool,
                "error": str (如果失败)
            }
        """
        cmd = self.client.ko_cmd + ["dpctl", node_name] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            return {
                "component": "ovs-dpctl",
                "node_name": node_name,
                "command": command,
                "error": result.get("error"),
                "success": False
            }

        return {
            "component": "ovs-dpctl",
            "node_name": node_name,
            "command": command,
            "output": result.get("data", ""),
            "success": True
        }

    async def collect_ovs_appctl(
        self,
        node_name: str,
        target: str,
        command: str
    ) -> Dict:
        """
        执行 ovs-appctl 命令 (OVS 守护进程控制)

        常用命令:
        - ovs-vswitchd/dpctl/show: 显示数据路径统计
        - ovs-vswitchd/coverage/show: 显示覆盖范围统计

        执行方式: kubectl-ko appctl {nodeName} [options]

        Args:
            node_name: 节点名称
            target: 目标守护进程 (例如: "ovs-vswitchd")
            command: ovs-appctl 命令参数 (例如: "dpctl/show")

        Returns:
            {
                "component": "ovs-appctl",
                "node_name": str,
                "target": str,
                "command": str,
                "output": str,
                "success": bool,
                "error": str (如果失败)
            }
        """
        cmd = self.client.ko_cmd + ["appctl", node_name, target] + command.split()

        result = await self.client.run(cmd, timeout=30)

        if not result["success"]:
            return {
                "component": "ovs-appctl",
                "node_name": node_name,
                "target": target,
                "command": command,
                "error": result.get("error"),
                "success": False
            }

        return {
            "component": "ovs-appctl",
            "node_name": node_name,
            "target": target,
            "command": command,
            "output": result.get("data", ""),
            "success": True
        }

    async def collect_tcpdump(
        self,
        pod_name: str,
        namespace: str,
        count: int = 10,
        filter_expr: Optional[str] = None,
        timeout: int = 30,
        use_legacy_kubectl_ko: bool = False
    ) -> Dict:
        """
        捕获 Pod 流量 (tcpdump)

        ⭐ 新实现：自动查找 Pod 的 veth 网卡，在 ovs-ovn Pod 上直接执行 tcpdump，
        通过 timeout 命令控制超时，避免无限等待。

        Args:
            pod_name: Pod 名称
            namespace: 命名空间
            count: 捕获的数据包数量 (默认 10)
            filter_expr: tcpdump 过滤表达式 (例如: "port 80" 或 "icmp")
            timeout: 超时时间（秒），默认 30 秒
            use_legacy_kubectl_ko: 是否使用旧的 kubectl-ko 方式（不推荐，用于兼容）

        Returns:
            {
                "component": "tcpdump",
                "pod_name": str,
                "namespace": str,
                "method": str,  # "direct" 或 "kubectl-ko"
                "veth_interface": str,  # 使用的网卡名（direct 模式）
                "command": str,
                "output": str,
                "packet_count": int,
                "timeout_reached": bool,  # 是否超时
                "success": bool,
                "error": str (如果失败)
            }
        """
        # 如果用户明确要求使用旧方式
        if use_legacy_kubectl_ko:
            return await self._tcpdump_legacy(
                pod_name, namespace, count, filter_expr, timeout
            )

        # 新方式：自动查找 veth 网卡
        try:
            # 1. 查找 veth 网卡
            veth_info = await self.collect_pod_veth_interface(
                pod_name, namespace
            )

            if not veth_info["success"]:
                return {
                    "component": "tcpdump",
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "error": veth_info.get("error"),
                    "hint": "查找 Pod veth 网卡失败，请检查 Pod 是否运行",
                    "success": False
                }

            veth_host = veth_info["veth_host"]
            ovs_pod = veth_info["ovs_pod"]

            # 2. 构建命令：使用 timeout 控制超时
            # 命令格式: timeout <timeout>s tcpdump -i <interface> -c <count> -nn [filter]
            tcpdump_cmd = [
                "timeout", f"{timeout}s",
                "tcpdump", "-i", veth_host,
                "-c", str(count),
                "-nn"  # 不解析主机名和端口名
            ]

            if filter_expr:
                tcpdump_cmd.append(filter_expr)

            # 3. 在 ovs-ovn Pod 上执行
            cmd = self.client.kubectl_cmd + [
                "exec", "-n", "kube-system", ovs_pod, "--"
            ] + tcpdump_cmd

            result = await self.client.run(cmd, timeout=timeout + 10)

            # 4. 处理结果
            if not result["success"]:
                error_msg = result.get("error", "")

                # 检查是否是 timeout 导致的
                # timeout 命令超时返回 exit code 124
                # 错误消息格式: "command terminated with exit code 124"
                is_timeout = (
                    "exit code 124" in error_msg or
                    "timeout" in error_msg.lower() or
                    "Terminated" in error_msg
                )

                if is_timeout:
                    # timeout 退出，说明已捕获了一些包或没有流量
                    # 从 error 消息中提取 tcpdump 输出（如果有的话）
                    output_lines = error_msg.split('\n')
                    tcpdump_output = []

                    # tcpdump 的输出通常在 "listening on" 和 "command terminated" 之间
                    capturing = False
                    for line in output_lines:
                        if "listening on" in line:
                            capturing = True
                            continue
                        if "command terminated" in line:
                            break
                        if capturing:
                            tcpdump_output.append(line)

                    output = '\n'.join(tcpdump_output).strip()
                    packet_count = output.count('\n') if output else 0

                    return {
                        "component": "tcpdump",
                        "pod_name": pod_name,
                        "namespace": namespace,
                        "method": "direct",
                        "veth_interface": veth_host,
                        "ovs_pod": ovs_pod,
                        "command": " ".join(cmd),
                        "output": output,
                        "packet_count": packet_count,
                        "timeout_reached": True,
                        "success": True,
                        "hint": f"在 {timeout} 秒内捕获了 {packet_count} 个数据包（可能未达到 {count} 个）。可能原因：1) 网络流量少 2) 过滤器不匹配 3) 超时时间太短"
                    }

                return {
                    "component": "tcpdump",
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "error": error_msg,
                    "command": " ".join(cmd),
                    "success": False,
                    "hint": "tcpdump 执行失败，请检查网卡名和权限",
                    "veth_interface": veth_host
                }

            output = result.get("data", "")
            packet_count = output.count('\n') if output else 0

            return {
                "component": "tcpdump",
                "pod_name": pod_name,
                "namespace": namespace,
                "method": "direct",
                "veth_interface": veth_host,
                "ovs_pod": ovs_pod,
                "command": " ".join(cmd),
                "output": output,
                "packet_count": packet_count,
                "timeout_reached": False,
                "success": True
            }

        except Exception as e:
            return {
                "component": "tcpdump",
                "pod_name": pod_name,
                "namespace": namespace,
                "error": f"执行异常: {str(e)}",
                "success": False,
                "hint": "请检查集群状态和网络配置"
            }

    async def _tcpdump_legacy(
        self,
        pod_name: str,
        namespace: str,
        count: int,
        filter_expr: Optional[str],
        timeout: int
    ) -> Dict:
        """
        旧的 kubectl-ko tcpdump 方式（保留用于兼容）

        ⚠️ 不推荐：这种方式可能超时无法打断
        """
        cmd = self.client.ko_cmd + ["tcpdump", f"{namespace}/{pod_name}", "-c", str(count)]

        if filter_expr:
            cmd.append(filter_expr)

        result = await self.client.run(cmd, timeout=timeout)

        if not result["success"]:
            error_msg = result.get("error", "")
            return {
                "component": "tcpdump",
                "pod_name": pod_name,
                "namespace": namespace,
                "error": error_msg,
                "command": " ".join(cmd),
                "success": False,
                "method": "kubectl-ko",
                "hint": "kubectl-ko tcpdump 超时或失败。建议使用默认的 direct 方式",
                "note": "可以通过 use_legacy_kubectl_ko=False 使用新的 direct 方式"
            }

        output = result.get("data", "")
        packet_count = output.count('\n') if output else 0

        return {
            "component": "tcpdump",
            "pod_name": pod_name,
            "namespace": namespace,
            "method": "kubectl-ko",
            "command": " ".join(cmd),
            "output": output,
            "packet_count": packet_count,
            "success": True
        }

    async def collect_node_tcpdump(
        self,
        node_name: str,
        interface: str,
        count: int = 10,
        filter_expr: Optional[str] = None,
        timeout: int = 30
    ) -> Dict:
        """
        在节点的指定网卡上抓包 (tcpdump)

        ⭐ **使用场景**: 验证流量是否真正离开节点，用于诊断外部网络问题

        💡 **诊断工作流**:
        1. 使用 ovn-trace 确定流路径
        2. 在 Pod veth 上抓包（验证流量离开 Pod）
        3. 在节点物理网卡上抓包（此工具，验证流量离开节点）
        4. 判断: 如果包离开节点但无回复 → 外部网络问题

        Args:
            node_name: 节点名称
            interface: 网卡名称（例如: eth0, ens33, ovn0）
            count: 捕获的数据包数量 (默认 10)
            filter_expr: tcpdump 过滤表达式 (例如: "icmp", "host 8.8.8.8")
            timeout: 超时时间（秒），默认 30 秒

        Returns:
            {
                "component": "node_tcpdump",
                "node_name": str,
                "interface": str,
                "command": str,
                "output": str,
                "packet_count": int,
                "timeout_reached": bool,
                "success": bool,
                "error": str (如果失败)
            }
        """
        try:
            # 1. 获取节点上的 ovs-ovn Pod（用于执行 tcpdump）
            # 获取节点上所有 kube-system 命名空间的 Pod
            cmd = self.client.kubectl_cmd + [
                "get", "pods", "-n", "kube-system",
                "-l", "app=ovs",
                "-o", "jsonpath={.items[?(@.spec.nodeName=='" + node_name + "')].metadata.name}",
                "--field-selector", f"spec.nodeName={node_name}"
            ]

            result = await self.client.run(cmd, timeout=10)

            if not result["success"]:
                return {
                    "component": "node_tcpdump",
                    "node_name": node_name,
                    "interface": interface,
                    "error": f"获取节点 {node_name} 的 ovs Pod 失败: {result.get('error')}",
                    "success": False
                }

            ovs_pod = result.get("data", "").strip()

            if not ovs_pod:
                return {
                    "component": "node_tcpdump",
                    "node_name": node_name,
                    "interface": interface,
                    "error": f"节点 {node_name} 上没有找到 ovs-ovn Pod",
                    "success": False
                }

            # 2. 构建命令：使用 timeout 控制超时
            # 命令格式: timeout <timeout>s tcpdump -i <interface> -c <count> -nn [filter]
            tcpdump_cmd = [
                "timeout", f"{timeout}s",
                "tcpdump", "-i", interface,
                "-c", str(count),
                "-nn"  # 不解析主机名和端口名
            ]

            if filter_expr:
                tcpdump_cmd.append(filter_expr)

            # 3. 在 ovs-ovn Pod 上执行（使用 hostNetwork 访问节点网卡）
            cmd = self.client.kubectl_cmd + [
                "exec", "-n", "kube-system", ovs_pod, "--"
            ] + tcpdump_cmd

            result = await self.client.run(cmd, timeout=timeout + 10)

            # 4. 处理结果
            if not result["success"]:
                error_msg = result.get("error", "")

                # 检查是否是 timeout 导致的
                is_timeout = (
                    "exit code 124" in error_msg or
                    "timeout" in error_msg.lower() or
                    "Terminated" in error_msg
                )

                if is_timeout:
                    # timeout 退出，说明已捕获了一些包或没有流量
                    # 从 error 消息中提取 tcpdump 输出
                    output_lines = error_msg.split('\n')
                    # 提取 tcpdump 的输出（通常在前面部分）
                    output = '\n'.join(
                        line for line in output_lines
                        if line and not line.startswith('command') and 'exit code' not in line
                    )
                    packet_count = output.count('\n') if output else 0

                    return {
                        "component": "node_tcpdump",
                        "node_name": node_name,
                        "interface": interface,
                        "command": " ".join(tcpdump_cmd),
                        "output": output,
                        "packet_count": packet_count,
                        "timeout_reached": True,
                        "success": True,
                        "note": f"在 {timeout} 秒内未捕获到 {count} 个包（捕获了 {packet_count} 个）"
                    }
                else:
                    # 真正的错误
                    return {
                        "component": "node_tcpdump",
                        "node_name": node_name,
                        "interface": interface,
                        "error": error_msg,
                        "command": " ".join(cmd),
                        "success": False
                    }

            # 成功的情况
            output = result.get("data", "")
            packet_count = output.count('\n') if output else 0

            return {
                "component": "node_tcpdump",
                "node_name": node_name,
                "interface": interface,
                "command": " ".join(tcpdump_cmd),
                "output": output,
                "packet_count": packet_count,
                "timeout_reached": False,
                "success": True
            }

        except Exception as e:
            return {
                "component": "node_tcpdump",
                "node_name": node_name,
                "interface": interface,
                "error": str(e),
                "success": False
            }

    async def collect_ovn_trace(
        self,
        target_type: str,  # "pod" or "node"
        target_name: str,
        target_ip: str,
        target_mac: Optional[str] = None,
        protocol: str = "icmp",
        port: Optional[int] = None,
        arp_type: Optional[str] = None
    ) -> Dict:
        """
        追踪 OVN 微流 (ovn-trace) - 🌟 网络诊断的**首选**工具

        ⭐ **为什么优先使用 ovn-trace？**
        - 快速定位数据包在 OVN 逻辑网络中的流向
        - 确定数据包从哪个网卡流出（output_nic）
        - 判断流量是否被丢弃（is_dropped）及原因
        - 无需实际发送流量，纯逻辑模拟

        💡 **诊断工作流建议**：
        1. 先使用 ovn-trace 确定流路径和出网卡
        2. 再在出网卡上抓包（tcpdump），验证实际流量

        执行方式:
        - kubectl-ko trace {namespace/podname} <target_ip> [target_mac] {icmp|tcp|udp} [port]
        - kubectl-ko trace {node//nodename} <target_ip> [target_mac] {icmp|tcp|udp} [port]
        - kubectl-ko trace {namespace/podname} <target_ip> [target_mac] arp {request|reply}
        - kubectl-ko trace {node//nodename} <target_ip> [target_mac] arp {request|reply}

        Args:
            target_type: 目标类型 ("pod" 或 "node")
            target_name: 目标名称 (Pod 名称或节点名称，Pod 需包含 namespace，格式 "namespace/podname")
            target_ip: 目标 IP 地址
            target_mac: 目标 MAC 地址 (可选，未提供时自动查找)
            protocol: 协议类型 ("icmp", "tcp", "udp", "arp")
            port: 目标端口 (仅 tcp/udp, 可选)
            arp_type: ARP 类型 ("request" 或 "reply", 仅 arp 协议)

        Returns:
            {
                "component": "ovn-trace",
                "target": str,
                "target_ip": str,
                "target_mac": str,  # 实际使用的 MAC 地址
                "protocol": str,
                "trace_output": str,  # 原始输出
                "parsed": {  # 🆕 智能解析结果
                    "output_nic": str,  # 流出的网卡（如 "eth0", "veth_xxx_h"）
                    "final_verdict": str,  # 最终裁决（"allowed" 或 "dropped"）
                    "drop_reason": str,  # 丢弃原因（如果被丢弃）
                    "flow_path": List[str],  # 关键流路径
                },
                "success": bool,
                "error": str (如果失败),
                "auto_fetched_mac": bool  # 是否自动获取了 MAC 地址
            }
        """
        import re

        # 🆕 步骤 1: 自动查找 MAC 地址（如果未提供）
        auto_fetched_mac = False
        if not target_mac and target_type == "pod":
            # 从 Pod 名称解析 namespace 和 pod_name
            if "/" in target_name:
                namespace, pod_name = target_name.split("/", 1)

                # 获取 Pod 信息（使用 describe 获取详细信息）
                pod_info = await self.collect_pod_describe(
                    pod_name=pod_name,
                    namespace=namespace
                )

                # 检查是否成功（没有 error 字段表示成功）
                if "error" not in pod_info:
                    # 从 key_info 中获取 annotations
                    key_info = pod_info.get("key_info", {})
                    annotations = key_info.get("annotations", {})
                    mac_address = annotations.get("ovn.kubernetes.io/mac_address")

                    if mac_address:
                        target_mac = mac_address
                        auto_fetched_mac = True
                    else:
                        return {
                            "component": "ovn-trace",
                            "target": target_name,
                            "target_ip": target_ip,
                            "error": f"无法自动获取 Pod {target_name} 的 MAC 地址",
                            "hint": "请确保 Pod annotation 中包含 'ovn.kubernetes.io/mac_address'，或手动提供 target_mac 参数",
                            "success": False,
                            "auto_fetched_mac": False
                        }
                else:
                    return {
                        "component": "ovn-trace",
                        "target": target_name,
                        "target_ip": target_ip,
                        "error": f"无法获取 Pod 信息: {pod_info.get('error', 'Unknown error')}",
                        "success": False,
                        "auto_fetched_mac": False
                    }

        # 构建目标标识
        if target_type == "pod":
            target = f"{target_name}"
        else:  # node
            target = f"node//{target_name}"

        # 构建命令: kubectl-ko trace <target> <target_ip> [target_mac] <protocol> [port] [arp_type]
        cmd = self.client.ko_cmd + ["trace", target, target_ip]

        if target_mac:
            cmd.append(target_mac)

        cmd.append(protocol)

        if protocol in ["tcp", "udp"] and port:
            cmd.append(str(port))

        if protocol == "arp" and arp_type:
            cmd.append(arp_type)

        result = await self.client.run(cmd, timeout=60)

        if not result["success"]:
            return {
                "component": "ovn-trace",
                "target": target,
                "target_ip": target_ip,
                "target_mac": target_mac,
                "protocol": protocol,
                "error": result.get("error"),
                "success": False,
                "auto_fetched_mac": auto_fetched_mac
            }

        trace_output = result.get("data", "")

        # 🆕 步骤 2: 智能解析 trace 输出
        parsed = self._parse_ovn_trace_output(trace_output)

        return {
            "component": "ovn-trace",
            "target": target,
            "target_ip": target_ip,
            "target_mac": target_mac,
            "protocol": protocol,
            "port": port,
            "trace_output": trace_output,
            "parsed": parsed,  # 🆕 解析后的结构化数据
            "success": True,
            "auto_fetched_mac": auto_fetched_mac
        }

    # === Network 资源收集 ===
    # 注：collect_network_connectivity 已移除，因为依赖 kube-ovn-pinger 日志，参考价值有限

    # === 辅助方法 ===

    def _parse_ovn_trace_output(self, trace_output: str) -> Dict:
        """
        解析 ovn-trace 输出，提取关键信息

        Args:
            trace_output: ovn-trace 的原始输出

        Returns:
            {
                "output_nic": str,  # 流出的网卡
                "final_verdict": str,  # "allowed" 或 "dropped"
                "drop_reason": str,  # 丢弃原因（如果被丢弃）
                "flow_path": List[str],  # 关键流路径摘要
                "key_stages": Dict,  # 关键阶段信息
                "analysis": str,  # 🆕 智能分析结果
                "next_steps": List[str],  # 🆕 建议的下一步操作
            }
        """
        import re

        lines = trace_output.split('\n')

        result = {
            "output_nic": None,
            "final_verdict": "unknown",
            "drop_reason": None,
            "flow_path": [],
            "key_stages": {},
            "analysis": "",
            "next_steps": []
        }

        # 关键词模式
        output_patterns = [
            r"output port\s+(\S+)",  # "output port eth0"
            r"output:\s+(\S+)",  # "output: eth0"
            r"to\s+(\S+)",  # "to eth0"
        ]

        drop_patterns = [
            r"drop",
            r"dropped",
            r"reject",
            r"acl.*drop",
            r"policy.*drop"
        ]

        flow_keywords = [
            "ct", "commit", "nat", "lrp", "lsp", "acl",
            "output", "input", "encap", "decap", "recirc"
        ]

        # 特殊模式：loopback / omitting output
        loopback_pattern = r"omitting output.*inport == outport.*loopback"
        has_loopback_omit = False
        has_nat = False
        has_output_action = False

        # 逐行解析
        for line in lines:
            line_stripped = line.strip()

            # 检测特殊模式
            if re.search(loopback_pattern, line_stripped, re.IGNORECASE):
                has_loopback_omit = True

            if "nat(" in line_stripped.lower() or "nat)" in line_stripped.lower():
                has_nat = True

            if "output;" in line_stripped:
                has_output_action = True

            # 1. 检测 output 网卡
            for pattern in output_patterns:
                match = re.search(pattern, line_stripped, re.IGNORECASE)
                if match:
                    output_nic = match.group(1)
                    # 清理可能的特殊字符（包括分号）
                    output_nic = output_nic.strip('(");')
                    if output_nic and output_nic not in ["None", "-", "[]"]:
                        result["output_nic"] = output_nic
                        break

            # 2. 检测丢弃标记
            for pattern in drop_patterns:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    if result["final_verdict"] != "dropped":
                        result["final_verdict"] = "dropped"
                        result["drop_reason"] = line_stripped

            # 3. 提取关键流路径
            if any(keyword in line_stripped.lower() for keyword in flow_keywords):
                # 限制长度，避免过多细节
                if len(line_stripped) < 200:
                    result["flow_path"].append(line_stripped)

        # 🆕 4. 智能分析和建议
        analysis_parts = []
        next_steps = []

        # 情况 1: loopback omit（说明需要实际发包验证）
        if has_loopback_omit:
            analysis_parts.append("ovn-trace 显示逻辑路径中遇到 loopback 检查，数据包被回环到 Pod 本身。")
            analysis_parts.append("这并不代表流量真正被丢弃，而是逻辑模拟的限制。")
            next_steps.append("1. 使用 collect_tcpdump 在 Pod 的 veth 上抓包，验证流量离开 Pod")
            next_steps.append("2. 检查节点路由表 (collect_node_ip_route)，确认出口网卡")
            next_steps.append("3. 使用 collect_node_tcpdump 在出口物理网卡（如 eth0）抓包，验证流量是否真正发出")
            next_steps.append("4. 如果 Pod veth 和节点物理网卡都有包，但没有回复 → 外部网络问题")

            # 修正裁决
            if has_nat:
                result["final_verdict"] = "needs_verification"
                result["analysis"] = "流量经过 NAT 处理，但被 loopback 规则拦截。需要实际抓包验证。使用 collect_tcpdump 抓 Pod veth，然后使用 collect_node_tcpdump 抓节点网卡。"
            else:
                result["final_verdict"] = "needs_verification"
                result["analysis"] = "流量在逻辑路径中被回环检查拦截。建议进行实际抓包验证。"

        # 情况 2: 明确的 output_nic
        elif result["output_nic"]:
            analysis_parts.append(f"流量将从 {result['output_nic']} 网卡流出。")
            result["final_verdict"] = "allowed"

            # 判断是物理网卡还是虚拟网卡
            if any(prefix in result["output_nic"] for prefix in ["eth", "ens", "eno", "enp"]):
                analysis_parts.append("这是物理网卡，流量将离开 OVN 网络。")
                next_steps.append(f"在 {result['output_nic']} 上使用 tcpdump 抓包验证")
                next_steps.append("如果没有回包，说明是外部网络问题，不是 Kube-OVN 问题")
            else:
                analysis_parts.append("这是虚拟网卡，流量仍在 OVN 网络内部。")
                next_steps.append(f"在 {result['output_nic']} 上使用 tcpdump 抓包")
                next_steps.append("继续追踪流量到下一跳")

        # 情况 3: 明确丢弃
        elif result["final_verdict"] == "dropped":
            if "acl" in result.get("drop_reason", "").lower():
                analysis_parts.append("流量被 ACL 策略丢弃。")
                next_steps.append("检查网络策略和 ACL 配置")
                next_steps.append("使用 ovn-nbctl 查看 ACL 规则详情")
            elif "policy" in result.get("drop_reason", "").lower():
                analysis_parts.append("流量被网络策略丢弃。")
                next_steps.append("检查 Kubernetes NetworkPolicy 配置")
            else:
                analysis_parts.append(f"流量被丢弃: {result.get('drop_reason', '未知原因')}")
                next_steps.append("检查 OVN 流表和日志")

        # 情况 4: unknown
        else:
            if has_output_action:
                result["final_verdict"] = "allowed"
                analysis_parts.append("检测到 output 动作，流量应该被允许。")
                next_steps.append("在实际网卡上抓包验证")

        result["analysis"] = " ".join(analysis_parts)
        result["next_steps"] = next_steps

        # 5. 提取关键阶段（简化版）
        if len(result["flow_path"]) > 0:
            # 只保留前 20 个关键步骤
            result["flow_path"] = result["flow_path"][:20]

            # 提取关键阶段
            for i, step in enumerate(result["flow_path"]):
                if "ct(" in step:
                    result["key_stages"]["conntrack"] = step
                elif "nat" in step.lower():
                    result["key_stages"]["nat"] = step
                elif "acl" in step.lower():
                    result["key_stages"]["acl"] = step
                elif "output" in step.lower() and result["output_nic"]:
                    result["key_stages"]["output"] = step

        return result

    def _filter_logs(self, logs: List[str]) -> List[str]:
        """过滤日志，优先保留 warning 和 error"""
        keywords = [
            'error', 'Error', 'ERROR',
            'warning', 'Warning', 'WARNING',
            'panic', 'fatal', 'Failed', 'failed',
            'exception', 'Exception', 'EXCEPTION'
        ]

        # 第一轮：保留包含关键字的日志
        filtered = [log for log in logs if any(kw in log for kw in keywords)]

        # 第二轮：如果过滤后太少，补充其他日志
        if len(filtered) < 100:
            remaining = 100 - len(filtered)
            for log in logs:
                if log not in filtered:
                    filtered.append(log)
                    remaining -= 1
                    if remaining <= 0:
                        break

        return filtered

    def _count_errors(self, logs: List[str]) -> int:
        """统计错误数量"""
        error_keywords = ['error', 'Error', 'ERROR', 'fatal', 'panic']
        return sum(
            1 for log in logs
            if any(kw in log for kw in error_keywords)
        )

    def _count_warnings(self, logs: List[str]) -> int:
        """统计警告数量"""
        warning_keywords = ['warning', 'Warning', 'WARNING']
        return sum(
            1 for log in logs
            if any(kw in log for kw in warning_keywords)
        )

    # === 批量收集 ===

    async def collect_batch(self, tasks: List[Dict]) -> Dict:
        """
        批量收集资源

        Args:
            tasks: [
                {"type": "pod_logs", "pod_name": "...", "namespace": "..."},
                {"type": "subnet_status", "subnet_name": "..."},
                ...
            ]

        Returns:
            {
                "results": {
                    "task_index": {...}
                },
                "errors": [
                    {"task_index": int, "error": str}
                ]
            }
        """
        results = {}
        errors = []

        for idx, task in enumerate(tasks):
            task_type = task.get("type")

            try:
                if task_type == "pod_logs":
                    result = await self.collect_pod_logs(
                        pod_name=task["pod_name"],
                        namespace=task["namespace"],
                        tail=task.get("tail", 100),
                        container=task.get("container"),
                        filter_errors=task.get("filter_errors", True)
                    )

                elif task_type == "pod_describe":
                    result = await self.collect_pod_describe(
                        pod_name=task["pod_name"],
                        namespace=task["namespace"]
                    )

                elif task_type == "pod_events":
                    result = await self.collect_pod_events(
                        pod_name=task["pod_name"],
                        namespace=task["namespace"],
                        limit=task.get("limit", 20),
                        filter_warnings=task.get("filter_warnings", True)
                    )

                elif task_type == "subnet_status":
                    result = await self.collect_subnet_status(
                        subnet_name=task.get("subnet_name")
                    )

                elif task_type == "subnet_ips":
                    result = await self.collect_subnet_ips(
                        subnet_name=task["subnet_name"],
                        limit=task.get("limit", 100)
                    )

                elif task_type == "node_info":
                    result = await self.collect_node_info(
                        node_name=task.get("node_name")
                    )

                elif task_type == "node_network_config":
                    result = await self.collect_node_network_config(
                        node_name=task.get("node_name")
                    )

                elif task_type == "controller_logs":
                    result = await self.collect_controller_logs(
                        tail=task.get("tail", 100)
                    )

                elif task_type == "controller_status":
                    result = await self.collect_controller_status()

                elif task_type == "network_connectivity":
                    result = await self.collect_network_connectivity(
                        source_pod=task["source_pod"],
                        source_namespace=task["source_namespace"],
                        target=task["target"],
                        test_type=task.get("test_type", "ping")
                    )

                else:
                    errors.append({
                        "task_index": idx,
                        "error": f"Unknown task type: {task_type}"
                    })
                    continue

                results[idx] = result

            except Exception as e:
                errors.append({
                    "task_index": idx,
                    "error": str(e)
                })

        return {
            "results": results,
            "errors": errors
        }
