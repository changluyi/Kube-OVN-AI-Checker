#!/usr/bin/env python3
"""
测试思维链输出格式
"""

from rich.console import Console
from kube_ovn_checker.cli.main import print_diagnosis_result


def test_thought_chain_display():
    """测试思维链显示"""

    # 模拟诊断结果
    mock_result = {
        "status": "completed",
        "rounds": [
            {
                "thought": "用户报告 kube-ovn-pinger 无法访问外部 IP，这是网络连通性问题。根据诊断策略，我应该首先使用 ovn-trace 分析逻辑路径。",
                "tool_name": "collect_pod_describe",
                "tool_input": {
                    "pod_name": "kube-ovn-pinger-82zgs",
                    "namespace": "kube-system"
                }
            },
            {
                "thought": "现在我有 Pod 的基本信息，IP 是 10.16.0.2。根据网络连通性诊断工作流，我需要使用 ovn-trace 分析逻辑路径。",
                "tool_name": "collect_ovn_trace",
                "tool_input": {
                    "target_type": "pod",
                    "target_name": "kube-system/kube-ovn-pinger-82zgs",
                    "target_ip": "114.114.114.114",
                    "protocol": "icmp"
                }
            },
            {
                "thought": "ovn-trace 显示流量遇到 loopback 检查，这是逻辑模拟的限制。需要在 Pod 的 veth 上抓包验证流量是否真正离开 Pod。",
                "tool_name": "collect_tcpdump",
                "tool_input": {
                    "pod_name": "kube-ovn-pinger-82zgs",
                    "namespace": "kube-system",
                    "filter_expr": "icmp and host 114.114.114.114"
                }
            },
            {
                "thought": "Pod veth 上有 ICMP 请求包发出，说明流量成功离开 Pod。现在需要检查节点路由表，确定流量从哪个物理网卡出去。",
                "tool_name": "collect_node_ip_route",
                "tool_input": {
                    "node_name": "kube-ovn-control-plane"
                }
            },
            {
                "thought": "路由表显示默认路由通过 eth0 网卡出去。现在需要在 eth0 网卡上抓包，验证流量是否真正离开节点。",
                "tool_name": "collect_node_tcpdump",
                "tool_input": {
                    "node_name": "kube-ovn-control-plane",
                    "interface": "eth0",
                    "filter_expr": "icmp and host 114.114.114.114"
                }
            },
            {
                "thought": "流量成功从节点的 eth0 网卡发出，源 IP 是 172.18.0.2（经过 NAT），但没有看到回复包。这表明问题不在 Kube-OVN 内部，而是外部网络问题。",
                "tool_name": "collect_pod_logs",
                "tool_input": {
                    "pod_name": "kube-ovn-pinger-82zgs",
                    "namespace": "kube-system",
                    "tail": 50
                }
            }
        ],
        "diagnosis": {
            "problem": "kube-ovn-pinger 无法访问 114.114.114.114",
            "root_cause": "外部网络问题，不是 Kube-OVN 配置问题",
            "solution": "检查外部网络连接和防火墙配置",
            "evidence": [
                "ovn-trace 显示流量逻辑路径正常",
                "Pod veth 上有 ICMP 请求包",
                "节点 eth0 上有 NAT 后的 ICMP 请求包",
                "eth0 上没有 ICMP 回复包"
            ]
        },
        "collected_data": {
            "tools": [
                {"name": "collect_pod_describe"},
                {"name": "collect_ovn_trace"},
                {"name": "collect_tcpdump"},
                {"name": "collect_node_ip_route"},
                {"name": "collect_node_tcpdump"},
                {"name": "collect_pod_logs"}
            ]
        }
    }

    console = Console()
    console.print()

    print_diagnosis_result(mock_result)


if __name__ == "__main__":
    test_thought_chain_display()
