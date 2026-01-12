#!/usr/bin/env python3
"""
测试 fallback 逻辑（无 API Key 时）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 临时移除 API Key，测试 fallback
original_key = os.environ.get("OPENAI_API_KEY")
if original_key:
    del os.environ["OPENAI_API_KEY"]

from kube_ovn_checker.knowledge.rules import match_rule

def test_fallback_to_default():
    """测试无 API Key 时的 fallback"""
    print("🧪 测试 fallback 逻辑（无 API Key）\n")

    # 由于没有 API Key，应该 fallback 到默认场景
    test_queries = [
        "外部网络不通",
        "无法访问 service nginx-svc",
        "node1 的 pod 无法访问 node2 的 pod",
        "nginx pod 无法连接到 app pod"
    ]

    print("所有查询都应该返回默认场景（因为没有 API Key）：\n")

    for query in test_queries:
        result = match_rule(query)
        print(f"  '{query}' → {result}")
        assert result == "pod_to_pod", f"期望默认场景，实际 {result}"

    print("\n✅ Fallback 逻辑正常工作")

if __name__ == "__main__":
    try:
        test_fallback_to_default()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 恢复 API Key
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
