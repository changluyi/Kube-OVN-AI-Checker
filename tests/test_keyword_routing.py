#!/usr/bin/env python3
"""
测试关键词匹配功能的简单脚本
"""

import sys
from kube_ovn_checker.analyzers.llm_agent_analyzer import LLMAgentAnalyzer


def test_keyword_extraction():
    """测试1: 关键词提取"""
    print("=" * 60)
    print("测试1: 关键词提取")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 测试提取 network-connectivity.md 的关键词
        from pathlib import Path
        doc = Path("kube_ovn_checker/knowledge/workflows/network-connectivity.md")
        keywords = analyzer._extract_search_keywords(doc)

        print(f"\n✅ 关键词提取成功:")
        print(f"   文档: {doc.name}")
        print(f"   关键词: {keywords}")

        # 验证关键词
        expected_keywords = ["网络", "ping", "连通", "连接", "不通", "timeout", "无法访问", "通信"]
        for kw in expected_keywords:
            assert kw in keywords, f"❌ 缺少关键词: {kw}"

        print(f"\n✅ 所有预期关键词都存在")

        return True
    except Exception as e:
        print(f"❌ 关键词提取测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_keyword_matching():
    """测试2: 关键词匹配"""
    print("\n" + "=" * 60)
    print("测试2: 关键词匹配")
    print("=" * 60)

    try:
        from pathlib import Path
        analyzer = LLMAgentAnalyzer()

        # 测试场景
        test_cases = [
            {
                "query": "Pod间网络不通",
                "expected_contains": ["network-connectivity.md"],
                "description": "网络问题"
            },
            {
                "query": "IP地址耗尽，无法分配",
                "expected_contains": ["ip-management.md"],
                "description": "IP管理问题"
            },
            {
                "query": "Pod一直ContainerCreating",
                "expected_contains": ["ip-management.md"],
                "description": "Pod启动问题（与IP相关）"
            },
            {
                "query": "未知问题",
                "expected_contains": ["general.md"],
                "description": "通用问题"
            }
        ]

        all_passed = True
        for i, case in enumerate(test_cases, 1):
            query = case["query"]
            expected = case["expected_contains"]
            desc = case["description"]

            print(f"\n测试 {i}: {desc}")
            print(f"  查询: {query}")

            matched = analyzer._match_knowledge_docs(query)

            print(f"  匹配的文档: {[Path(doc).name for doc in matched]}")

            # 验证
            for exp in expected:
                if not any(exp in doc for doc in matched):
                    print(f"  ❌ 应该匹配 {exp}")
                    all_passed = False
                else:
                    print(f"  ✅ 正确匹配 {exp}")

        if all_passed:
            print(f"\n✅ 所有关键词匹配测试通过")
        else:
            print(f"\n⚠️  有部分测试失败")

        return all_passed
    except Exception as e:
        print(f"❌ 关键词匹配测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_loading():
    """测试3: 工作流加载"""
    print("\n" + "=" * 60)
    print("测试3: 工作流加载")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 测试加载网络连通性工作流
        query = "Pod间ping不通"
        matched_docs = analyzer._match_knowledge_docs(query)

        print(f"\n查询: {query}")
        print(f"匹配文档数: {len(matched_docs)}")

        # 读取并验证内容
        for doc_path in matched_docs:
            from pathlib import Path
            content = Path(doc_path).read_text(encoding='utf-8')

            # 检查是否包含预期内容
            if "network-connectivity" in doc_path:
                assert "ovn-trace" in content, "❌ 应该包含 ovn-trace"
                assert "tcpdump" in content, "❌ 应该包含 tcpdump"
                print(f"  ✅ {Path(doc_path).name}: 包含 ovn-trace 和 tcpdump")
            elif "general" in doc_path:
                assert "诊断方法论" in content, "❌ 应该包含诊断方法论"
                print(f"  ✅ {Path(doc_path).name}: 包含诊断方法论")
            else:
                print(f"  ✅ {Path(doc_path).name}: 加载成功")

        print(f"\n✅ 工作流加载测试通过")
        return True
    except Exception as e:
        print(f"❌ 工作流加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试4: 集成测试（模拟 diagnose）"""
    print("\n" + "=" * 60)
    print("测试4: 集成测试")
    print("=" * 60)

    try:
        analyzer = LLMAgentAnalyzer()

        # 模拟 diagnose 中的知识加载逻辑
        user_query = "Pod间网络不通，ping超时"
        t0_summary = "**总体状态**: 1/2 个组件不健康"

        # 1. 获取架构知识
        core_knowledge = analyzer.knowledge.get_architecture()[:3000]
        print(f"\n✅ 架构知识: {len(core_knowledge)} 字符")

        # 2. 匹配工作流
        workflow_docs = analyzer._match_knowledge_docs(user_query)
        print(f"✅ 匹配工作流: {len(workflow_docs)} 个文档")

        # 3. 读取工作流内容
        workflow_contents = []
        for doc_path in workflow_docs:
            from pathlib import Path
            content = Path(doc_path).read_text(encoding='utf-8')
            # 移除 frontmatter
            lines = content.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if i == 0 and line.strip() == '---':
                    continue
                if line.strip() == '---' and i > 0:
                    start_idx = i + 1
                    break
            workflow_contents.append('\n'.join(lines[start_idx:]))

        workflow_knowledge = "\n\n## 相关诊断工作流\n\n" + "\n\n".join(workflow_contents)
        print(f"✅ 工作流知识: {len(workflow_knowledge)} 字符")

        # 4. 组合知识
        combined_knowledge = f"{core_knowledge}{workflow_knowledge}"
        print(f"✅ 组合知识: {len(combined_knowledge)} 字符")

        # 验证
        assert "ovn-trace" in combined_knowledge, "❌ 应该包含 ovn-trace"
        assert "tcpdump" in combined_knowledge, "❌ 应该包含 tcpdump"
        assert "Kube-OVN" in combined_knowledge, "❌ 应该包含架构知识"

        print(f"\n✅ 集成测试通过")

        return True
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "🚀" * 30)
    print("关键词路由功能测试套件")
    print("🚀" * 30 + "\n")

    tests = [
        ("关键词提取测试", test_keyword_extraction),
        ("关键词匹配测试", test_keyword_matching),
        ("工作流加载测试", test_workflow_loading),
        ("集成测试", test_integration),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
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
        print("\n🎉 所有测试通过！关键词路由功能已正确实现。")
        return 0
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败，请检查实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
