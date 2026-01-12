"""
Kubernetes 客户端 - 基于 kubectl 和集群内的 kubectl-ko

使用策略：
1. kubectl - 标准 K8s 资源
2. kubectl-ko - 从集群 Pod 复制，操作 Kube-OVN CRD
"""

import subprocess
import os
from typing import Dict, List, Optional
from pathlib import Path

from .cache import get_cache


class KubectlWrapper:
    """kubectl 封装

    集成缓存机制,减少重复的 kubectl 调用。
    """

    def __init__(self, context: Optional[str] = None, enable_cache: bool = True):
        """
        Args:
            context: kubeconfig context (默认使用 current-context)
            enable_cache: 是否启用缓存 (默认 True)
        """
        self.context = context
        self.enable_cache = enable_cache
        self.kubectl_cmd = self._build_kubectl_cmd()
        self.ko_cmd = self._build_ko_cmd()
        self.cache = get_cache() if enable_cache else None

    def _build_kubectl_cmd(self) -> List[str]:
        """构建 kubectl 命令前缀"""
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])
        return cmd

    def _build_ko_cmd(self) -> List[str]:
        """
        构建 kubectl-ko 命令前缀

        策略：
        1. 优先使用 PATH 中的 kubectl-ko
        2. 如果不存在，从集群 Pod 复制
        3. 缓存到本地 ~/.kube-ovn-checker/kubectl-ko
        """
        # 检查 PATH 中是否有 kubectl-ko
        if self._check_kubectl_ko_in_path():
            return ["kubectl-ko"]

        # 检查缓存目录
        cache_dir = Path.home() / ".kube-ovn-checker"
        cached_ko = cache_dir / "kubectl-ko"

        if cached_ko.exists() and os.access(cached_ko, os.X_OK):
            return [str(cached_ko)]

        # 从集群 Pod 复制
        print("📥 首次运行：从集群 Pod 复制 kubectl-ko...")
        ko_path = self._copy_kubectl_ko_from_cluster(cache_dir)

        if ko_path:
            return [str(ko_path)]
        else:
            print("⚠️  无法获取 kubectl-ko，某些功能可能不可用")
            return ["kubectl-ko"]  # 保留命令，让错误自然发生

    def _check_kubectl_ko_in_path(self) -> bool:
        """检查 PATH 中是否有 kubectl-ko"""
        try:
            result = subprocess.run(
                ["which", "kubectl-ko"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False

    def _copy_kubectl_ko_from_cluster(self, cache_dir: Path) -> Optional[Path]:
        """
        从集群 Pod 复制 kubectl-ko

        策略：
        1. 查找 kube-ovn-pinger Pod（最轻量）
        2. 如果不存在，查找 kube-ovn-controller
        3. 从 /kube-ovn/kubectl-ko 复制
        4. 缓存到 ~/.kube-ovn-checker/
        """
        try:
            # 创建缓存目录
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached_ko = cache_dir / "kubectl-ko"

            # 查找合适的 Pod
            pod_name, namespace = self._find_pod_for_kubectl_ko()

            if not pod_name:
                print("❌ 未找到可用的 Kube-OVN Pod")
                return None

            print(f"  📦 从 Pod {namespace}/{pod_name} 复制...")

            # 复制 kubectl-ko
            result = subprocess.run([
                "kubectl", "cp",
                f"{namespace}/{pod_name}:/kube-ovn/kubectl-ko",
                str(cached_ko),
                "-c", "kube-ovn-pinger" if "pinger" in pod_name else "-c",
                "kube-ovn-controller"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"❌ 复制失败: {result.stderr}")
                return None

            # 添加执行权限
            os.chmod(cached_ko, 0o755)

            print(f"✅ kubectl-ko 已缓存到 {cached_ko}")
            return cached_ko

        except Exception as e:
            print(f"❌ 复制 kubectl-ko 时出错: {e}")
            return None

    def _find_pod_for_kubectl_ko(self) -> tuple[Optional[str], Optional[str]]:
        """
        查找用于复制 kubectl-ko 的 Pod

        优先级：
        1. kube-ovn-pinger (DaemonSet，必存在，最轻量)
        2. kube-ovn-controller (Deployment，必存在)
        """

        # 策略 1: 查找 pinger Pod
        pinger_pods = self._find_pods_by_selector(
            namespace="kube-system",
            selector="app=kube-ovn-pinger"
        )

        if pinger_pods:
            # 返回第一个运行中的 Pod
            for pod in pinger_pods:
                if pod.get("phase") == "Running":
                    return pod["name"], "kube-system"

        # 策略 2: 查找 controller Pod
        controller_pods = self._find_pods_by_selector(
            namespace="kube-system",
            selector="app=kube-ovn-controller"
        )

        if controller_pods:
            for pod in controller_pods:
                if pod.get("phase") == "Running":
                    return pod["name"], "kube-system"

        return None, None

    def _find_pods_by_selector(self, namespace: str, selector: str) -> List[Dict]:
        """根据 selector 查找 Pod"""
        try:
            cmd = self.kubectl_cmd + [
                "get", "pods", "-n", namespace,
                "-l", selector,
                "-o", "jsonpath={range .items[*]}{.metadata.name}{','}{.status.phase}{'\\n'}{end}"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return []

            lines = result.stdout.strip().split('\n') if result.stdout else []

            pods = []
            for line in lines:
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    pods.append({"name": parts[0], "phase": parts[1]})

            return pods

        except:
            return []

    async def run(self, cmd: List[str], timeout: int = 10, use_cache: bool = True) -> Dict:
        """
        执行命令并解析结果

        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            use_cache: 是否使用缓存 (默认 True)

        Returns:
            {"success": bool, "data": any, "error": str}
        """
        # 如果启用缓存且请求允许缓存
        if self.enable_cache and use_cache and self.cache:
            # 生成缓存键
            cache_key = self.cache.generate_key(
                method="run",
                command=" ".join(cmd),
                timeout=timeout
            )

            # 尝试从缓存获取
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                # 缓存命中,添加缓存标记
                cached_result["_cached"] = True
                return cached_result

        # 执行实际命令
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                response = {
                    "success": False,
                    "error": result.stderr.strip(),
                    "cmd": " ".join(cmd)
                }
                # 失败结果不缓存
                return response

            # 尝试解析 JSON
            try:
                data = json.loads(result.stdout)
                response = {"success": True, "data": data}
            except json.JSONDecodeError:
                # 不是 JSON，返回原始文本
                response = {"success": True, "data": result.stdout.strip()}

            # 缓存成功结果
            if self.enable_cache and use_cache and self.cache:
                response["_cached"] = False
                self.cache.set(cache_key, response)

            return response

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout}s",
                "cmd": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cmd": " ".join(cmd)
            }

    # === 标准 K8s 资源操作 ===

    async def get_pod(self, namespace: str, pod_name: str) -> Dict:
        """获取单个 Pod 信息"""
        cmd = self.kubectl_cmd + [
            "get", "pod", pod_name,
            "-n", namespace,
            "-o", "json"
        ]
        return await self.run(cmd, timeout=10)

    async def get_pods(self, namespace: str = None,
                       selector: str = None,
                       field_selector: str = None) -> Dict:
        """获取 Pod 列表"""
        cmd = self.kubectl_cmd + ["get", "pods"]

        if namespace:
            cmd.extend(["-n", namespace])
        else:
            cmd.append("-A")

        if selector:
            cmd.extend(["-l", selector])

        if field_selector:
            cmd.extend(["--field-selector", field_selector])

        cmd.extend(["-o", "json"])
        return await self.run(cmd, timeout=15)

    async def get_events(self, namespace: str,
                         field_selector: str = None) -> Dict:
        """获取事件"""
        cmd = self.kubectl_cmd + ["get", "events", "-n", namespace]

        if field_selector:
            cmd.extend(["--field-selector", field_selector])

        cmd.extend(["-o", "json"])
        return await self.run(cmd, timeout=10)

    async def describe_pod(self, namespace: str, pod_name: str) -> Dict:
        """获取 Pod 详细信息（describe）"""
        cmd = self.kubectl_cmd + [
            "describe", "pod", pod_name,
            "-n", namespace
        ]
        return await self.run(cmd, timeout=15)

    # === Kube-OVN CRD 操作（使用 kubectl-ko）===

    async def get_subnets(self) -> Dict:
        """获取所有子网"""
        cmd = self.ko_cmd + ["get", "subnet", "-o", "json"]
        return await self.run(cmd, timeout=10)

    async def get_subnet(self, name: str) -> Dict:
        """获取单个子网详情"""
        cmd = self.ko_cmd + ["get", "subnet", name, "-o", "json"]
        return await self.run(cmd, timeout=10)

    async def get_ip(self, ip_cr_name: str) -> Dict:
        """
        获取单个 IP CR 详情

        Args:
            ip_cr_name: IP CR 名称（格式: podname.namespace）

        Returns:
            {
                "success": True,
                "data": {IP CR JSON}
            }
        """
        cmd = self.ko_cmd + ["get", "ip", ip_cr_name, "-o", "json"]
        return await self.run(cmd, timeout=10)

    async def get_ips(self, namespace: str = None) -> Dict:
        """获取 IP 列表"""
        cmd = self.ko_cmd + ["get", "ip", "-o", "json"]

        if namespace:
            cmd.extend(["-n", namespace])
        else:
            cmd.append("-A")

        return await self.run(cmd, timeout=15)

    async def get_vpcs(self) -> Dict:
        """获取 VPC 列表"""
        cmd = self.ko_cmd + ["get", "vpc", "-o", "json"]
        return await self.run(cmd, timeout=10)

    async def get_controller_logs(self, tail: int = 100) -> Dict:
        """获取 kube-ovn-controller 日志"""
        cmd = self.kubectl_cmd + [
            "logs", "-n", "kube-system",
            "deploy/kube-ovn-controller",
            "--tail", str(tail)
        ]
        return await self.run(cmd, timeout=15)

    # === OVN 数据访问（通过 kubectl-ko）===

    async def nbctl_list_logical_switch(self) -> Dict:
        """获取逻辑交换机列表"""
        cmd = self.ko_cmd + ["nbctl", "list", "Logical_Switch"]
        return await self.run(cmd, timeout=15)

    async def nbctl_list_logical_router(self) -> Dict:
        """获取逻辑路由器列表"""
        cmd = self.ko_cmd + ["nbctl", "list", "Logical_Router"]
        return await self.run(cmd, timeout=15)

    async def nbctl_show(self, resource_type: str, name: str) -> Dict:
        """显示 OVN 资源详情"""
        cmd = self.ko_cmd + ["nbctl", "show", resource_type, name]
        return await self.run(cmd, timeout=15)

    async def sbctl_list_datapath(self) -> Dict:
        """获取数据路径列表"""
        cmd = self.ko_cmd + ["sbctl", "list", "Datapath"]
        return await self.run(cmd, timeout=15)

    # === T0 收集器新增方法 ===

    async def get_deployment(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 Deployment 状态

        Args:
            name: Deployment 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {
                "success": True/False,
                "data": {
                    "name": str,
                    "namespace": str,
                    "ready_replicas": int,
                    "replicas": int,
                    "updated_replicas": int,
                    "available_replicas": int,
                    "unavailable_replicas": int
                },
                "error": str (如果失败)
            }
        """
        cmd = self.kubectl_cmd + [
            "get", "deployment", name,
            "-n", namespace,
            "-o", "json"
        ]
        return await self.run(cmd, timeout=2)

    async def get_daemonset(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 DaemonSet 状态

        Args:
            name: DaemonSet 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {
                "success": True/False,
                "data": {
                    "name": str,
                    "namespace": str,
                    "number_ready": int,
                    "desired_number_scheduled": int,
                    "current_number_scheduled": int,
                    "number_unavailable": int,
                    "updated_number_scheduled": int
                },
                "error": str (如果失败)
            }
        """
        cmd = self.kubectl_cmd + [
            "get", "daemonset", name,
            "-n", namespace,
            "-o", "json"
        ]
        return await self.run(cmd, timeout=2)

    async def get_endpoints(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 Endpoint 地址列表

        Args:
            name: Endpoint 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {
                "success": True/False,
                "data": {
                    "name": str,
                    "namespace": str,
                    "addresses": ["IP:PORT", ...],
                    "not_ready_addresses": ["IP:PORT", ...]
                },
                "error": str (如果失败)
            }
        """
        cmd = self.kubectl_cmd + [
            "get", "endpoints", name,
            "-n", namespace,
            "-o", "json"
        ]
        return await self.run(cmd, timeout=2)

    async def describe_deployment(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 Deployment 详细信息 (describe)

        Args:
            name: Deployment 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {"success": True/False, "data": "describe 文本输出", "error": str}
        """
        cmd = self.kubectl_cmd + [
            "describe", "deployment", name,
            "-n", namespace
        ]
        return await self.run(cmd, timeout=3)

    async def describe_daemonset(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 DaemonSet 详细信息 (describe)

        Args:
            name: DaemonSet 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {"success": True/False, "data": "describe 文本输出", "error": str}
        """
        cmd = self.kubectl_cmd + [
            "describe", "daemonset", name,
            "-n", namespace
        ]
        return await self.run(cmd, timeout=3)

    async def describe_endpoints(self, name: str, namespace: str = "kube-system") -> Dict:
        """
        获取 Endpoint 详细信息 (describe)

        Args:
            name: Endpoint 名称
            namespace: 命名空间 (默认 kube-system)

        Returns:
            {"success": True/False, "data": "describe 文本输出", "error": str}
        """
        cmd = self.kubectl_cmd + [
            "describe", "endpoints", name,
            "-n", namespace
        ]
        return await self.run(cmd, timeout=3)

    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: str = "kube-system",
        container: Optional[str] = None,
        tail: int = 200,
        since: Optional[str] = "10m"
    ) -> Dict:
        """
        获取 Pod 日志

        Args:
            pod_name: Pod 名称
            namespace: 命名空间 (默认 kube-system)
            container: 容器名称 (多容器 Pod 必需)
            tail: 返回最后 N 行 (默认 200)
            since: 返回最近时间段的日志 (默认 "10m")

        Returns:
            {"success": True/False, "data": "日志文本", "error": str}
        """
        cmd = self.kubectl_cmd + [
            "logs", pod_name,
            "-n", namespace,
            "--tail", str(tail),
            "--since", since
        ]

        if container:
            cmd.extend(["-c", container])

        return await self.run(cmd, timeout=2)

    async def get_nodes(self) -> Dict:
        """
        获取所有节点信息

        Returns:
            {
                "success": True/False,
                "data": {
                    "items": [节点列表]
                },
                "error": str
            }
        """
        cmd = self.kubectl_cmd + ["get", "nodes", "-o", "json"]
        return await self.run(cmd, timeout=10)

    # === 缓存管理方法 ===

    def get_cache_stats(self) -> Optional[Dict]:
        """获取缓存统计信息

        Returns:
            {
                "size": 当前缓存条目数,
                "max_size": 最大容量,
                "hits": 命中次数,
                "misses": 未命中次数,
                "evictions": 淘汰次数,
                "hit_rate": 命中率 (0.0-1.0),
                "ttl_seconds": 过期时间
            }
            如果未启用缓存则返回 None
        """
        if self.cache:
            return self.cache.get_stats()
        return None

    def clear_cache(self):
        """清空缓存"""
        if self.cache:
            self.cache.clear()

    def cleanup_cache(self) -> int:
        """清理过期的缓存条目

        Returns:
            清理的条目数
        """
        if self.cache:
            return self.cache.cleanup_expired()
        return 0


# 全局单例
_client = None

def get_k8s_client(context: str = None) -> KubectlWrapper:
    """获取 K8s 客户端实例"""
    global _client
    if _client is None:
        _client = KubectlWrapper(context=context)
    return _client


# === 导入 json 模块 ===
import json
