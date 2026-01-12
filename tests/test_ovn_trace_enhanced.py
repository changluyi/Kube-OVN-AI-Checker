#!/usr/bin/env python3
"""
测试 ovn-trace 工具的增强功能
"""

import asyncio
import json
from kube_ovn_checker.collectors import K8sResourceCollector


async def test_auto_mac_fetch():
    """测试 1: 自动获取 MAC 地址"""
    print("=" * 60)
    print("🧪 测试 1: 自动获取 Pod MAC 地址")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    # 不提供 target_mac，应该自动获取
    result = await collector.collect_ovn_trace(
        target_type="pod",
        target_name="kube-system/kube-ovn-pinger-82zgs",
        target_ip="114.114.114.114",
        protocol="icmp"
        # 注意：没有提供 target_mac
    )

    print(f"目标: {result.get('target', 'N/A')}")
    print(f"目标 IP: {result.get('target_ip', 'N/A')}")
    print(f"实际 MAC: {result.get('target_mac', 'N/A')}")
    print(f"协议: {result.get('protocol', 'N/A')}")
    print(f"自动获取 MAC: {result.get('auto_fetched_mac', False)}")
    print()

    if result["success"]:
        print("✅ ovn-trace 执行成功！")
        print(f"\n原始输出预览 (前 20 行):")
        print("-" * 40)
        output = result.get("trace_output", "")
        lines = output.split('\n')[:20]
        for line in lines:
            print(line)
        if len(output.split('\n')) > 20:
            remaining = len(output.split('\n')) - 20
            print(f"\n... (还有 {remaining} 行)")

        # 显示解析结果
        print(f"\n📊 解析结果:")
        print("-" * 40)
        parsed = result.get("parsed", {})
        print(f"输出网卡: {parsed.get('output_nic', 'N/A')}")
        print(f"最终裁决: {parsed.get('final_verdict', 'N/A')}")
        if parsed.get('drop_reason'):
            print(f"丢弃原因: {parsed['drop_reason']}")
        print(f"\n关键流路径 (前 5 条):")
        for i, path in enumerate(parsed.get('flow_path', [])[:5], 1):
            print(f"  {i}. {path}")
    else:
        print(f"❌ 失败: {result.get('error')}")
        if "hint" in result:
            print(f"💡 提示: {result['hint']}")

    return result["success"]


async def test_manual_mac():
    """测试 2: 手动提供 MAC 地址"""
    print()
    print("=" * 60)
    print("🧪 测试 2: 手动提供 MAC 地址")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    # 手动提供 MAC 地址
    result = await collector.collect_ovn_trace(
        target_type="pod",
        target_name="kube-system/kube-ovn-pinger-82zgs",
        target_ip="10.244.0.1",
        target_mac="00:00:00:AA:BB:CC",  # 手动指定
        protocol="icmp"
    )

    print(f"目标: {result.get('target', 'N/A')}")
    print(f"目标 IP: {result.get('target_ip', 'N/A')}")
    print(f"使用的 MAC: {result.get('target_mac', 'N/A')}")
    print(f"自动获取 MAC: {result.get('auto_fetched_mac', False)}")
    print()

    if result["success"]:
        print("✅ 手动 MAC 模式成功！")

        parsed = result.get("parsed", {})
        print(f"\n解析结果:")
        print(f"  输出网卡: {parsed.get('output_nic', 'N/A')}")
        print(f"  最终裁决: {parsed.get('final_verdict', 'N/A')}")
    else:
        print(f"❌ 失败: {result.get('error')}")

    return result["success"]


