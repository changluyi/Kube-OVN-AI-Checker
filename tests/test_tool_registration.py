#!/usr/bin/env python3
"""
验证 collect_node_tcpdump 工具是否正确注册
"""

from kube_ovn_checker.analyzers.tools import get_k8s_tools


def test_tool_registration():
    """测试工具注册"""
    print("=" * 70)
    print("验证 collect_node_tcpdump 工具注册")
    print("=" * 70)
    print()

    # 获取所有工具
    tools = get_k8s_tools()

    # 查找工具
    tcpdump_tools = []
    for tool in tools:
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        if 'tcpdump' in tool_name.lower():
            tcpdump_tools.append(tool_name)

    print("📊 找到的 tcpdump 相关工具:")
    print("-" * 70)
    for i, tool_name in enumerate(tcpdump_tools, 1):
        print(f"  {i}. {tool_name}")

    print()

    # 检查是否有 collect_node_tcpdump
    has_node_tcpdump = any('node_tcpdump' in str(tool).lower() for tool in tools)

    if has_node_tcpdump:
        print("✅ collect_node_tcpdump 已正确注册！")
        print()
        print("💡 工具说明:")
        for tool in tools:
            if 'node_tcpdump' in str(tool).lower():
                print(f"   名称: {tool.name}")
                print(f"   描述: {tool.description[:100]}...")
                print()
                break
        return True
    else:
        print("❌ collect_node_tcpdump 未注册！")
        print()
        print("⚠️  LLM Agent 将无法使用此工具！")
        return False


if __name__ == "__main__":
    success = test_tool_registration()
    exit(0 if success else 1)
