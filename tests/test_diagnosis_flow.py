#!/usr/bin/env python3
"""
测试完整的诊断流程 - 验证 loopback omit 改进

这个脚本模拟 LLM Agent 的决策过程,验证改进后的解析是否引导正确的诊断流程
"""

import asyncio
import json
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


def print_section(title: str):
    """打印分隔符"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


async def simulate_llm_agent_decision(parsed: dict):
    """
    模拟 LLM Agent 的决策过程

    基于 parsed 结果决定下一步操作
    """
    print("🤖 LLM Agent 决策过程:")
    print("-" * 70)

    # 1. 检查 final_verdict
    verdict = parsed.get("final_verdict")
    print(f"📊 final_verdict: {verdict}")

    if verdict == "needs_verification":
        print("✅ 识别为需要验证的情况（不是真正的 dropped）")

        # 2. 读取 analysis
        analysis = parsed.get("analysis", "")
        print(f"💡 分析: {analysis}")

        # 3. 查看 next_steps
        next_steps = parsed.get("next_steps", [])
        print(f"🎯 建议的下一步:")
        for i, step in enumerate(next_steps, 1):
            print(f"   {i}. {step}")

        print()
        print("✅ 决策: 按照 next_steps 继续诊断")
        print()
        print("预期流程:")
        print("  1. 使用 tcpdump 在 ovn0 网卡抓包")
        print("  2. 检查节点路由表，确认出口网卡")
        print("  3. 在出口物理网卡抓包")
        print("  4. 如果包出去但没有回复 → 外部网络问题")

        return True

    elif verdict == "dropped":
        print("❌ 识别为流量被丢弃")
        reason = parsed.get("drop_reason", "unknown")
        print(f"   原因: {reason}")
        print()
        print("决策: 检查 ACL/网络策略配置")
        return False

    elif verdict == "allowed":
        output_nic = parsed.get("output_nic")
        print(f"✅ 流量被允许，将从 {output_nic} 流出")

        if output_nic:
            print(f"   决策: 在 {output_nic} 上抓包验证")
        else:
            print("   决策: 需要进一步分析")

        return True

    else:
        print(f"⚠️  未知的裁决状态: {verdict}")
        return False


async def test_diagnosis_flow():
    """测试完整的诊断流程"""

    print_section("🧪 测试诊断流程 - Loopback Omit 情况")

    # 1. 解析 ovn-trace 输出
    print("步骤 1: 解析 ovn-trace 输出")
    print("-" * 70)

    collector = K8sResourceCollector()
    parsed = collector._parse_ovn_trace_output(SAMPLE_TRACE_OUTPUT)

    print("✅ 解析完成")
    print()
    print("解析结果:")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    print()

    # 2. 验证关键字段
    print_section("步骤 2: 验证关键字段")

    checks = {
        "final_verdict": parsed["final_verdict"] == "needs_verification",
        "has_analysis": bool(parsed.get("analysis")),
        "has_next_steps": len(parsed.get("next_steps", [])) > 0,
        "loopback_in_analysis": "loopback" in parsed.get("analysis", "").lower(),
        "tcpdump_ovn0_in_steps": any("ovn0" in s for s in parsed.get("next_steps", [])),
        "check_routing_in_steps": any("路由" in s for s in parsed.get("next_steps", [])),
        "physical_nic_in_steps": any("物理网卡" in s for s in parsed.get("next_steps", [])),
    }

    print("验证结果:")
    all_passed = True
    for check_name, check_result in checks.items():
        status = "✅" if check_result else "❌"
        print(f"  {status} {check_name}")
        if not check_result:
            all_passed = False

    print()

    if not all_passed:
        print("❌ 部分验证失败！")
        return False

    # 3. 模拟 LLM Agent 决策
    print_section("步骤 3: 模拟 LLM Agent 决策")

    correct_decision = await simulate_llm_agent_decision(parsed)

    # 4. 总结
    print_section("📊 测试总结")

    if all_passed and correct_decision:
        print("🎉 所有测试通过！")
        print()
        print("✨ 主要改进:")
        print("  1. ✅ 正确识别 loopback omit 情况")
        print("  2. ✅ 返回 needs_verification 而非 dropped")
        print("  3. ✅ 提供清晰的 analysis 说明")
        print("  4. ✅ 给出具体的 next_steps 指导")
        print("  5. ✅ LLM Agent 能做出正确的诊断决策")
        print()
        print("💡 现在的诊断流程:")
        print("   ovn-trace → needs_verification → tcpdump ovn0")
        print("            → 检查路由 → tcpdump 物理网卡")
        print("            → 正确判断: 外部网络问题")
        print()
        return True
    else:
        print("❌ 测试失败")
        return False


async def main():
    """主函数"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "诊断流程测试 - Loopback Omit" + " " * 14 + "║")
    print("╚" + "═" * 68 + "╝")

    success = await test_diagnosis_flow()

    print()
    if success:
        print("✅ 测试成功！改进已验证！")
        print()
    else:
        print("❌ 测试失败！需要进一步调试！")
        print()

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
