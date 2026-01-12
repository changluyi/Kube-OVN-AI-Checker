"""
Kube-OVN 知识库模块

提供：
- 规则系统（兜底机制）
- 知识检索器（基于元数据的文档检索）
- 知识注入器（T0 轻量级知识注入）
"""

from .rules import get_all_rules, match_rule, get_rule_by_name
from .retriever import MetadataRetriever, Document
from .injector import KnowledgeInjector

__all__ = [
    # 规则系统（兜底机制）
    "get_all_rules",
    "match_rule",
    "get_rule_by_name",

    # 知识检索
    "MetadataRetriever",
    "Document",

    # 知识注入
    "KnowledgeInjector",
]
