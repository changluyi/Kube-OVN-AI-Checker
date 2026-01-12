"""
原子知识检索工具 - Agent-Native 架构

提供细粒度的知识检索工具，让 Agent 自主决定何时、如何检索知识。

原子工具：
- list_documents(): 列出文档（轻量级）
- read_document(): 读取单个文档
- search_documents(): 搜索相关文档
- list_categories(): 列出所有分类
"""

from typing import List, Dict, Optional
from langchain.tools import tool


# 全局检索器实例（懒加载）
_retriever = None


def _get_retriever():
    """获取检索器实例"""
    global _retriever
    if _retriever is None:
        from kube_ovn_checker.knowledge.retriever import MetadataRetriever
        _retriever = MetadataRetriever()
    return _retriever


@tool
def list_documents(
    category: Optional[str] = None,
    keywords: Optional[List[str]] = None
) -> List[Dict]:
    """列出知识库中的文档

    Args:
        category: 可选的分类过滤（如 "pod_to_pod", "pod_to_service"）
        keywords: 可选的关键词过滤

    Returns:
        文档列表，每个文档包含 path, title, category, priority, estimated_tokens
        不包含 content（减少 token 消耗）

    Examples:
        >>> list_documents()
        >>> list_documents(category="pod_to_pod")
        >>> list_documents(keywords=["跨节点", "overlay"])
    """
    retriever = _get_retriever()
    docs = retriever._documents

    # 过滤
    if category:
        docs = [d for d in docs if d.category == category]
    if keywords:
        docs = [
            d for d in docs
            if any(kw.lower() in str(t).lower() for kw in keywords for t in d.triggers)
        ]

    # 返回轻量级信息（不包含 content）
    return [
        {
            "path": d.path,
            "title": d.title,
            "category": d.category,
            "priority": d.priority,
            "estimated_tokens": d.estimated_tokens
        }
        for d in docs
    ]


@tool
def read_document(
    path: str,
    max_tokens: Optional[int] = None
) -> str:
    """读取单个文档内容

    Args:
        path: 文档路径（如 "principles/dataplane/pod-communication/cross-node-overlay.md"）
        max_tokens: 可选的 Token 限制（如果文档过长，会截断）

    Returns:
        文档内容（Markdown 格式）

    Examples:
        >>> read_document("principles/dataplane/pod-communication/cross-node-overlay.md")
        >>> read_document("architecture.md", max_tokens=2000)
    """
    retriever = _get_retriever()
    doc = None

    for d in retriever._documents:
        if d.path == path:
            doc = d
            break

    if not doc:
        raise ValueError(f"文档不存在: {path}")

    content = doc.content

    # Token 限制
    if max_tokens and doc.estimated_tokens > max_tokens:
        ratio = max_tokens / doc.estimated_tokens
        content = doc.content[:int(len(doc.content) * ratio)]
        return content + "\n\n...(内容已截断)"

    return content


@tool
def search_documents(
    query: str,
    max_results: int = 5
) -> List[Dict]:
    """在知识库中搜索文档（基于关键词）

    Args:
        query: 搜索查询（如 "跨节点通信 隧道"）
        max_results: 最大返回结果数

    Returns:
        相关文档列表，包含 path, title, relevance

    Examples:
        >>> search_documents("跨节点 overlay")
        >>> search_documents("MTU 分片", max_results=3)
    """
    retriever = _get_retriever()

    # 简单的关键词匹配
    query_lower = query.lower()
    matched_docs = []

    for doc in retriever._documents:
        # 搜索标题、触发词、内容
        if (
            query_lower in doc.title.lower() or
            any(query_lower in str(t).lower() for t in doc.triggers) or
            query_lower in doc.content.lower()
        ):
            matched_docs.append(doc)
            if len(matched_docs) >= max_results:
                break

    return [
        {
            "path": d.path,
            "title": d.title,
            "relevance": 0.8  # 简化的相关性评分
        }
        for d in matched_docs
    ]


@tool
def list_categories() -> List[str]:
    """列出所有可用的知识分类

    Returns:
        分类列表（如 ["pod_to_pod", "pod_to_service", "pod_to_external"]）

    Examples:
        >>> list_categories()
        ["general", "pod_to_pod", "pod_to_pod_same_node", "pod_to_pod_cross_node", "pod_to_service", "pod_to_external"]
    """
    retriever = _get_retriever()
    categories = set(d.category for d in retriever._documents)
    return sorted(list(categories))


# 导出所有工具
ALL_TOOLS = [
    list_documents,
    read_document,
    search_documents,
    list_categories,
]


if __name__ == "__main__":
    import doctest
    doctest.testmod()
