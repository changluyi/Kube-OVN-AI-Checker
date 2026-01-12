#!/usr/bin/env python3
"""
快速测试 LLM 分类器（使用真实 Transformer 置信度）

运行前请设置环境变量：
export OPENAI_API_KEY=your-key
export LLM_API_BASE=https://api.openai.com/v1  # 可选
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
import math

def test_llm_classification():
    """测试纯 LLM 分类（无规则匹配）"""

    # 初始化客户端
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ 请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量")
        return

    client = OpenAI(api_key=api_key, base_url=os.getenv("LLM_API_BASE"))

    # 定义类别
    categories = [
        "general",
        "pod_to_pod",
        "pod_to_pod_cross_node",
        "pod_to_service",
        "pod_to_external"
    ]

    # 系统提示
    system_prompt = f"""你是 Kube-OVN 网络诊断专家。根据用户查询分类到以下场景之一：

{', '.join(categories)}

分类规则：
1. **general** - 问候语、帮助请求、非诊断查询
2. **pod_to_pod** - 同一节点内的 Pod 通信问题
3. **pod_to_pod_cross_node** - 不同节点的 Pod 通信问题
4. **pod_to_service** - Kubernetes Service 访问问题
5. **pod_to_external** - Pod 访问外部网络的问题

只返回类别名称，不要解释。"""

    # 测试查询
    test_queries = [
        "node1 的 pod 无法访问 node2 的 pod",
        "nginx pod 无法连接到 app pod",
        "外部网络不通",
        "无法访问 service nginx-svc",
        "你好，有什么可以帮助的吗？",
        "网络好像有问题，有点慢",
        "kube-ovn-controller Pod 一直重启",
        "不同节点之间的 pod 无法通信"
    ]

    print("🧪 LLM 分类测试（纯 LLM，无规则匹配）")
    print("=" * 70)

    for query in test_queries:
        try:
            # 调用 LLM
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.0,
                logprobs=True,
                top_logprobs=3
            )

            # 提取结果
            category = response.choices[0].message.content.strip()
            logprobs = response.choices[0].logprobs.content

            # 计算真实置信度（Transformer softmax 概率）
            avg_logprob = sum(token.logprob for token in logprobs) / len(logprobs)
            confidence = math.exp(avg_logprob)

            # 显示结果
            print(f"\n📝 查询: {query}")
            print(f"🎯 分类: {category}")
            print(f"📊 置信度: {confidence:.3f} (基于 {len(logprobs)} 个 token)")

            # 显示前 2 个 token 的概率
            print("   Token 概率:")
            for tp in logprobs[:2]:
                print(f"     '{tp.token}': {math.exp(tp.logprob):.3f}")

        except Exception as e:
            print(f"\n❌ 错误: {e}")

    print("\n" + "=" * 70)
    print("✅ 测试完成")

if __name__ == "__main__":
    test_llm_classification()
