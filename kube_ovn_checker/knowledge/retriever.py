"""
知识检索器 - 基于元数据的知识文档检索

核心功能：
- 扫描知识库目录，解析文档 YAML frontmatter
- 基于分类和触发词匹配检索相关文档
- 支持优先级排序和 Token 数量限制
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml


class Document:
    """知识文档

    Attributes:
        path: 文档相对路径
        title: 文档标题
        category: 所属分类
        triggers: 触发关键词列表
        priority: 优先级（数字越小越重要）
        content: 文档内容（去除 frontmatter）
        estimated_tokens: 估算的 Token 数量
    """

    def __init__(
        self,
        path: str,
        title: str,
        category: str,
        triggers: List[str],
        priority: int,
        content: str,
        estimated_tokens: int
    ):
        self.path = path
        self.title = title
        self.category = category
        self.triggers = triggers
        self.priority = priority
        self.content = content
        self.estimated_tokens = estimated_tokens

    def __repr__(self):
        return f"Document(path={self.path}, category={self.category}, priority={self.priority})"


class MetadataRetriever:
    """基于元数据的知识检索器（自动发现版本）

    功能：
    1. 自动扫描知识库目录，解析 YAML frontmatter
    2. 根据分类和触发词检索文档
    3. 按优先级排序，控制 Token 数量

    改进：
    - 移除硬编码 CATEGORY_PATHS
    - 自动发现所有 .md 文档
    """

    def __init__(self, knowledge_dir: Optional[str] = None):
        """初始化检索器

        Args:
            knowledge_dir: 知识库根目录（默认为 kube_ovn_checker/knowledge/）
        """
        if knowledge_dir is None:
            # 默认路径
            current_dir = Path(__file__).parent
            self.knowledge_dir = current_dir
        else:
            self.knowledge_dir = Path(knowledge_dir)

        # 自动发现所有文档（替代硬编码 CATEGORY_PATHS）
        self._documents = self._auto_discover_documents()

        # 文档缓存 {category: [Document]}
        self._cache: Dict[str, List[Document]] = {}

    def _auto_discover_documents(self) -> List[Document]:
        """自动扫描所有 .md 文档

        Returns:
            所有发现的文档列表
        """
        documents = []

        # 递归扫描所有 .md 文件
        for md_file in self.knowledge_dir.rglob("*.md"):
            # 跳过备份文件和隐藏文件
            if "backup" in md_file.name or md_file.name.startswith("."):
                continue

            doc = self._load_document(md_file)
            if doc:
                documents.append(doc)

        print(f"✅ 自动发现 {len(documents)} 个知识文档")
        return documents

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """解析 YAML frontmatter

        Args:
            content: 文档完整内容（包含 frontmatter）

        Returns:
            解析后的元数据字典
        """
        # 提取 frontmatter（在 --- 之间）
        pattern = r'^---\n(.*?)\n---'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            frontmatter = yaml.safe_load(match.group(1))
            return frontmatter or {}
        except yaml.YAMLError:
            return {}

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数量

        粗略估算：中文约 1.5 字 = 1 token，英文约 4 字 = 1 token

        Args:
            text: 文本内容

        Returns:
            估算的 Token 数量
        """
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 统计非中文字符
        other_chars = len(text) - chinese_chars

        # 粗略估算
        tokens = chinese_chars / 1.5 + other_chars / 4
        return int(tokens)

    def _load_document(self, file_path: Path) -> Optional[Document]:
        """加载单个文档

        Args:
            file_path: 文档绝对路径

        Returns:
            Document 对象，如果解析失败则返回 None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析 frontmatter
            frontmatter = self._parse_frontmatter(content)

            # 提取标题（第一个 # 标题）
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else file_path.stem

            # 提取元数据
            # 兼容旧格式：search_keywords -> triggers
            triggers = frontmatter.get('triggers') or frontmatter.get('search_keywords') or []
            category = frontmatter.get('category', 'general')
            priority = frontmatter.get('priority', 999)  # 默认最低优先级

            # 去除 frontmatter，保留正文
            body = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

            # 估算 Token 数量
            tokens = self._estimate_tokens(body)

            # 计算相对路径
            relative_path = str(file_path.relative_to(self.knowledge_dir))

            return Document(
                path=relative_path,
                title=title,
                category=category,
                triggers=triggers,
                priority=priority,
                content=body,
                estimated_tokens=tokens
            )

        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load document {file_path}: {e}")
            return None

    def _scan_directory(self, category: str) -> List[Document]:
        """从自动发现的文档中过滤指定分类的文档

        Args:
            category: 分类名称（如 "pod_to_pod_cross_node"）

        Returns:
            该分类的文档列表
        """
        # 检查缓存
        if category in self._cache:
            return self._cache[category]

        documents = []

        # 从自动发现的文档中过滤
        for doc in self._documents:
            if doc.category == category:
                documents.append(doc)

        # 缓存结果
        self._cache[category] = documents

        return documents

    def retrieve(
        self,
        category: str,
        max_tokens: int = 10000,
        keywords: Optional[List[str]] = None
    ) -> List[Document]:
        """检索知识文档

        Args:
            category: 分类名称
                - "pod_to_pod": 同节点 Pod 通信
                - "pod_to_pod_cross_node": 跨节点 Pod 通信
                - "pod_to_service": Service 访问
                - "pod_to_external": 外部网络访问
            max_tokens: 最大 Token 数量限制
            keywords: 可选的关键词列表，用于进一步过滤文档

        Returns:
            按优先级排序的文档列表（Token 总量受 max_tokens 限制）
        """
        # 扫描文档
        documents = self._scan_directory(category)

        # 按关键词过滤（如果提供）
        if keywords:
            filtered = []
            for doc in documents:
                # 检查 triggers 是否匹配任一关键词
                for keyword in keywords:
                    if keyword.lower() in [t.lower() for t in doc.triggers]:
                        filtered.append(doc)
                        break
            documents = filtered

        # 按优先级排序（数字越小越优先）
        documents = sorted(documents, key=lambda d: d.priority)

        # 限制 Token 数量（贪心算法：优先取高优先级文档）
        result = []
        total_tokens = 0

        for doc in documents:
            if total_tokens + doc.estimated_tokens <= max_tokens:
                result.append(doc)
                total_tokens += doc.estimated_tokens
            else:
                # 尝试截断文档以适应剩余空间
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 500:  # 至少保留 500 tokens
                    # 截断内容
                    ratio = remaining_tokens / doc.estimated_tokens
                    truncated_content = doc.content[:int(len(doc.content) * ratio)]

                    # 创建截断后的文档副本
                    truncated_doc = Document(
                        path=doc.path,
                        title=doc.title,
                        category=doc.category,
                        triggers=doc.triggers,
                        priority=doc.priority,
                        content=truncated_content + "\n\n...(内容已截断)",
                        estimated_tokens=remaining_tokens
                    )
                    result.append(truncated_doc)
                    total_tokens += remaining_tokens
                break

        return result

    def get_architecture_doc(self) -> Optional[Document]:
        """获取架构文档（高优先级基础文档）

        Returns:
            架构文档，如果不存在则返回 None
        """
        arch_path = self.knowledge_dir / "architecture.md"

        if not arch_path.exists():
            return None

        return self._load_document(arch_path)

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 测试代码
if __name__ == "__main__":
    import json

    retriever = MetadataRetriever()

    print("=" * 70)
    print("🧪 知识检索器测试")
    print("=" * 70)

    # 测试1: 获取架构文档
    print("\n📋 测试1: 获取架构文档")
    arch_doc = retriever.get_architecture_doc()
    if arch_doc:
        print(f"  标题: {arch_doc.title}")
        print(f"  路径: {arch_doc.path}")
        print(f"  估算 Tokens: {arch_doc.estimated_tokens}")
    else:
        print("  ⚠️  未找到架构文档")

    # 测试2: 检索同节点 Pod 通信相关文档
    print("\n📋 测试2: 检索同节点 Pod 通信文档 (max_tokens=5000)")
    docs = retriever.retrieve("pod_to_pod", max_tokens=5000)

    print(f"  找到 {len(docs)} 个文档:")
    for doc in docs:
        print(f"    - {doc.title} ({doc.estimated_tokens} tokens, priority={doc.priority})")

    # 测试3: 检索跨节点 Pod 通信相关文档
    print("\n📋 测试3: 检索跨节点 Pod 通信文档 (max_tokens=3000)")
    docs = retriever.retrieve("pod_to_pod_cross_node", max_tokens=3000)

    total_tokens = sum(d.estimated_tokens for d in docs)
    print(f"  找到 {len(docs)} 个文档 (总计 {total_tokens} tokens):")
    for doc in docs:
        print(f"    - {doc.title} ({doc.estimated_tokens} tokens, priority={doc.priority})")

    # 测试4: 带关键词过滤
    print("\n📋 测试4: 带关键词过滤 (keywords=['ping', '连通'])")
    docs = retriever.retrieve(
        "pod_to_pod",
        max_tokens=10000,
        keywords=["ping", "连通"]
    )

    print(f"  找到 {len(docs)} 个文档:")
    for doc in docs:
        print(f"    - {doc.title}")
        print(f"      触发词: {doc.triggers}")

    print("\n" + "=" * 70)
    print("✅ 测试完成")
