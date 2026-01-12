#!/usr/bin/env python3
"""
测试 ovn-trace 解析改进：loopback omit 情况
"""

from kube_ovn_checker.collectors import K8sResourceCollector


# 实际的 ovn-trace 输出（包含 loopback omit）
SAMPLE_TRACE_OUTPUT = """# icmp,reg14=0x6,vlan_tci=0x0000,dl_src=c2:ea:e3:0e:b1:74,dl_dst=c2:ea:e3:0e:b1:74,nw_src=10.16.0.2,nw_dst=114.114.114.114,nw_tos=0,nw_ecn=0,nw_ttl=255,nw_frag=no,icmp_type=0,icmp_code=0

ingress(dp="ovn-default", inport="kube-ovn-pinger-82zgs.kube-system")
---------------------------------------------------------------------
 0. ls_in_check_port_sec (northd.c:9926): 1, priority 50, uuid a2de298e
    reg0[15] = check_in_port_sec();
    next;
 5. ls_in_pre_lb (northd.c:6393): ip, priority 100, uuid 5d326a95
    reg0[2] = 1;
    next;
 6. ls_in_pre_stateful (northd.c:6571): reg0[2] == 1, priority 110, uuid f9f81c3c
    ct_lb_mark;

ct_lb_mark
----------
 7. ls_in_acl_hint (northd.c:6640): ct.new && !ct.est, priority 7, uuid ee6b262a
    reg0[7] = 1;
    reg0[9] = 1;
    reg0[1] = 1;
    next;
 8. ls_in_acl_eval (northd.c:7757): ip && !ct.est, priority 1, uuid 2e308c2f
    next;
15. ls_in_pre_hairpin (northd.c:8867): ip && ct.trk, priority 100, uuid c524c7e0
    reg0[6] = chk_lb_hairpin();
    reg0[12] = chk_lb_hairpin_reply();
    next;
21. ls_in_stateful (northd.c:8806): reg0[1] == 1 && reg0[13] == 0, priority 100, uuid 59df7026
    ct_commit { ct_mark.blocked = 0; ct_mark.allow_established = reg0[20]; ct_label.acl_id = reg2[16..31]; };
    next;
28. ls_in_l2_lkup (northd.c:10949): eth.dst == c2:ea:e3:0e:b1:74, priority 50, uuid f73ea0d7
    outport = "kube-ovn-pinger-82zgs.kube-system";
    output;
    /* omitting output because inport == outport && !flags.loopback */

--------"""

def test_loopback_parsing():
    """测试 loopback omit 情况的解析"""
    print("=" * 60)
    print("🧪 测试 ovn-trace 解析：loopback omit 情况")
    print("=" * 60)
    print()

    collector = K8sResourceCollector()
    parsed = collector._parse_ovn_trace_output(SAMPLE_TRACE_OUTPUT)

    print("📊 解析结果:")
    print("-" * 60)
    print(f"output_nic: {parsed['output_nic']}")
    print(f"final_verdict: {parsed['final_verdict']}")
    print(f"drop_reason: {parsed.get('drop_reason', 'N/A')}")
    print()

    print("🆕 智能分析:")
    print("-" * 60)
    print(parsed.get('analysis', 'N/A'))
    print()

    print("🎯 建议的下一步:")
    print("-" * 60)
    for i, step in enumerate(parsed.get('next_steps', []), 1):
        print(f"{i}. {step}")
    print()

    # 验证结果
    checks = [
        ("final_verdict = needs_verification", parsed['final_verdict'] == 'needs_verification'),
        ("analysis 包含 loopback 说明", 'loopback' in parsed.get('analysis', '').lower()),
        ("next_steps 包含 collect_tcpdump", any('collect_tcpdump' in s for s in parsed.get('next_steps', []))),
        ("next_steps 包含 collect_node_tcpdump", any('collect_node_tcpdump' in s for s in parsed.get('next_steps', []))),
        ("next_steps 包含检查节点路由", 'collect_node_ip_route' in ''.join(parsed.get('next_steps', []))),
        ("next_steps 包含物理网卡抓包", '物理网卡' in ''.join(parsed.get('next_steps', []))),
    ]

    print("✅ 验证结果:")
    print("-" * 60)
    all_passed = True
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"{status} {check_name}")
        if not check_result:
            all_passed = False

    print()
    if all_passed:
        print("🎉 所有检查通过！loopback omit 情况正确识别！")
        print()
        print("💡 这样 LLM Agent 就会得到正确的提示：")
        print("   - 不是流量被丢弃，而是需要实际抓包验证")
        print("   - 第一步: 使用 collect_tcpdump 抓 Pod veth")
        print("   - 第二步: 使用 collect_node_ip_route 检查路由")
        print("   - 第三步: 使用 collect_node_tcpdump 抓物理网卡")
        print("   - 通过实际流量判断是外部网络问题")
    else:
        print("⚠️  部分检查失败，需要调整解析逻辑")

    return all_passed


def test_physical_nic_output():
    """测试物理网卡输出情况的解析"""
    print()
    print("=" * 60)
    print("🧪 测试 ovn-trace 解析：物理网卡输出")
    print("=" * 60)
    print()

    # 模拟输出到物理网卡的 trace
    trace_with_physical_nic = """# icmp,...
ingress(dp="ovn-default", inport="xxx")
---------------------------------------------------------------------
...
output port eth0;
--------"""

    collector = K8sResourceCollector()
    parsed = collector._parse_ovn_trace_output(trace_with_physical_nic)

    print("📊 解析结果:")
    print("-" * 60)
    print(f"output_nic: {parsed['output_nic']}")
    print(f"final_verdict: {parsed['final_verdict']}")
    print()

    print("🆕 智能分析:")
    print("-" * 60)
    print(parsed.get('analysis', 'N/A'))
    print()

    print("🎯 建议的下一步:")
    print("-" * 60)
    for i, step in enumerate(parsed.get('next_steps', []), 1):
        print(f"{i}. {step}")
    print()

    # 验证
    checks = [
        ("output_nic = eth0", parsed['output_nic'] == 'eth0'),
        ("final_verdict = allowed", parsed['final_verdict'] == 'allowed'),
        ("analysis 提到物理网卡", '物理网卡' in parsed.get('analysis', '')),
        ("next_steps 包含外部网络判断", '外部网络' in ''.join(parsed.get('next_steps', []))),
    ]

    print("✅ 验证结果:")
    print("-" * 60)
    all_passed = True
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"{status} {check_name}")
        if not check_result:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "ovn-trace 解析改进测试" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    result1 = test_loopback_parsing()
    result2 = test_physical_nic_output()

    print()
    print("=" * 60)
    print("📊 总体测试结果")
    print("=" * 60)
    print()

    if result1 and result2:
        print("🎉 所有测试通过！ovn-trace 解析改进成功！")
        print()
        print("✨ 主要改进:")
        print("   1. ✅ 正确识别 loopback omit 情况")
        print("   2. ✅ 提供智能分析和下一步建议")
        print("   3. ✅ 区分物理网卡和虚拟网卡")
        print("   4. ✅ 引导 LLM Agent 走正确的诊断流程")
        print()
        print("📚 现在的流程:")
        print("   ovn-trace → 发现 needs_verification → tcpdump ovn0")
        print("            → 检查节点路由 → 物理网卡抓包 → 判断外部网络问题")
    else:
        print("⚠️  部分测试失败，需要继续改进")
