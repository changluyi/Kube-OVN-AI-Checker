#!/usr/bin/env python3
"""
测试实际诊断的思维链捕获

这个脚本会模拟真实的诊断流程，验证是否正确捕获思维链
"""

import asyncio
import json
from kube_ovn_checker.analyzers.llm_agent_analyzer import LLMAgentAnalyzer


async def test_real_diagnosis_structure():
    """测试真实诊断的数据结构"""

    print("🧪 测试真实诊断流程的数据结构...")
    print()

    # 创建 Analyzer（使用较便宜的模型用于测试）
    analyzer = LLMAgentAnalyzer(
        model="gpt-4o-mini",
        temperature=0.0,
        max_rounds=3  # 限制轮数，快速测试
    )

    # 模拟一个简单的问题
    user_query = "kube-ovn-pinger 无法访问外部 IP"

    print(f"📝 问题: {user_query}")
    print()

    # 执行诊断
    result = await analyzer.diagnose(
        t0_data={},
        user_query=user_query,
        progress_callback=lambda msg: print(f"  {msg}")
    )

    print()
    print("=" * 70)
    print("📊 诊断结果结构分析:")
    print("=" * 70)
    print()

    # 检查 rounds 字段
    rounds = result.get("rounds")
    print(f"1. rounds 类型: {type(rounds)}")

    if isinstance(rounds, list):
        print(f"   ✅ rounds 是列表，包含 {len(rounds)} 个轮次")
        print()

        # 分析每个轮次的结构
        for i, round_data in enumerate(rounds, 1):
            print(f"   第 {i} 轮:")
            if isinstance(round_data, dict):
                for key in round_data.keys():
                    print(f"     - {key}")

                # 检查关键字段
                if "thought" in round_data:
                    thought = round_data["thought"]
                    if thought:
                        thought_preview = thought[:100] + "..." if len(thought) > 100 else thought
                        print(f"     💭 thought: {thought_preview}")
                    else:
                        print(f"     ⚠️  thought 为空")

                if "tool_name" in round_data:
                    print(f"     🔧 tool_name: {round_data['tool_name']}")

                if "tool_input" in round_data:
                    print(f"     📥 tool_input: {type(round_data['tool_input'])}")
            else:
                print(f"     ⚠️  轮次数据类型错误: {type(round_data)}")
            print()
    else:
        print(f"   ❌ rounds 不是列表，而是: {rounds}")
        print()

    # 保存完整的诊断报告用于检查
    timestamp = __import__('time').strftime("%Y%m%d_%H%M%S")
    report_file = f"test_diagnosis_structure_{timestamp}.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"💾 完整报告已保存: {report_file}")
    print()

    # 总结
    print("=" * 70)
    print("✅ 测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_real_diagnosis_structure())
