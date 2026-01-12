"""
LangChain Tools - 将 K8s 资源收集器封装为 LLM 可调用的工具

设计理念：
- LLM 通过调用这些工具来收集 K8s 资源信息
- 每个工具对应一种资源类型的收集
- 返回格式化的文本，便于 LLM 理解
"""

try:
    from pydantic import BaseModel, Field
except ImportError:
    from pydantic.v1 import BaseModel, Field

from langchain.tools import tool
from typing import Optional, List
import json

from ...collectors import K8sResourceCollector
from ...collectors.t0_collector import collect_t0


# === 辅助函数 ===

def format_for_llm(data: dict, indent: int = 2) -> str:
    """将数据格式化为 LLM 可读的文本"""
    return json.dumps(data, indent=indent, ensure_ascii=False)


# === Pod 工具 ===

class CollectPodLogsInput(BaseModel):
    """收集 Pod 日志的参数"""
    pod_name: str = Field(description="Pod 名称")
    namespace: str = Field(description="命名空间")
    tail: int = Field(default=100, description="返回最后 N 行日志")
    filter_errors: bool = Field(default=True, description="是否只保留错误和警告")


@tool(args_schema=CollectPodLogsInput)
async def collect_pod_logs(
    pod_name: str,
    namespace: str,
    tail: int = 100,
    filter_errors: bool = True
) -> str:
    """
    收集 Kubernetes Pod 日志

    当需要查看 Pod 运行日志、错误信息时使用此工具。
    返回日志内容，包括错误和警告的统计信息。

    Args:
        pod_name: Pod 名称
        namespace: 命名空间
        tail: 返回最后 N 行日志
        filter_errors: 是否只保留错误和警告

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_pod_logs(
        pod_name=pod_name,
        namespace=namespace,
        tail=tail,
        filter_errors=filter_errors
    )

    return format_for_llm(result)


class CollectPodDescribeInput(BaseModel):
    """收集 Pod 详细信息的参数"""
    pod_name: str = Field(description="Pod 名称")
    namespace: str = Field(description="命名空间")


@tool(args_schema=CollectPodDescribeInput)
async def collect_pod_describe(pod_name: str, namespace: str) -> str:
    """
    收集 Kubernetes Pod 详细信息

    当需要查看 Pod 的完整配置、状态、重启次数、IP 地址等详细信息时使用此工具。

    Args:
        pod_name: Pod 名称
        namespace: 命名空间

    Returns:
        格式化的 Pod 详细信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_pod_describe(
        pod_name=pod_name,
        namespace=namespace
    )

    return format_for_llm(result)


class CollectPodEventsInput(BaseModel):
    """收集 Pod 事件的参数"""
    pod_name: str = Field(description="Pod 名称")
    namespace: str = Field(description="命名空间")
    limit: int = Field(default=20, description="返回最近 N 个事件")
    filter_warnings: bool = Field(default=True, description="是否只保留警告和错误")


@tool(args_schema=CollectPodEventsInput)
async def collect_pod_events(
    pod_name: str,
    namespace: str,
    limit: int = 20,
    filter_warnings: bool = True
) -> str:
    """
    收集 Kubernetes Pod 事件

    当需要查看 Pod 的事件历史、警告、错误时使用此工具。
    事件可以帮助理解 Pod 的状态变化和问题原因。

    Args:
        pod_name: Pod 名称
        namespace: 命名空间
        limit: 返回最近 N 个事件
        filter_warnings: 是否只保留警告和错误

    Returns:
        格式化的事件列表
    """
    collector = K8sResourceCollector()
    result = await collector.collect_pod_events(
        pod_name=pod_name,
        namespace=namespace,
        limit=limit,
        filter_warnings=filter_warnings
    )

    return format_for_llm(result)


# === Subnet 工具 ===

class CollectSubnetStatusInput(BaseModel):
    """收集 Subnet 状态的参数"""
    subnet_name: str = Field(
        default=None,
        description="子网名称，留空则检查所有子网"
    )