async def test_trace_parsing():
    """测试 3: trace 输出解析"""
    print()
    print("=" * 60)
    print("🧪 测试 3: 智能解析 ovn-trace 输出")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    result = await collector.collect_ovn_trace(
        target_type="pod",
        target_name="kube-system/kube-ovn-pinger-82zgs",
        target_ip="192.168.1.1",
        protocol="icmp"
    )

    if result["success"]:
        print("✅ ovn-trace 执行成功！")
        print(f"\n📊 解析结果详情:")
        print("-" * 40)

        parsed = result.get("parsed", {})

        print(f"1. 输出网卡: {parsed.get('output_nic', 'N/A')}")
        print(f"2. 最终裁决: {parsed.get('final_verdict', 'N/A')}")

        if parsed.get('drop_reason'):
            print(f"3. 丢弃原因: {parsed['drop_reason']}")

        print(f"\n4. 关键阶段:")
        key_stages = parsed.get('key_stages', {})
        for stage_name, stage_info in key_stages.items():
            print(f"   - {stage_name}: {stage_info[:80]}...")

        print(f"\n5. 完整流路径 (前 10 条):")
        flow_path = parsed.get('flow_path', [])
        if flow_path:
            for i, path in enumerate(flow_path[:10], 1):
                print(f"   {i}. {path}")
        else:
            print("   (无流路径信息)")

        # 验证解析质量
        print(f"\n✅ 解析质量评估:")
        checks = [
            ("output_nic 已识别", parsed.get('output_nic') is not None),
            ("final_verdict 已确定", parsed.get('final_verdict') in ['allowed', 'dropped']),
            ("flow_path 已提取", len(parsed.get('flow_path', [])) > 0),
        ]

        all_passed = True
        for check_name, check_result in checks:
            status = "✅" if check_result else "⚠️"
            print(f"   {status} {check_name}")
            if not check_result:
                all_passed = False

        return all_passed
    else:
        print(f"❌ 失败: {result.get('error')}")
        return False


async def test_different_protocols():
    """测试 4: 不同协议的支持"""
    print()
    print("=" * 60)
    print("🧪 测试 4: 不同协议的支持")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    test_cases = [
        {
            "name": "ICMP",
            "params": {
                "target_type": "pod",
                "target_name": "kube-system/kube-ovn-pinger-82zgs",
                "target_ip": "8.8.8.8",
                "protocol": "icmp"
            }
        },
        {
            "name": "TCP with port",
            "params": {
                "target_type": "pod",
                "target_name": "kube-system/kube-ovn-pinger-82zgs",
                "target_ip": "8.8.8.8",
                "protocol": "tcp",
                "port": 443
            }
        },
    ]

    all_passed = True

    for test_case in test_cases:
        print(f"\n测试 {test_case['name']}...")
        result = await collector.collect_ovn_trace(**test_case['params'])

        if result["success"]:
            parsed = result.get("parsed", {})
            print(f"  ✅ 成功")
            print(f"     输出网卡: {parsed.get('output_nic', 'N/A')}")
            print(f"     裁决: {parsed.get('final_verdict', 'N/A')}")
        else:
            print(f"  ❌ 失败: {result.get('error')}")
            all_passed = False

    return all_passed


async def test_error_handling():
    """测试 5: 错误处理"""
    print()
    print("=" * 60)
    print("🧪 测试 5: 错误处理")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()

    # 测试无效的 Pod（无法获取 MAC）
    print("测试 1: 无效的 Pod 名称...")
    result = await collector.collect_ovn_trace(
        target_type="pod",
        target_name="invalid-namespace/invalid-pod",
        target_ip="1.2.3.4",
        protocol="icmp"
    )

    if not result["success"]:
        print(f"✅ 正确处理无效 Pod")
        print(f"   错误信息: {result.get('error', 'N/A')[:100]}...")
        if "hint" in result:
            print(f"   提示: {result['hint']}")
        test1_passed = True
    else:
        print(f"⚠️  意外成功")
        test1_passed = False

    return test1_passed


async def main():
    """运行所有测试"""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "ovn-trace 增强功能测试" + " " * 19 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    tests = [
        ("自动获取 MAC 地址", test_auto_mac_fetch),
        ("手动提供 MAC 地址", test_manual_mac),
        ("智能解析 trace 输出", test_trace_parsing),
        ("不同协议支持", test_different_protocols),
        ("错误处理", test_error_handling),
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
        print("🎉 所有测试通过！ovn-trace 工具增强成功！")
        print()
        print("✨ 主要改进:")
        print("   - ✅ 自动获取 Pod MAC 地址")
        print("   - ✅ 智能解析 trace 输出")
        print("   - ✅ 提取 output_nic、final_verdict 等关键信息")
        print("   - ✅ 结构化流路径展示")
        print()
        print("📚 使用建议:")
        print("   1. 网络诊断时，首先使用 ovn-trace 确定流路径")
        print("   2. 根据解析结果，确定出网卡和裁决结果")
        print("   3. 如果流量未被丢弃，再在出网卡上抓包（tcpdump）")
        print("   4. 这样可以更快定位问题，减少诊断轮次")
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
