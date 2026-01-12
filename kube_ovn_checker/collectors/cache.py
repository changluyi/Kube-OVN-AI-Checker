"""
Kubernetes API 响应缓存模块

使用 LRU (Least Recently Used) 策略缓存 API 响应,
减少重复的 kubectl 调用,提升性能。

特性:
- 自动过期 (TTL 30秒)
- LRU 淘汰策略
- 线程安全
- 缓存统计
"""

import hashlib
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict


class K8sCache:
    """Kubernetes API 响应缓存

    使用 LRU 策略缓存 kubectl 命令的响应结果,
    减少重复的 API 调用。

    Example:
        cache = K8sCache(ttl_seconds=30, max_size=100)

        # 生成缓存键
        key = cache.generate_key("get_pod", namespace="default", name="test-pod")

        # 获取缓存
        result = cache.get(key)
        if result is None:
            # 缓存未命中,调用 API
            result = await api_call()
            cache.set(key, result)

        # 获取统计信息
        stats = cache.get_stats()
        print(f"缓存命中率: {stats['hit_rate']:.1%}")
    """

    def __init__(
        self,
        ttl_seconds: int = 30,
        max_size: int = 100
    ):
        """初始化缓存

        Args:
            ttl_seconds: 缓存过期时间 (秒, 默认 30)
            max_size: 最大缓存条目数 (默认 100)
        """
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_size = max_size

        # OrderedDict 实现 LRU
        # key -> (data, timestamp)
        self._cache: OrderedDict[str, Tuple[Any, datetime]] = OrderedDict()

        # 线程锁
        self._lock = threading.RLock()

        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def generate_key(self, method: str, **kwargs) -> str:
        """生成缓存键

        将方法名和参数序列化为 MD5 哈希值

        Args:
            method: 方法名 (如 "get_pod", "get_subnets")
            **kwargs: 方法参数

        Returns:
            MD5 哈希值 (32位十六进制字符串)

        Example:
            key = cache.generate_key(
                "get_pod",
                namespace="default",
                name="test-pod"
            )
            # 返回: "a3f5e8d9c2b1f4e6..."
        """
        # 序列化参数为 JSON
        key_data = {
            "method": method,
            "params": kwargs
        }

        # 排序后转 JSON (确保相同参数生成相同键)
        key_str = json.dumps(key_data, sort_keys=True)

        # 生成 MD5 哈希
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存的数据,如果不存在或已过期则返回 None
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            data, timestamp = self._cache[key]

            # 检查是否过期
            if datetime.now() - timestamp > self.ttl:
                # 过期,删除
                del self._cache[key]
                self._misses += 1
                return None

            # 命中,移到末尾 (LRU)
            self._cache.move_to_end(key)
            self._hits += 1

            return data

    def set(self, key: str, data: Any):
        """设置缓存值

        Args:
            key: 缓存键
            data: 要缓存的数据
        """
        with self._lock:
            # 如果已存在,先删除 (后面会重新插入到末尾)
            if key in self._cache:
                del self._cache[key]

            # 插入新值
            self._cache[key] = (data, datetime.now())

            # 检查是否超过容量
            if len(self._cache) > self.max_size:
                # 删除最旧的 (第一个)
                self._cache.popitem(last=False)
                self._evictions += 1

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            # 重置统计
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            {
                "size": 当前缓存条目数,
                "max_size": 最大容量,
                "hits": 命中次数,
                "misses": 未命中次数,
                "evictions": 淘汰次数,
                "hit_rate": 命中率 (0.0-1.0),
                "ttl_seconds": 过期时间
            }
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl.total_seconds()
            }

    def remove(self, key: str) -> bool:
        """删除指定缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def cleanup_expired(self):
        """清理所有过期的缓存条目"""
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key
                for key, (_, timestamp) in self._cache.items()
                if now - timestamp > self.ttl
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def __len__(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """检查键是否存在且未过期"""
        return self.get(key) is not None

    def __repr__(self) -> str:
        """字符串表示"""
        stats = self.get_stats()
        return (
            f"K8sCache(size={stats['size']}/{stats['max_size']}, "
            f"hit_rate={stats['hit_rate']:.1%}, "
            f"ttl={stats['ttl_seconds']}s)"
        )


# 全局缓存实例
_cache: Optional[K8sCache] = None
_cache_lock = threading.Lock()


def get_cache(ttl_seconds: int = 30, max_size: int = 100) -> K8sCache:
    """获取全局缓存实例

    Args:
        ttl_seconds: 缓存过期时间 (秒)
        max_size: 最大缓存条目数

    Returns:
        K8sCache 实例
    """
    global _cache

    with _cache_lock:
        if _cache is None:
            _cache = K8sCache(
                ttl_seconds=ttl_seconds,
                max_size=max_size
            )

        return _cache


def reset_cache():
    """重置全局缓存"""
    global _cache

    with _cache_lock:
        if _cache is not None:
            _cache.clear()
        _cache = None