@tool(args_schema=CollectSubnetStatusInput)
async def collect_subnet_status(subnet_name: Optional[str] = None) -> str:
    """
    收集 Kube-OVN Subnet CR 状态

    当需要检查子网 IP 使用情况、状态是否健康时使用此工具。
    可以诊断 IP 耗尽、子网配置错误等问题。

    Args:
        subnet_name: 子网名称，留空则检查所有子网

    Returns:
        格式化的子网状态信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_subnet_status(subnet_name=subnet_name)

    return format_for_llm(result)


class CollectPodIPInput(BaseModel):
    """收集 Pod IP 信息的参数"""
    pod_name: str = Field(description="Pod 名称")
    namespace: str = Field(description="命名空间")


@tool(args_schema=CollectPodIPInput)
async def collect_pod_ip(pod_name: str, namespace: str) -> str:
    """
    收集单个 Pod 的 IP 信息（通过 Kube-OVN IP CR）

    当需要查看 Pod 的 IP 地址、MAC 地址、所属 Subnet、所在节点等信息时使用此工具。

    IP CR 的命名格式: podname.namespace

    Args:
        pod_name: Pod 名称
        namespace: 命名空间

    Returns:
        格式化的 Pod IP 信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_pod_ip(
        pod_name=pod_name,
        namespace=namespace
    )

    return format_for_llm(result)


# === Node 工具 ===

class CollectNodeInfoInput(BaseModel):
    """收集节点信息的参数"""
    node_name: str = Field(
        default=None,
        description="节点名称，留空则检查所有节点"
    )


@tool(args_schema=CollectNodeInfoInput)
async def collect_node_info(node_name: Optional[str] = None) -> str:
    """
    收集 Kubernetes 节点信息

    当需要检查节点状态、资源容量、可分配资源、条件等信息时使用此工具。

    Args:
        node_name: 节点名称，留空则检查所有节点

    Returns:
        格式化的节点信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_info(node_name=node_name)

    return format_for_llm(result)


# === Node 网络配置工具 ===

class CollectNodeIPAddrInput(BaseModel):
    """收集节点网络接口信息的参数"""
    node_name: str = Field(description="节点名称")
    interface: Optional[str] = Field(
        default=None,
        description="网络接口名称 (如 eth0)，留空则显示所有接口"
    )


@tool(args_schema=CollectNodeIPAddrInput)
async def collect_node_ip_addr(
    node_name: str,
    interface: Optional[str] = None
) -> str:
    """
    收集节点网络接口信息 (ip addr)

    当需要查看节点的网络接口、IP 地址、MAC 地址、MTU 等信息时使用此工具。
    在节点的 ovs-ovn Pod 上执行: ip addr [show dev <interface>]

    Args:
        node_name: 节点名称
        interface: 网络接口名称，留空则显示所有接口

    Returns:
        格式化的网络接口信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_ip_addr(
        node_name=node_name,
        interface=interface
    )

    return format_for_llm(result)


class CollectNodeIPRouteInput(BaseModel):
    """收集节点路由表的参数"""
    node_name: str = Field(description="节点名称")


@tool(args_schema=CollectNodeIPRouteInput)
async def collect_node_ip_route(node_name: str) -> str:
    """
    收集节点路由表 (ip route)

    当需要诊断网络路由问题时，查看节点的路由表信息时使用此工具。
    在节点的 ovs-ovn Pod 上执行: ip route show

    Args:
        node_name: 节点名称

    Returns:
        格式化的路由表信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_ip_route(node_name=node_name)

    return format_for_llm(result)


class CollectNodeIPTablesInput(BaseModel):
    """收集节点防火墙规则的参数"""
    node_name: str = Field(description="节点名称")
    table: str = Field(
        default="filter",
        description="iptables 表名: filter | nat | mangle | raw"
    )


@tool(args_schema=CollectNodeIPTablesInput)
async def collect_node_iptables(
    node_name: str,
    table: str = "filter"
) -> str:
    """
    收集节点防火墙规则 (iptables/nftables)

    当需要诊断防火墙、NAT、数据包过滤问题时使用此工具。
    在节点的 ovs-ovn Pod 上执行: iptables-save -t <table> 或 nft list table <table>

    Args:
        node_name: 节点名称
        table: iptables 表名 (默认: filter)

    Returns:
        格式化的防火墙规则信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_iptables(
        node_name=node_name,
        table=table
    )

    return format_for_llm(result)


