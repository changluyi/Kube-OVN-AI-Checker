"""
LLM 多文档匹配检索器 - 使用 LLM 智能匹配相关文档

核心功能：
- 自动发现所有知识文档
- 构建精简索引（≤1.5K tokens）
- 使用 LLM 返回多个相关文档及置信度评分
- 支持缓存（相同查询直接返回）
"""

import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

from langchain_openai import ChatOpenAI


class LLMMultiMatchRetriever:
    """基于 LLM 的多文档匹配检索器

    功能：
    1. 自动扫描所有知识文档
    2. 构建精简索引供 LLM 分析
    3. LLM 返回多个相关文档及置信度
    4. 支持缓存机制
    """

    def __init__(
        self,
        knowledge_dir: str,
        llm: Optional[ChatOpenAI] = None,
        use_cache: bool = True
    ):
        """初始化检索器

        Args:
            knowledge_dir: 知识库根目录
            llm: LLM 实例（如果为 None，则从环境变量创建默认实例）
            use_cache: 是否使用缓存
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.use_cache = use_cache

        # 如果没有传入 LLM，从环境变量创建
        if llm is None:
            import os
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("LLM_API_BASE")
            model = os.getenv("LLM_MODEL", "gpt-4o")

            if not api_key:
                raise ValueError(
                    "未找到 LLM_API_KEY 或 OPENAI_API_KEY 环境变量\n"
                    "请设置: export LLM_API_KEY='your-key'"
                )

            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,  # None 会使用默认 OpenAI 端点
                temperature=0.1,
            )
            print(f"✅ LLM 初始化: model={model}, base_url={base_url or 'default'}")

        self.llm = llm

        # 自动发现所有文档
        from kube_ovn_checker.knowledge.retriever import MetadataRetriever
        base_retriever = MetadataRetriever(knowledge_dir)
        self._documents = base_retriever._documents

        # 构建精简索引（启用 debug）
        import os
        debug_mode = os.getenv('DEBUG_INDEX', 'false').lower() == 'true' or os.getenv('VERBOSE', 'false').lower() == 'true'
        self._doc_index = self._build_compact_index(debug=debug_mode)

        # 内存缓存 {query_hash: [Document]}
        self._cache: Dict[str, List[Dict]] = {}

        print(f"✅ LLM 检索器初始化完成: {len(self._documents)} 个文档")

    def _build_compact_index(self, debug: bool = False) -> str:
        """构建精简的文档索引（用于 LLM 匹配）

        只保留关键信息，减少 token 消耗

        Args:
            debug: 是否打印 debug 信息

        Returns:
            精简索引文本（≤1.5K tokens）
        """
        if debug:
            print("\n" + "=" * 70)
            print("🔍 开始构建文档索引...")
            print("=" * 70)

        lines = ["## 知识库文档索引\n"]

        # 按分类分组
        by_category = {}
        for doc in self._documents:
            cat = doc.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(doc)

        if debug:
            print(f"\n📊 分类统计: {len(by_category)} 个分类")
            for cat, docs in sorted(by_category.items()):
                print(f"  - {cat}: {len(docs)} 个文档")

        # 生成索引
        for category, docs in sorted(by_category.items()):
            lines.append(f"\n### {category.upper()}")

            # 按优先级排序
            sorted_docs = sorted(docs, key=lambda d: d.priority)

            if debug:
                print(f"\n📝 分类 [{category.upper()}] ({len(sorted_docs)} 个文档):")

            for i, doc in enumerate(sorted_docs, 1):
                # 精简格式：只保留路径、标题、触发词
                # 确保 triggers 都是字符串
                # 包含所有 triggers,不限制数量(提高匹配精度)
                triggers_str = ', '.join(str(t) for t in doc.triggers) if doc.triggers else '无'
                lines.append(f"{i}. **{doc.title}**")
                lines.append(f"   - 路径: `{doc.path}`")
                lines.append(f"   - 触发词: {triggers_str}")

                if debug:
                    print(f"  {i}. {doc.title}")
                    print(f"     路径: {doc.path}")
                    print(f"     触发词: {triggers_str}")
                    print(f"     优先级: {doc.priority}, Tokens: {doc.estimated_tokens}")

        index = "\n".join(lines)

        # 验证大小
        estimated_tokens = len(index) // 4  # 粗略估算
        char_count = len(index)

        print(f"\n✅ 索引构建完成:")
        print(f"   - 字符数: {char_count}")
        print(f"   - 估算 tokens: ~{estimated_tokens}")
        print(f"   - 目标: <1500 tokens {'✅ 达标' if estimated_tokens < 1500 else '❌ 超标'}")

        if debug:
            print("\n" + "=" * 70)
            print("📄 完整索引内容:")
            print("=" * 70)
            print(index)
            print("=" * 70)

        return index

    def _llm_match_documents(self, query: str) -> List[Dict[str, Any]]:
        """使用 LLM 匹配文档

        Args:
            query: 用户查询

        Returns:
            匹配结果列表:
            [
                {"path": "pod-communication/cross-node-overlay.md",
                 "confidence": 0.95,
                 "reason": "明确提到跨节点 overlay"},
                {"path": "pod-communication/mtu-configuration.md",
                 "confidence": 0.70,
                 "reason": "提到 MTU 分片问题"}
            ]
        """
        prompt = f"""你是 Kube-OVN 知识库匹配专家。

