#!/usr/bin/env python3
"""
测试 tcpdump 工具的新实现（veth 网卡自动发现）
"""

import asyncio
import json
from kube_ovn_checker.collectors import K8sResourceCollector


async def test_veth_discovery():
    """测试 1: veth 网卡查找功能"""
    print("=" * 60)
    print("🧪 测试 1: veth 网卡查找")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_pod_veth_interface(
        pod_name="kube-ovn-pinger-82zgs",
        namespace="kube-system"
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    if result["success"]:
        print("✅ veth 网卡查找成功！")
        print(f"  节点: {result['node_name']}")
        print(f"  veth_ovs: {result['veth_ovs']}")
        print(f"  veth_host: {result['veth_host']}")
        print(f"  ovs_pod: {result['ovs_pod']}")
        print(f"  网卡类型: {result['pod_nic_type']}")
    else:
        print(f"❌ 失败: {result.get('error')}")

    return result["success"]


async def test_tcpdump_basic():
    """测试 2: 基本流量捕获"""
    print("=" * 60)
    print("🧪 测试 2: 基本流量捕获（10 个包，30 秒超时）")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_tcpdump(
        pod_name="kube-ovn-pinger-82zgs",
        namespace="kube-system",
        count=10,
        timeout=30
    )

    print(f"方法: {result.get('method', 'unknown')}")
    print(f"网卡: {result.get('veth_interface', 'N/A')}")
    print(f"命令: {result.get('command', 'N/A')}")
    print(f"捕获包数: {result.get('packet_count', 0)}")
    print(f"是否超时: {result.get('timeout_reached', False)}")
    print()

    if result["success"]:
        print("✅ tcpdump 执行成功！")
        print("\n捕获的流量:")
        print("-" * 40)
        output = result.get("output", "")
        lines = output.split('\n')[:15]  # 只显示前 15 行
        for line in lines:
            print(line)
        if len(output.split('\n')) > 15:
            remaining = len(output.split('\n')) - 15
            print(f"\n... (还有 {remaining} 行)")
    else:
        print(f"❌ 失败: {result.get('error')}")
        if "hint" in result:
            print(f"💡 提示: {result['hint']}")

    return result["success"]


async def test_tcpdump_with_filter():
    """测试 3: 使用过滤器捕获"""
    print("=" * 60)
    print("🧪 测试 3: 使用过滤器捕获 ICMP 包")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_tcpdump(
        pod_name="kube-ovn-pinger-82zgs",
        namespace="kube-system",
        count=5,
        filter_expr="icmp",
        timeout=20
    )

    print(f"方法: {result.get('method', 'unknown')}")
    print(f"过滤器: icmp")
    print(f"捕获包数: {result.get('packet_count', 0)}")
    print()

    if result["success"]:
        print("✅ 带过滤器的 tcpdump 执行成功！")
        print("\n捕获的 ICMP 流量:")
        print("-" * 40)
        output = result.get("output", "")
        lines = output.split('\n')[:10]
        for line in lines:
            print(line)
    else:
        print(f"❌ 失败: {result.get('error')}")

    return result["success"]


async def test_tcpdump_timeout():
    """测试 4: 超时机制"""
    print("=" * 60)
    print("🧪 测试 4: 超时机制（短超时 + 大包数）")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_tcpdump(
        pod_name="kube-ovn-pinger-82zgs",
        namespace="kube-system",
        count=1000,  # 设置很大的数量
        filter_expr="host 8.8.8.8",  # 不匹配的流量
        timeout=10  # 短超时
    )

    print(f"捕获包数: {result.get('packet_count', 0)}")
    print(f"是否超时: {result.get('timeout_reached', False)}")
    print()

    if result["success"]:
        if result.get("timeout_reached"):
            print("✅ 超时机制正常工作！")
            print(f"💡 {result.get('hint', '')}")
        else:
            print("⚠️  未超时（可能捕获了足够的包）")
    else:
        print(f"❌ 失败: {result.get('error')}")

    return result["success"]


async def test_tcpdump_legacy_mode():
    """测试 5: 旧模式兼容性"""
    print("=" * 60)
    print("🧪 测试 5: 旧模式（kubectl-ko）兼容性")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_tcpdump(
        pod_name="kube-ovn-pinger-82zgs",
        namespace="kube-system",
        count=5,
        timeout=15,
        use_legacy_kubectl_ko=True  # 使用旧模式
    )

    print(f"方法: {result.get('method', 'unknown')}")
    print()

    if result["success"]:
        print("✅ 旧模式兼容性正常！")
        print(f"捕获包数: {result.get('packet_count', 0)}")
    else:
        print(f"❌ 失败: {result.get('error')}")
        if "hint" in result:
            print(f"💡 提示: {result['hint']}")

    return result["success"]


async def main():
    """运行所有测试"""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "tcpdump 工具测试套件" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    tests = [
        ("veth 网卡查找", test_veth_discovery),
        ("基本流量捕获", test_tcpdump_basic),
        ("过滤器捕获", test_tcpdump_with_filter),
        ("超时机制", test_tcpdump_timeout),
        ("旧模式兼容性", test_tcpdump_legacy_mode),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ 异常: {e}")
            results.append((test_name, False))
            import traceback
            traceback.print_exc()

        print()
        print()

    # 总结
    print("=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print()

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {test_name}")

    print()
    print(f"总计: {passed}/{total} 测试通过")
    print()

    if passed == total:
        print("🎉 所有测试通过！tcpdump 工具增强成功！")
    else:
        print("⚠️  部分测试失败，请检查实现")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