class CollectNodeIPVSInput(BaseModel):
    """收集节点 IPVS 负载均衡信息的参数"""
    node_name: str = Field(description="节点名称")


@tool(args_schema=CollectNodeIPVSInput)
async def collect_node_ipvs(node_name: str) -> str:
    """
    收集节点 IPVS 负载均衡信息 (ipvsadm)

    当需要诊断 Kubernetes Service 负载均衡问题时使用此工具。
    在节点的 ovs-ovn Pod 上执行: ipvsadm -Ln

    Args:
        node_name: 节点名称

    Returns:
        格式化的 IPVS 虚拟服务和服务器信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_ipvs(node_name=node_name)

    return format_for_llm(result)


class CollectNodeSysctlInput(BaseModel):
    """收集节点内核参数的参数"""
    node_name: str = Field(description="节点名称")
    parameters: Optional[List[str]] = Field(
        default=None,
        description="内核参数列表，留空则使用默认参数集合"
    )


@tool(args_schema=CollectNodeSysctlInput)
async def collect_node_sysctl(
    node_name: str,
    parameters: Optional[List[str]] = None
) -> str:
    """
    收集节点内核网络参数 (sysctl)

    当需要诊断内核参数相关问题时使用此工具。
    在节点的 ovs-ovn Pod 上执行: sysctl <param1> <param2> ...

    默认参数包括:
    - net.ipv4.ip_forward
    - net.ipv4.conf.all.rp_filter
    - net.bridge.bridge-nf-call-iptables
    等 9 个常用网络参数

    Args:
        node_name: 节点名称
        parameters: 内核参数列表，留空则使用默认参数集合

    Returns:
        格式化的内核参数信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_sysctl(
        node_name=node_name,
        parameters=parameters
    )

    return format_for_llm(result)


# === Controller 日志工具 ===

class CollectKubeOVNControllerLogsInput(BaseModel):
    """收集 kube-ovn-controller 日志的参数"""
    tail: int = Field(default=100, description="返回最后 N 行日志")


@tool(args_schema=CollectKubeOVNControllerLogsInput)
async def collect_kube_ovn_controller_logs(tail: int = 100) -> str:
    """
    收集 kube-ovn-controller 日志 (通过 kubectl logs)

    当需要诊断 Kube-OVN 控制器平面的问题时使用此工具。
    kube-ovn-controller 是 Deployment,运行在 kube-system namespace。

    Args:
        tail: 返回最后 N 行日志

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_kube_ovn_controller_logs(tail=tail)

    return format_for_llm(result)


class CollectKubeOVNCNILogsInput(BaseModel):
    """收集 kube-ovn-cni 日志的参数"""
    node_name: str = Field(description="节点名称")
    tail: int = Field(default=100, description="返回每个日志文件的最后 N 行")


@tool(args_schema=CollectKubeOVNCNILogsInput)
async def collect_kube_ovn_cni_logs(node_name: str, tail: int = 100) -> str:
    """
    收集 kube-ovn-cni 日志 (从节点 /var/log/kube-ovn/)

    当需要诊断 CNI 插件问题时使用此工具。
    kube-ovn-cni 是 DaemonSet,日志在节点的 /var/log/kube-ovn/ 目录下。

    Args:
        node_name: 节点名称
        tail: 返回每个日志文件的最后 N 行

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_kube_ovn_cni_logs(
        node_name=node_name,
        tail=tail
    )

    return format_for_llm(result)


class CollectOVNControllerLogsInput(BaseModel):
    """收集 ovn-controller 日志的参数"""
    node_name: str = Field(description="节点名称")
    tail: int = Field(default=100, description="返回最后 N 行日志")


