"""
知识注入器 - 将检索到的知识文档注入到 LLM 上下文

核心功能：
- T0 轻量级注入：架构文档 + 场景相关文档（约 7-10K tokens）
- Token 管理：优先级截断策略
- 格式化：生成清晰的 Agent 系统提示
"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage

from .retriever import MetadataRetriever, Document


class KnowledgeInjector:
    """知识注入器 - 负责将知识注入到 Agent 上下文

    注入策略：
    1. T0 (初始注入)：架构文档 + 场景相关文档
    2. Token 管理：优先级截断（架构 > 场景 > 原则）
    3. 兜底机制：知识注入失败时回退到静态规则
    """

    # Token 预算
    ARCHITECTURE_BUDGET = 2000      # 架构文档预算（2K tokens）
    SCENARIO_BUDGET = 7000          # 场景文档预算（7K tokens）
    MAX_TOTAL_TOKENS = 10000        # 总计预算（10K tokens）

    def __init__(self, retriever: Optional[MetadataRetriever] = None):
        """初始化注入器

        Args:
            retriever: 知识检索器（如果为 None，则创建默认实例）
        """
        self.retriever = retriever or MetadataRetriever()

    def _format_document(self, doc: Document) -> str:
        """格式化单个文档为 Agent 可读的文本

        Args:
            doc: 文档对象

        Returns:
            格式化后的文本
        """
        return f"""
## {doc.title}

{doc.content}
"""

    def _build_knowledge_section(
        self,
        arch_doc: Optional[Document],
        scenario_docs: List[Document]
    ) -> str:
        """构建知识注入文本

        Args:
            arch_doc: 架构文档（可选）
            scenario_docs: 场景相关文档列表

        Returns:
            格式化后的知识文本
        """
        sections = []

        # 1. 架构文档（高优先级）
        if arch_doc:
            sections.append(f"""# 📐 Kube-OVN 架构知识

{self._format_document(arch_doc)}
""")

        # 2. 场景相关文档
        if scenario_docs:
            sections.append("# 📚 诊断工作流和原则\n")

            for doc in scenario_docs:
                sections.append(self._format_document(doc))

        # 合并所有部分
        knowledge_text = "\n".join(sections)

        return knowledge_text

    def inject_t0(
        self,
        category: str,
        fallback_rule: str = ""
    ) -> tuple[str, bool]:
        """T0 轻量级知识注入（初始注入）

        在 Agent 初始化后立即注入，提供基础知识上下文。

        注入内容：
        1. 架构文档（~2K tokens）- 提供系统架构理解
        2. 场景相关文档（~7K tokens）- 针对具体诊断场景

        Args:
            category: 诊断分类
                - "pod_to_pod": 同节点 Pod 通信
                - "pod_to_pod_cross_node": 跨节点 Pod 通信
                - "pod_to_service": Service 访问
                - "pod_to_external": 外部网络访问
            fallback_rule: 兜底规则（知识注入失败时使用）

        Returns:
            (知识文本, 是否成功注入)
            - 知识文本: 格式化后的知识内容（或兜底规则）
            - 是否成功: True 表示使用了知识库，False 表示使用了兜底规则
        """
        try:
            # 1. 获取架构文档
            arch_doc = self.retriever.get_architecture_doc()

            # 2. 如果存在架构文档，应用 Token 限制
            if arch_doc and arch_doc.estimated_tokens > self.ARCHITECTURE_BUDGET:
                # 截断架构文档以适应预算
                ratio = self.ARCHITECTURE_BUDGET / arch_doc.estimated_tokens
                arch_doc.content = arch_doc.content[:int(len(arch_doc.content) * ratio)] + "\n\n...(内容已截断)"
                arch_doc.estimated_tokens = self.ARCHITECTURE_BUDGET

            # 3. 获取场景相关文档
            scenario_docs = self.retriever.retrieve(
                category=category,
                max_tokens=self.SCENARIO_BUDGET
            )

            # 4. 如果知识库为空，使用兜底规则
            if not arch_doc and not scenario_docs:
                if fallback_rule:
                    return (
                        f"## 网络连通性诊断规则\n{fallback_rule}",
                        False
                    )
                else:
                    return ("## 知识库为空，基于通用知识进行诊断", False)

            # 5. 构建知识文本
            knowledge_text = self._build_knowledge_section(arch_doc, scenario_docs)

            return (knowledge_text, True)

        except Exception as e:
            import warnings
            warnings.warn(f"知识注入失败，使用兜底规则: {e}")

            # 兜底机制：使用静态规则
            return (
                f"## 网络连通性诊断规则\n{fallback_rule}",
                False
            )

    def inject_system_message(
        self,
        category: str,
        fallback_rule: str = ""
    ) -> SystemMessage:
        """生成包含知识的 SystemMessage

        Args:
            category: 诊断分类
            fallback_rule: 兜底规则

        Returns:
            LangChain SystemMessage 对象
        """
        knowledge_text, success = self.inject_t0(category, fallback_rule)

        # 生成系统提示
        system_prompt = f"""你是 Kube-OVN 网络诊断专家。