## 用户查询

{query}

## 知识库文档索引

{self._doc_index}

## 任务

分析用户查询，返回所有相关的文档路径。

## 输出格式

严格输出 JSON 数组:

```json
[
  {{"path": "pod-communication/cross-node-overlay.md", "confidence": 0.95, "reason": "明确提到跨节点 overlay"}},
  {{"path": "pod-communication/mtu-configuration.md", "confidence": 0.70, "reason": "提到 MTU 分片问题"}}
]
```

## 置信度标准

- **0.9-1.0**: 非常确定（关键词明确匹配）
- **0.7-0.9**: 比较确定（场景相关）
- **0.5-0.7**: 可能相关（有参考价值）
- **<0.5**: 不相关（不要返回）

## 重要提示

- path 必须完全匹配索引中的路径
- confidence 必须在 0-1 之间
- reason 用中文简述匹配理由
"""

        try:
            # 调用 LLM
            response = self.llm.invoke(prompt)
            content = response.content

            # 提取 JSON
            json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_str = content.strip()

            matches = json.loads(json_str)

            # 验证路径
            valid_matches = []
            for match in matches:
                if self._find_doc_by_path(match["path"]):
                    valid_matches.append(match)
                else:
                    print(f"⚠️  LLM 返回的路径不存在: {match['path']}")

            return valid_matches

        except Exception as e:
            print(f"❌ LLM 匹配失败: {e}")
            return []

    def _find_doc_by_path(self, path: str) -> Optional[Any]:
        """根据路径查找文档

        Args:
            path: 文档路径

        Returns:
            Document 对象，如果不存在则返回 None
        """
        for doc in self._documents:
            if doc.path == path:
                return doc
        return None

    def _generate_cache_key(self, query: str) -> str:
        """生成缓存键

        Args:
            query: 用户查询

        Returns:
            MD5 哈希值
        """
        return hashlib.md5(query.encode()).hexdigest()

    def retrieve(
        self,
        query: str,
        max_tokens: int = 10000
    ) -> List[Any]:
        """智能检索文档

        Args:
            query: 用户查询（自然语言）
            max_tokens: 最大 Token 数量限制

        Returns:
            按置信度排序的文档列表
        """
        # 1. 检查缓存
        if self.use_cache:
            cache_key = self._generate_cache_key(query)
            if cache_key in self._cache:
                print(f"✅ 缓存命中: {query}")
                cached_paths = self._cache[cache_key]
                return [self._find_doc_by_path(p["path"]) for p in cached_paths if self._find_doc_by_path(p["path"])]

        # 2. LLM 匹配多文档
        print(f"🔍 LLM 匹配: {query}")
        matches = self._llm_match_documents(query)

        if not matches:
            # 不降级：抛出异常，要求 LLM 必须工作
            raise RuntimeError(
                f"LLM 匹配失败，无法找到相关文档。查询: {query}\n"
                f"请检查: 1) OPENAI_API_KEY 是否配置 2) 网络是否能访问 OpenAI API"
            )

        # 3. 构建结果（按 confidence 排序）
        matched_docs = []
        for match in matches:
            doc = self._find_doc_by_path(match["path"])
            if doc:
                matched_docs.append((doc, match["confidence"], match["reason"]))
                print(f"  ✅ {doc.title} (置信度: {match['confidence']:.2f}, 理由: {match['reason']})")

        matched_docs.sort(key=lambda x: x[1], reverse=True)

        # 4. Token 限制
        result = []
        total_tokens = 0

        for doc, confidence, reason in matched_docs:
            if total_tokens + doc.estimated_tokens <= max_tokens:
                result.append(doc)
                total_tokens += doc.estimated_tokens
            else:
                # 尝试截断文档以适应剩余空间
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 500:  # 至少保留 500 tokens
                    print(f"  ⚠️  截断文档: {doc.title}")
                    # TODO: 实现截断逻辑
                break

        # 5. 缓存结果
        if self.use_cache:
            self._cache[cache_key] = matches

        print(f"✅ 返回 {len(result)} 个文档，总计 ~{total_tokens} tokens")
        return result


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # 测试 LLM 检索器
    retriever = LLMMultiMatchRetriever(
        knowledge_dir="kube_ovn_checker/knowledge"
    )

    print("\n" + "=" * 70)
    print("🧪 LLM 多文档匹配测试")
    print("=" * 70)

    # 测试1: 单场景匹配
    print("\n📋 测试1: 单场景匹配")
    query1 = "跨节点 overlay 通信失败"
    docs1 = retriever.retrieve(query1)
    print(f"查询: {query1}")
    print(f"结果: {len(docs1)} 个文档")

    # 测试2: 多场景匹配
    print("\n📋 测试2: 多场景匹配")
    query2 = "跨节点 overlay 通信失败，还有 MTU 分片问题"
    docs2 = retriever.retrieve(query2)
    print(f"查询: {query2}")
    print(f"结果: {len(docs2)} 个文档")

    # 测试3: 缓存测试
    print("\n📋 测试3: 缓存测试")
    docs3 = retriever.retrieve(query1)  # 应该命中缓存
    print(f"查询: {query1} (缓存)")
    print(f"结果: {len(docs3)} 个文档")