@tool(args_schema=CollectOVNControllerLogsInput)
async def collect_ovn_controller_logs(node_name: str, tail: int = 100) -> str:
    """
    收集 ovn-controller 日志 (从节点 /var/log/ovn/)

    当需要诊断 OVN 控制器问题时使用此工具。
    ovn-controller 是 OVN 主控制进程,日志在 /var/log/ovn/ovn-controller.log。

    Args:
        node_name: 节点名称
        tail: 返回最后 N 行日志

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovn_controller_logs(
        node_name=node_name,
        tail=tail
    )

    return format_for_llm(result)


class CollectOVNNorthdLogsInput(BaseModel):
    """收集 ovn-northd 日志的参数"""
    node_name: str = Field(description="节点名称")
    tail: int = Field(default=100, description="返回最后 N 行日志")


@tool(args_schema=CollectOVNNorthdLogsInput)
async def collect_ovn_northd_logs(node_name: str, tail: int = 100) -> str:
    """
    收集 ovn-northd 日志 (从节点 /var/log/ovn/)

    当需要诊断 OVN Northbound 数据库问题时使用此工具。
    ovn-northd 是 OVN Northbound 守护进程,日志在 /var/log/ovn/ovn-northd.log。

    Args:
        node_name: 节点名称
        tail: 返回最后 N 行日志

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovn_northd_logs(
        node_name=node_name,
        tail=tail
    )

    return format_for_llm(result)


class CollectOVSVswitchdLogsInput(BaseModel):
    """收集 ovs-vswitchd 日志的参数"""
    node_name: str = Field(description="节点名称")
    tail: int = Field(default=100, description="返回最后 N 行日志")


@tool(args_schema=CollectOVSVswitchdLogsInput)
async def collect_ovs_vswitchd_logs(node_name: str, tail: int = 100) -> str:
    """
    收集 ovs-vswitchd 日志 (从节点 /var/log/openvswitch/)

    当需要诊断 Open vSwitch 交换机问题时使用此工具。
    ovs-vswitchd 是 Open vSwitch 交换机守护进程,日志在 /var/log/openvswitch/ovs-vswitchd.log。

    Args:
        node_name: 节点名称
        tail: 返回最后 N 行日志

    Returns:
        格式化的日志信息
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovs_vswitchd_logs(
        node_name=node_name,
        tail=tail
    )

    return format_for_llm(result)


# === Network 工具 ===
# 注：collect_network_connectivity 已移除，因为依赖 kube-ovn-pinger 日志，参考价值有限

# === OVN/OVS 诊断工具 ===

class CollectOVNNbctlInput(BaseModel):
    """执行 ovn-nbctl 命令的参数"""
    command: str = Field(
        description="ovn-nbctl 命令参数，例如: 'list LB' 或 'show LR1'"
    )


@tool(args_schema=CollectOVNNbctlInput)
async def collect_ovn_nbctl(command: str) -> str:
    """
    执行 ovn-nbctl 命令 (OVN Northbound 数据库操作)

    当需要查询或修改 OVN 逻辑网络配置时使用此工具。
    可以诊断逻辑路由器、逻辑交换机、负载均衡器等配置问题。

    常用命令:
    - list LB: 列出所有负载均衡器
    - list LR: 列出所有逻辑路由器
    - list LS: 列出所有逻辑交换机
    - show <resource>: 显示资源详情

    Args:
        command: ovn-nbctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovn_nbctl(command=command)

    return format_for_llm(result)


class CollectOVNSbctlInput(BaseModel):
    """执行 ovn-sbctl 命令的参数"""
    command: str = Field(
        description="ovn-sbctl 命令参数，例如: 'list datapath' 或 'show'"
    )