# 📚 知识库

{knowledge_text}

---

# 🎯 诊断策略

基于上述知识，按照以下原则进行诊断：

1. **渐进式诊断**：从快速检查到深度分析
2. **证据驱动**：每个结论都要有日志、配置等证据支持
3. **工具优先级**：ovn-trace（逻辑） → tcpdump（实际） → OVN DB（配置）
4. **及时停止**：当有足够证据时立即给出结论，避免无限调用工具

## 停止条件 ⚠️

满足以下任一条件时，**立即停止工具调用**并给出诊断：
1. 已找到明确的根本原因和证据
2. 已达到 5 轮工具调用
3. 证据显示问题不存在（系统运行正常）

## 输出格式

**诊断结果:**

**问题:** [清晰的问题描述]

**根本原因:** [根本原因分析]

**证据:**
- [具体证据1: 日志、事件或配置]
- [具体证据2: 日志、事件或配置]

**解决方案:** [具体的、可操作的解决步骤]

**相关组件:** [kube-ovn-controller, ovn-nb, 等]

**验证方法:** [如何验证问题已解决]
"""

        return SystemMessage(content=system_prompt)


# 测试代码
if __name__ == "__main__":
    import json

    injector = KnowledgeInjector()

    print("=" * 70)
    print("🧪 知识注入器测试")
    print("=" * 70)

    # 测试1: T0 注入 - 同节点 Pod 通信
    print("\n📋 测试1: T0 注入 - 同节点 Pod 通信")
    knowledge_text, success = injector.inject_t0("pod_to_pod")

    print(f"  注入成功: {success}")
    print(f"  知识文本长度: {len(knowledge_text)} 字符")

    # 统计文档数量
    doc_count = knowledge_text.count("## ")
    print(f"  包含章节数: {doc_count}")

    # 显示前 500 字符
    print(f"  前 500 字符预览:")
    print("  " + "-" * 66)
    for line in knowledge_text[:500].split("\n")[:10]:
        print(f"  {line}")
    print("  " + "-" * 66)

    # 测试2: T0 注入 - Service 访问
    print("\n📋 测试2: T0 注入 - Service 访问")
    knowledge_text, success = injector.inject_t0("pod_to_service")

    print(f"  注入成功: {success}")
    print(f"  知识文本长度: {len(knowledge_text)} 字符")

    # 测试3: 生成 SystemMessage
    print("\n📋 测试3: 生成 SystemMessage")
    system_msg = injector.inject_system_message(
        "pod_to_pod_cross_node",
        fallback_rule="兜底规则内容..."
    )

    print(f"  SystemMessage 长度: {len(system_msg.content)} 字符")

    # 估算 Token 数量（粗略）
    estimated_tokens = len(system_msg.content) / 3  # 粗略估算：3 字符 ≈ 1 token
    print(f"  估算 Token 数: {int(estimated_tokens)}")

    print("\n" + "=" * 70)
    print("✅ 测试完成")
