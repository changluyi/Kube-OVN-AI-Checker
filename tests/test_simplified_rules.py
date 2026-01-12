#!/usr/bin/env python3
"""
测试简化的规则系统

验证规则匹配是否正常工作
"""

import sys
sys.path.insert(0, '/home/yichanglu/developer/kube-ovn-langgraph-checker')

from kube_ovn_checker.knowledge.rules import match_rule, get_all_rules

def test_rule_matching():
    """测试规则匹配逻辑"""

    test_cases = [
        {
            "name": "同节点通信",
            "query": "nginx-pod 无法 ping 通 app-pod",
            "expected": "pod_to_pod"
        },
        {
            "name": "跨节点通信",
            "query": "node1 的 pod 无法访问 node2 的 pod",
            "expected": "pod_to_pod_cross_node"
        },
        {
            "name": "Service 访问",
            "query": "无法访问 service nginx-svc",
            "expected": "pod_to_service"
        },
        {
            "name": "外部网络",
            "query": "pod 无法访问 8.8.8.8",
            "expected": "pod_to_external"
        },
    ]

    print("🧪 测试规则匹配\n")

    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        expected = test_case["expected"]
        name = test_case["name"]

        result = match_rule(query)
        passed = result == expected

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{i}. {status} - {name}")
        print(f"   查询: {query}")
        print(f"   期望: {expected}")
        print(f"   实际: {result}")

        if not passed:
            all_passed = False

        print()

    if all_passed:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败")
        return 1

def test_rules_content():
    """测试规则内容是否完整"""

    print("\n🔍 检查规则内容\n")

    rules = get_all_rules()

    expected_rules = [
        "pod_to_pod",
        "pod_to_pod_cross_node",
        "pod_to_service",
        "pod_to_external"
    ]

    for rule_name in expected_rules:
        if rule_name in rules:
            rule_content = rules[rule_name]
            print(f"✅ {rule_name}: {len(rule_content)} 字符")
        else:
            print(f"❌ {rule_name}: 缺失")
            return 1

    print("\n✅ 所有规则都存在")
    return 0

if __name__ == "__main__":
    ret1 = test_rules_content()
    ret2 = test_rule_matching()

    sys.exit(max(ret1, ret2))