@tool(args_schema=CollectOVNSbctlInput)
async def collect_ovn_sbctl(command: str) -> str:
    """
    执行 ovn-sbctl 命令 (OVN Southbound 数据库操作)

    当需要诊断 OVN 数据平面状态时使用此工具。
    可以查看数据路径、端口、绑定等运行时状态。

    常用命令:
    - list datapath: 列出所有数据路径
    - list port: 列出所有逻辑端口
    - show: 显示系统概览

    Args:
        command: ovn-sbctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovn_sbctl(command=command)

    return format_for_llm(result)


class CollectOVSVsctlInput(BaseModel):
    """执行 ovs-vsctl 命令的参数"""
    node_name: str = Field(description="节点名称")
    command: str = Field(
        description="ovs-vsctl 命令参数，例如: 'show' 或 'list Bridge'"
    )


@tool(args_schema=CollectOVSVsctlInput)
async def collect_ovs_vsctl(node_name: str, command: str) -> str:
    """
    执行 ovs-vsctl 命令 (OVS 交换机配置查询)

    当需要诊断节点上的 OVS 交换机配置时使用此工具。
    可以查看网桥、端口、接口等配置。

    常用命令:
    - show: 显示 OVS 配置概览
    - list Bridge: 列出所有网桥
    - list Port: 列出所有端口

    Args:
        node_name: 节点名称
        command: ovs-vsctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovs_vsctl(
        node_name=node_name,
        command=command
    )

    return format_for_llm(result)


class CollectOVSOfctlInput(BaseModel):
    """执行 ovs-ofctl 命令的参数"""
    node_name: str = Field(description="节点名称")
    command: str = Field(
        description="ovs-ofctl 命令参数，例如: 'dump-flows br-int' 或 'show br-int'"
    )


@tool(args_schema=CollectOVSOfctlInput)
async def collect_ovs_ofctl(node_name: str, command: str) -> str:
    """
    执行 ovs-ofctl 命令 (OpenFlow 诊断)

    当需要诊断 OpenFlow 流表和转发规则时使用此工具。
    可以查看流表、端口状态、组表等。

    常用命令:
    - dump-flows <bridge>: 转储流表
    - show <bridge>: 显示网桥状态
    - dump-ports-desc <bridge>: 显示端口描述

    Args:
        node_name: 节点名称
        command: ovs-ofctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovs_ofctl(
        node_name=node_name,
        command=command
    )

    return format_for_llm(result)


class CollectOVSDpctlInput(BaseModel):
    """执行 ovs-dpctl 命令的参数"""
    node_name: str = Field(description="节点名称")
    command: str = Field(
        description="ovs-dpctl 命令参数，例如: 'show' 或 'dump-dps'"
    )


@tool(args_schema=CollectOVSDpctlInput)
async def collect_ovs_dpctl(node_name: str, command: str) -> str:
    """
    执行 ovs-dpctl 命令 (OVS 数据路径诊断)

    当需要诊断 OVS 数据路径性能和统计信息时使用此工具。
    可以查看数据路径接口、流统计、缓存等。

    常用命令:
    - show: 显示数据路径信息
    - dump-dps: 列出所有数据路径
    - show -st: 显示统计信息

    Args:
        node_name: 节点名称
        command: ovs-dpctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovs_dpctl(
        node_name=node_name,
        command=command
    )

    return format_for_llm(result)


class CollectOVSAppctlInput(BaseModel):
    """执行 ovs-appctl 命令的参数"""
    node_name: str = Field(description="节点名称")
    target: str = Field(
        description="目标进程，例如: 'ovs-vswitchd' 或 'ovn-controller'"
    )
    command: str = Field(
        description="ovs-appctl 命令参数，例如: 'coverage/show' 或 'memory/show'"
    )


