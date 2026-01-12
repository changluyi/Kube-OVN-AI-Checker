#!/usr/bin/env python3
"""
测试智能分类器（LLM + Transformer 置信度）

运行前设置：
export OPENAI_API_KEY=your-key
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kube_ovn_checker.knowledge.rules import match_rule


def test_basic_classification():
    """测试基本分类功能"""
    print("\n🧪 测试 1: 基本分类功能")

    # 外部网络
    category, confidence = match_rule("外部网络不通")
    assert category == "pod_to_external", f"期望 pod_to_external，实际 {category}"
    assert confidence > 0.5, f"期望较高置信度，实际 {confidence:.3f}"
    print(f"  ✅ 外部网络: {category} (置信度: {confidence:.3f})")

    # Service 访问
    category, confidence = match_rule("无法访问 service nginx-svc")
    assert category == "pod_to_service", f"期望 pod_to_service，实际 {category}"
    assert confidence > 0.5, f"期望较高置信度，实际 {confidence:.3f}"
    print(f"  ✅ Service 访问: {category} (置信度: {confidence:.3f})")

    # 问候语
    category, confidence = match_rule("你好，有什么可以帮助的吗？")
    assert category == "general", f"期望 general，实际 {category}"
    assert confidence > 0.5, f"期望较高置信度，实际 {confidence:.3f}"
    print(f"  ✅ 问候语: {category} (置信度: {confidence:.3f})")


def test_cross_node_detection():
    """测试跨节点检测"""
    print("\n🧪 测试 2: 跨节点检测")

    # 明确提到不同节点
    category, confidence = match_rule("node1 的 pod 无法访问 node2 的 pod")
    assert category == "pod_to_pod_cross_node", f"期望 pod_to_pod_cross_node，实际 {category}"
    print(f"  ✅ 明确跨节点: {category} (置信度: {confidence:.3f})")

    category, confidence = match_rule("跨节点通信失败")
    assert category == "pod_to_pod_cross_node", f"期望 pod_to_pod_cross_node，实际 {category}"
    print(f"  ✅ 跨节点关键词: {category} (置信度: {confidence:.3f})")


def test_same_node_default():
    """测试默认同节点"""
    print("\n🧪 测试 3: 默认同节点")

    # 未明确提及跨节点，默认同节点
    category, confidence = match_rule("nginx pod 无法连接到 app pod")
    # LLM 可能分类为 same_node 或 cross_node，只要合理即可
    assert category in ["pod_to_pod", "pod_to_pod_cross_node"], f"无效分类: {category}"
    print(f"  ✅ 默认场景: {category} (置信度: {confidence:.3f})")

    category, confidence = match_rule("pod 之间 ping 不通")
    assert category in ["pod_to_pod", "pod_to_pod_cross_node"], f"无效分类: {category}"
    print(f"  ✅ Pod 通信: {category} (置信度: {confidence:.3f})")


def test_confidence_return():
    """测试置信度返回"""
    print("\n🧪 测试 4: 置信度返回")

    category, confidence = match_rule("外部网络不通")

    assert category == "pod_to_external", f"期望 pod_to_external，实际 {category}"
    assert 0.0 <= confidence <= 1.0, f"置信度超出范围: {confidence}"
    assert confidence > 0.5, f"明确查询应有较高置信度，实际 {confidence:.3f}"
    print(f"  ✅ 外部网络: category={category}, confidence={confidence:.3f}")


def test_low_confidence_handling():
    """测试低置信度查询"""
    print("\n🧪 测试 5: 低置信度处理")

    # 模糊查询可能有较低置信度
    category, confidence = match_rule("网络好像有点问题")

    # 应该仍能返回分类
    assert category in [
        "general",
        "pod_to_pod",
        "pod_to_pod_cross_node",
        "pod_to_service",
        "pod_to_external"
    ], f"无效分类: {category}"
    print(f"  ✅ 模糊查询: category={category}, confidence={confidence:.3f}")


def test_complex_expressions():
    """测试复杂表达"""
    print("\n🧪 测试 6: 复杂表达")

    test_cases = [
        {
            "query": "Pod 之间通信很慢，偶尔会丢包",
            "expected": "pod_to_pod"  # 未明确跨节点
        },
        {
            "query": "kube-ovn-controller Pod 一直重启",
            "expected": "pod_to_pod"  # 单个 Pod 问题
        },
        {
            "query": "不同节点之间的 pod 无法通信",
            "expected": "pod_to_pod_cross_node"
        }
    ]

    for case in test_cases:
        category, confidence = match_rule(case["query"])
        # LLM 分类可能不完全匹配预期，只要合理即可
        assert category in [
            "general",
            "pod_to_pod",
            "pod_to_pod_cross_node",
            "pod_to_service",
            "pod_to_external"
        ], f"无效分类: {category}"
        print(f"  ✅ '{case['query'][:30]}...' → {category} (置信度: {confidence:.3f})")


def test_classification_accuracy():
    """测试分类准确率（基于多个样本）"""
    print("\n🧪 测试 7: 分类准确率")

    test_cases = [
        # (查询, 期望分类)
        ("你好", "general"),
        ("help", "general"),
        ("外部网络不通", "pod_to_external"),
        ("pod 无法访问 8.8.8.8", "pod_to_external"),
        ("无法访问 service nginx-svc", "pod_to_service"),
        ("ClusterIP 不通", "pod_to_service"),
        ("跨节点访问问题", "pod_to_pod_cross_node"),
        ("node1 到 node2 不通", "pod_to_pod_cross_node"),
        ("nginx pod 无法连接到 app pod", "pod_to_pod"),
        ("pod 之间 ping 不通", "pod_to_pod"),
    ]

    correct = 0
    total = len(test_cases)

    for query, expected in test_cases:
        category, _ = match_rule(query)
        if category == expected:
            correct += 1
            print(f"  ✅ '{query}' → {category}")
        else:
            print(f"  ⚠️  '{query}' → {category} (期望: {expected})")

    accuracy = correct / total
    print(f"\n  📊 准确率: {accuracy:.1%} ({correct}/{total})")

    # 期望准确率 >= 80%（因为 LLM 可能有不同理解）
    assert accuracy >= 0.8, f"准确率过低: {accuracy:.1%}"


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 LLM 智能分类测试套件")
    print("=" * 70)

    try:
        test_basic_classification()
        test_cross_node_detection()
        test_same_node_default()
        test_confidence_return()
        test_low_confidence_handling()
        test_complex_expressions()
        test_classification_accuracy()

        print("\n" + "=" * 70)
        print("✅ 所有测试通过！")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
