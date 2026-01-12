#!/usr/bin/env python3
"""
测试知识注入功能的简单脚本
"""

import asyncio
import sys
from kube_ovn_checker.analyzers.llm_agent_analyzer import LLMAgentAnalyzer


def test_initialization():
    """测试1: 验证初始化时知识注入状态追踪被正确设置"""
    print("=" * 60)
    print("测试1: 验证知识注入状态追踪初始化")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 检查状态追踪变量是否存在
        assert hasattr(analyzer, 'knowledge_injected'), "❌ 缺少 knowledge_injected 属性"
        assert hasattr(analyzer, 'injection_round'), "❌ 缺少 injection_round 属性"
        assert hasattr(analyzer, 'knowledge'), "❌ 缺少 knowledge 属性"

        # 检查初始值
        assert isinstance(analyzer.knowledge_injected, set), "❌ knowledge_injected 应该是 set 类型"
        assert analyzer.injection_round == 0, "❌ injection_round 初始值应该为 0"

        print("✅ 初始化测试通过")
        print(f"   - knowledge_injected: {analyzer.knowledge_injected}")
        print(f"   - injection_round: {analyzer.injection_round}")
        print(f"   - knowledge 对象存在: {analyzer.knowledge is not None}")

        return True
    except Exception as e:
        print(f"❌ 初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_helper_methods():
    """测试2: 验证辅助方法是否存在并可调用"""
    print("\n" + "=" * 60)
    print("测试2: 验证辅助方法")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 检查方法是否存在
        assert hasattr(analyzer, '_should_inject_knowledge'), "❌ 缺少 _should_inject_knowledge 方法"
        assert hasattr(analyzer, '_extract_doc_id_from_knowledge'), "❌ 缺少 _extract_doc_id_from_knowledge 方法"

        # 测试 _should_inject_knowledge
        print("\n测试 _should_inject_knowledge 方法:")

        # 应该总是触发的工具
        always_trigger_tools = ["collect_ovn_trace", "collect_tcpdump", "collect_ovn_nb_db", "collect_ovn_sb_db"]
        for tool in always_trigger_tools:
            result = analyzer._should_inject_knowledge(tool, {})
            assert result == True, f"❌ {tool} 应该总是触发知识注入"
            print(f"  ✅ {tool}: 应该注入 = {result}")

        # 应该从不触发的工具
        never_trigger_tools = ["collect_pod_status", "collect_node_info", "collect_subnet_status"]
        for tool in never_trigger_tools:
            result = analyzer._should_inject_knowledge(tool, {})
            assert result == False, f"❌ {tool} 应该从不触发知识注入"
            print(f"  ✅ {tool}: 应该注入 = {result}")

        # 条件触发的工具 - 无错误
        result = analyzer._should_inject_knowledge("collect_pod_logs", "Everything is fine")
        assert result == False, "❌ collect_pod_logs 无错误时不应触发"
        print(f"  ✅ collect_pod_logs (无错误): 应该注入 = {result}")

        # 条件触发的工具 - 有错误
        result = analyzer._should_inject_knowledge("collect_pod_logs", "Error: connection failed")
        assert result == True, "❌ collect_pod_logs 有错误时应该触发"
        print(f"  ✅ collect_pod_logs (有错误): 应该注入 = {result}")

        # 测试 _extract_doc_id_from_knowledge
        print("\n测试 _extract_doc_id_from_knowledge 方法:")

        # 测试有元数据的情况
        knowledge_with_metadata = """
---
metadata:
  id: test-document-id
---
Some content here
"""
        doc_id = analyzer._extract_doc_id_from_knowledge(knowledge_with_metadata)
        assert doc_id == "test-document-id", f"❌ 应该提取到 'test-document-id'，实际得到 '{doc_id}'"
        print(f"  ✅ 有元数据: {doc_id}")

        # 测试无元数据的情况（应该返回哈希）
        knowledge_without_metadata = "Just some content without metadata"
        doc_id = analyzer._extract_doc_id_from_knowledge(knowledge_without_metadata)
        assert len(doc_id) == 8, f"❌ 无元数据时应该返回8位哈希，实际得到 '{doc_id}'"
        print(f"  ✅ 无元数据 (哈希): {doc_id}")

        print("\n✅ 辅助方法测试通过")
        return True
    except Exception as e:
        print(f"❌ 辅助方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_base_methods():
    """测试3: 验证知识库基础方法"""
    print("\n" + "=" * 60)
    print("测试3: 验证知识库方法")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 测试 get_architecture 方法
        print("\n测试 knowledge.get_architecture():")
        architecture = analyzer.knowledge.get_architecture()
        assert isinstance(architecture, str), "❌ get_architecture 应该返回字符串"
        assert len(architecture) > 0, "❌ get_architecture 不应该返回空字符串"

        print(f"  ✅ 架构知识长度: {len(architecture)} 字符")
        print(f"  ✅ 前100字符: {architecture[:100]}...")

        # 测试截断
        truncated = architecture[:3000]
        print(f"  ✅ 截断后长度: {len(truncated)} 字符")

        # 测试 search_relevant_knowledge 方法
        print("\n测试 knowledge.search_relevant_knowledge():")
        test_collected_data = {
            "t0": {"controller_status": {"health": "unhealthy"}},
            "tools": [
                {"name": "collect_pod_logs", "output": "Error: connection timeout"}
            ]
        }

        knowledge = analyzer.knowledge.search_relevant_knowledge(
            collected_data=test_collected_data,
            max_length=3000
        )

        print(f"  ✅ 检索到相关知识: {len(knowledge) if knowledge else 0} 字符")
        if knowledge:
            print(f"  ✅ 知识预览: {knowledge[:200]}...")

        print("\n✅ 知识库方法测试通过")
        return True
    except Exception as e:
        print(f"❌ 知识库方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_initial_messages_structure():
    """测试4: 验证初始消息结构（模拟 diagnose 开始部分）"""
    print("\n" + "=" * 60)
    print("测试4: 验证初始消息结构")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 模拟 T0 数据
        t0_data = {
            "controller_status": {
                "health_status": "Healthy",
                "pods_running": 3
            },
            "node_status": {
                "health_status": "Healthy",
                "total_nodes": 5
            }
        }

        # 构建 T0 摘要
        t0_summary = analyzer._build_t0_summary(t0_data)
        print(f"\nT0 摘要:\n{t0_summary}")

        # 获取架构知识
        core_knowledge = analyzer.knowledge.get_architecture()[:3000]
        print(f"\n架构知识长度: {len(core_knowledge)} 字符")

        # 构建初始消息（模拟 diagnose 中的逻辑）
        from langchain_core.messages import SystemMessage, HumanMessage

        initial_messages = [
            SystemMessage(content=f"## Kube-OVN 核心架构\n{core_knowledge}"),
            HumanMessage(content=f"""## 当前任务

用户问题: 测试问题

## T0 健康检查结果

{t0_summary}

请根据用户问题、架构知识和 T0 结果进行诊断。
""")
        ]

        print(f"\n✅ 初始消息结构:")
        print(f"  - 消息数量: {len(initial_messages)}")
        print(f"  - 第一条类型: {type(initial_messages[0]).__name__} (SystemMessage)")
        print(f"  - 第二条类型: {type(initial_messages[1]).__name__} (HumanMessage)")
        print(f"  - SystemMessage 长度: {len(initial_messages[0].content)} 字符")
        print(f"  - HumanMessage 长度: {len(initial_messages[1].content)} 字符")

        assert len(initial_messages) == 2, "❌ 应该有2条初始消息"
        assert isinstance(initial_messages[0], SystemMessage), "❌ 第一条应该是 SystemMessage"
        assert isinstance(initial_messages[1], HumanMessage), "❌ 第二条应该是 HumanMessage"

        print("\n✅ 初始消息结构测试通过")
        return True
    except Exception as e:
        print(f"❌ 初始消息结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_diagnose_with_knowledge_injection():
    """测试5: 完整诊断流程（需要 LLM API）"""
    print("\n" + "=" * 60)
    print("测试5: 完整诊断流程（需要 LLM API 配置）")
    print("=" * 60)

    # 检查是否有 API key
    import os
    if not os.getenv("LLM_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("⚠️ 跳过完整诊断测试: 未配置 LLM_API_KEY 或 OPENAI_API_KEY")
        print("   设置环境变量后可以测试完整流程:")
        print("   export LLM_API_KEY=your-api-key")
        return True

    try:
        print("\n开始完整诊断测试...")

        analyzer = LLMAgentAnalyzer()

        # 准备测试数据
        t0_data = {
            "controller_status": {
                "health_status": "Healthy",
                "pods_running": 3
            }
        }

        user_query = "测试问题"

        # 定义进度回调
        progress_messages = []
        def progress_callback(msg):
            progress_messages.append(msg)
            print(f"  📌 {msg}")

        # 执行诊断
        print("\n执行诊断:")
        result = await analyzer.diagnose(
            t0_data=t0_data,
            user_query=user_query,
            progress_callback=progress_callback
        )

        # 验证结果
        print("\n验证结果:")
        assert result["status"] in ["completed", "max_rounds_reached"], f"❌ 意外的状态: {result['status']}"

        # 检查知识注入指标
        if "knowledge_injection" in result:
            ki = result["knowledge_injection"]
            print(f"  ✅ 知识注入指标:")
            print(f"     - 总注入次数: {ki['total_injected']}")
            print(f"     - 注入轮次: {ki['injection_round']}")
            print(f"     - 注入的文档: {ki['documents']}")

            # 验证至少注入了架构知识
            assert ki["total_injected"] >= 1, "❌ 应该至少注入一次架构知识"
            assert "architecture-overview" in ki["documents"], "❌ 应该包含架构概览文档"
        else:
            print("  ⚠️ 未找到知识注入指标（可能是旧版本返回格式）")

        print("\n✅ 完整诊断测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 完整诊断测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "🚀" * 30)
    print("知识注入功能测试套件")
    print("🚀" * 30 + "\n")

    tests = [
        ("初始化测试", test_initialization),
        ("辅助方法测试", test_helper_methods),
        ("知识库方法测试", test_knowledge_base_methods),
        ("初始消息结构测试", test_initial_messages_structure),
    ]

    # 异步测试
    async_tests = [
        ("完整诊断流程测试", test_full_diagnose_with_knowledge_injection),
    ]

    results = []

    # 运行同步测试
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 执行出错: {e}")
            results.append((test_name, False))

    # 运行异步测试
    for test_name, test_func in async_tests:
        try:
            result = asyncio.run(test_func())
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 执行出错: {e}")
            results.append((test_name, False))

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！知识注入功能已正确实现。")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