@tool(args_schema=CollectOVSAppctlInput)
async def collect_ovs_appctl(node_name: str, target: str, command: str) -> str:
    """
    执行 ovs-appctl 命令 (OVS 守护进程控制)

    当需要控制或查询 OVS 守护进程运行状态时使用此工具。
    可以查看覆盖率、内存使用、日志级别等。

    常用命令:
    - coverage/show: 显示代码覆盖率
    - memory/show: 显示内存使用
    - vlog/list: 列出日志模块
    - vlog/set: 设置日志级别

    Args:
        node_name: 节点名称
        target: 目标进程 (ovs-vswitchd/ovn-controller)
        command: ovs-appctl 命令参数

    Returns:
        格式化的命令输出
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovs_appctl(
        node_name=node_name,
        target=target,
        command=command
    )

    return format_for_llm(result)


class CollectTcpdumpInput(BaseModel):
    """捕获 Pod 流量的参数"""
    pod_name: str = Field(description="Pod 名称")
    namespace: str = Field(description="命名空间")
    count: int = Field(default=10, description="捕获的数据包数量")
    filter_expr: Optional[str] = Field(
        default=None,
        description="BPF 过滤表达式，例如: 'tcp port 80'"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="超时时间（秒），5-120 秒，默认 30 秒"
    )


@tool(args_schema=CollectTcpdumpInput)
async def collect_tcpdump(
    pod_name: str,
    namespace: str,
    count: int = 10,
    filter_expr: Optional[str] = None,
    timeout: int = 30
) -> str:
    """
    捕获 Pod 网络流量 (tcpdump) - **在 ovn-trace 之后使用**

    ⭐ **使用时机**: 网络诊断的第二步，在 ovn-trace 确定流路径后使用

    💡 **诊断工作流建议**：
    1. **第一步**: 使用 ovn-trace 确定流路径和出网卡
    2. **第二步**: 在出网卡上抓包（此工具）
    3. **判断**:
       - 如果 ovn-trace 显示流量到物理网卡 + 抓包无回复 → 外部网络问题
       - 如果 ovn-trace 显示流量在 OVN 内部丢弃 → Kube-OVN 配置问题

    ✨ **特性**:
    - 🆕 自动查找 Pod 的 veth 网卡
    - 🆕 直接在 ovs-ovn Pod 上执行 tcpdump
    - 🆕 通过 timeout 命令控制超时，避免无限等待

    当需要深度诊断网络问题时使用此工具。
    可以捕获 Pod 的进出流量,分析数据包内容。

    常用过滤器:
    - tcp port 80: 只捕获 TCP 80 端口
    - host 10.244.0.5: 只捕获特定 IP
    - icmp: 只捕获 ICMP 包

    Args:
        pod_name: Pod 名称
        namespace: 命名空间
        count: 捕获的数据包数量（默认 10）
        filter_expr: BPF 过滤表达式（可选）
        timeout: 超时时间（秒），默认 30 秒

    Returns:
        格式化的捕获结果，包括网卡信息、数据包内容等
    """
    collector = K8sResourceCollector()
    result = await collector.collect_tcpdump(
        pod_name=pod_name,
        namespace=namespace,
        count=count,
        filter_expr=filter_expr,
        timeout=timeout
    )

    return format_for_llm(result)


class CollectNodeTcpdumpInput(BaseModel):
    """在节点网卡上抓包的参数"""
    node_name: str = Field(
        description="节点名称"
    )
    interface: str = Field(
        description="网卡名称 (例如: eth0, ens33, ovn0)"
    )
    count: int = Field(
        default=10,
        description="捕获的数据包数量 (默认 10)"
    )
    filter_expr: Optional[str] = Field(
        default=None,
        description="tcpdump 过滤表达式 (例如: 'icmp', 'host 8.8.8.8')"
    )
    timeout: int = Field(
        default=30,
        description="超时时间（秒），默认 30 秒"
    )


@tool(args_schema=CollectNodeTcpdumpInput)
async def collect_node_tcpdump(
    node_name: str,
    interface: str,
    count: int = 10,
    filter_expr: Optional[str] = None,
    timeout: int = 30
) -> str:
    """
    在节点网卡上抓包 (tcpdump) - **验证流量是否离开节点**

    ⭐ **使用场景**: 在 ovn-trace 确定流路径后，验证流量是否真正离开节点

    💡 **诊断工作流建议**：
    1. **第一步**: 使用 ovn-trace 确定流路径和出网卡
    2. **第二步**: 在 Pod veth 上抓包 (collect_tcpdump)，验证流量离开 Pod
    3. **第三步**: 在节点网卡上抓包 (此工具)，验证流量离开节点
    4. **判断**:
       - 如果 Pod veth 有包，节点网卡也有包 → 流量成功离开节点
       - 如果节点网卡有包但无回复 → **外部网络问题**（不是 Kube-OVN 问题）
       - 如果节点网卡无包 → Kube-OVN 内部问题

    ✨ **特性**:
    - 🆕 在节点的任意网卡上抓包（物理网卡、ovn0 等）
    - 🆕 使用 timeout 命令控制超时，避免无限等待
    - 🆕 通过节点的 ovs-ovn Pod 执行，使用 hostNetwork 访问节点网卡

    常用网卡:
    - **物理网卡**: eth0, ens33, eno1, enp0s3（流量出口到外部网络）
    - **OVN 网卡**: ovn0（OVN 的网关接口）
    - **OVS 网桥**: br-int（内部网桥）

    常用过滤器:
    - icmp: 只捕获 ICMP 包
    - host 8.8.8.8: 只捕获特定 IP
    - tcp port 80: 只捕获 TCP 80 端口

    Args:
        node_name: 节点名称
        interface: 网卡名称（例如: eth0, ovn0）
        count: 捕获的数据包数量（默认 10）
        filter_expr: BPF 过滤表达式（可选）
        timeout: 超时时间（秒），默认 30 秒

    Returns:
        格式化的捕获结果，包括网卡信息、数据包内容、包数量等
    """
    collector = K8sResourceCollector()
    result = await collector.collect_node_tcpdump(
        node_name=node_name,
        interface=interface,
        count=count,
        filter_expr=filter_expr,
        timeout=timeout
    )

    return format_for_llm(result)


class CollectOVNTraceInput(BaseModel):
    """追踪 OVN 微流的参数"""
    target_type: str = Field(
        description="目标类型: pod 或 node"
    )
    target_name: str = Field(
        description="目标名称 (Pod 名称或节点名称)"
    )
    target_ip: str = Field(
        description="目标 IP 地址"
    )
    target_mac: Optional[str] = Field(
        default=None,
        description="目标 MAC 地址 (可选)"
    )
    protocol: str = Field(
        default="icmp",
        description="协议类型: icmp | tcp | udp | arp"
    )
    port: Optional[int] = Field(
        default=None,
        description="目标端口 (TCP/UDP 时需要)"
    )
    arp_type: Optional[str] = Field(
        default=None,
        description="ARP 类型: request | reply (仅 protocol=arp 时)"
    )


@tool(args_schema=CollectOVNTraceInput)
async def collect_ovn_trace(
    target_type: str,
    target_name: str,
    target_ip: str,
    target_mac: Optional[str] = None,
    protocol: str = "icmp",
    port: Optional[int] = None,
    arp_type: Optional[str] = None
) -> str:
    """
    🌟 追踪 OVN 微流 (ovn-trace) - **网络诊断的首选工具**

    ⭐ **优先级**: 网络连通性问题时，**首先使用此工具**！

    💡 **为什么优先使用 ovn-trace？**
    - ✅ 快速定位数据包在 OVN 逻辑网络中的流向
    - ✅ 确定数据包从哪个网卡流出（output_nic）
    - ✅ 判断流量是否被丢弃（final_verdict）及原因
    - ✅ 无需实际发送流量，纯逻辑模拟，速度快

    🔍 **诊断工作流建议**：
    1. **第一步**: 使用 ovn-trace 确定流路径和出网卡
    2. **第二步**: 根据解析结果的 `next_steps` 继续诊断
    3. **判断**:
       - 如果 `final_verdict = "needs_verification"` → 需要实际抓包验证
       - 如果 `final_verdict = "allowed"` + `output_nic` = 物理网卡 → 在物理网卡抓包
       - 如果没有回包 → 外部网络问题（不是 Kube-OVN 问题）
       - 如果 `final_verdict = "dropped"` → 检查 ACL/策略配置

    ✨ **新特性**:
    - 🆕 自动获取 Pod MAC 地址（target_mac 可选）
    - 🆕 智能解析 trace 输出，提取关键信息
    - 🆕 返回结构化数据：output_nic、final_verdict、flow_path
    - 🆕 **智能分析和建议** (`analysis`, `next_steps`):
      - 识别 loopback/omitting output 情况，提示需要实际抓包
      - 区分物理网卡和虚拟网卡，给出不同的建议
      - 针对不同情况提供具体的下一步操作

    支持的协议:
    - icmp: ICMP 协议 (默认)
    - tcp: TCP 协议 (需要 port 参数)
    - udp: UDP 协议 (需要 port 参数)
    - arp: ARP 协议 (需要 arp_type 参数)

    Args:
        target_type: 目标类型 (pod 或 node)
        target_name: 目标名称 (Pod 格式: "namespace/podname")
        target_ip: 目标 IP
        target_mac: 目标 MAC (可选，未提供时自动查询 Pod annotation)
        protocol: 协议类型
        port: 目标端口 (TCP/UDP)
        arp_type: ARP 类型 (ARP)

    Returns:
        格式化的追踪结果，包括原始输出和解析后的结构化数据。
        解析结果包含:
        - output_nic: 流出的网卡
        - final_verdict: 最终裁决 (allowed/dropped/needs_verification)
        - analysis: 智能分析结果
        - next_steps: 建议的下一步操作列表
    """
    collector = K8sResourceCollector()
    result = await collector.collect_ovn_trace(
        target_type=target_type,
        target_name=target_name,
        target_ip=target_ip,
        target_mac=target_mac,
        protocol=protocol,
        port=port,
        arp_type=arp_type
    )

    return format_for_llm(result)


# === T0 快速检查工具 ===

class CollectT0Input(BaseModel):
    """执行 T0 快速检查的参数"""
    namespace: str = Field(
        default="kube-system",
        description="命名空间 (默认 kube-system)"
    )
    pod_name: Optional[str] = Field(
        default=None,
        description="Pod 名称 (可选,用于单 Pod 诊断)"
    )
    scope: str = Field(
        default="cluster",
        description="检查范围: cluster | single"
    )


@tool(args_schema=CollectT0Input)
async def collect_t0_check(
    namespace: str = "kube-system",
    pod_name: Optional[str] = None,
    scope: str = "cluster"
) -> str:
    """
    执行 T0 快速健康检查

    当需要快速验证 Kube-OVN 核心组件健康状态时使用此工具。
    T0 检查 9 个核心组件 (Deployments + DaemonSets + Endpoints)。
    通常 2-3 秒内完成,无需等待即可获得集群健康状态概览。

    检查内容:
    - 3 个 Deployments (kube-ovn-controller, kube-ovn-pinger, etc.)
    - 3 个 DaemonSets (kube-ovn-cni, ovs-ovn, etc.)
    - 3 个 Endpoints (ovn-nb, ovn-sb, ovn-northd)
    - Controller 健康状态
    - Pod 统计信息
    - Subnet 概览

    Args:
        namespace: 命名空间 (默认 kube-system)
        pod_name: Pod 名称 (可选)
        scope: 检查范围 (cluster/single)

    Returns:
        格式化的 T0 检查结果
    """
    result = await collect_t0(
        namespace=namespace,
        pod_name=pod_name,
        scope=scope
    )

    return format_for_llm(result)


# === 工具列表 ===

def get_k8s_tools() -> list:
    """
    获取所有 K8s 资源收集工具

    Returns:
        LangChain Tools 列表
    """
    return [
        # T0 快速检查工具
        collect_t0_check,

        # Pod 工具
        collect_pod_logs,
        collect_pod_describe,
        collect_pod_events,
        collect_pod_ip,

        # Subnet 工具
        collect_subnet_status,

        # Node 工具
        collect_node_info,
        # Node 网络配置工具
        collect_node_ip_addr,
        collect_node_ip_route,
        collect_node_iptables,
        collect_node_ipvs,
        collect_node_sysctl,

        # Controller 日志工具
        collect_kube_ovn_controller_logs,
        collect_kube_ovn_cni_logs,
        collect_ovn_controller_logs,
        collect_ovn_northd_logs,
        collect_ovs_vswitchd_logs,

        # OVN/OVS 诊断工具
        collect_ovn_nbctl,
        collect_ovn_sbctl,
        collect_ovs_vsctl,
        collect_ovs_ofctl,
        collect_ovs_dpctl,
        collect_ovs_appctl,
        collect_tcpdump,
        collect_node_tcpdump,  # 🆕 在节点网卡上抓包
        collect_ovn_trace,
    ]
