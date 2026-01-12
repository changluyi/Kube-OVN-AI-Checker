from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI


PROVIDER_DEFAULTS = {
    "openai": {
        "env_keys": ["LLM_API_KEY"],
        "model_envs": ["LLM_MODEL"],
        "base_envs": ["LLM_API_BASE"],
        "model": "gpt-4o-mini",
        "base_url": None,
    },
    "glm": {
        "env_keys": ["LLM_API_KEY"],
        "model_envs": ["LLM_MODEL"],
        "base_envs": ["LLM_API_BASE"],
        "model": "glm-4.6",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
}


class LLMClient:
    """简单包装 ChatOpenAI, 支持 openai/glm provider 选择."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "openai",
        api_base: Optional[str] = None,
    ) -> None:
        provider = provider.lower()
        if provider not in PROVIDER_DEFAULTS:
            raise RuntimeError(f"不支持的 provider: {provider}")

        defaults = PROVIDER_DEFAULTS[provider]
        key = api_key
        if not key:
            for env_key in defaults["env_keys"]:
                val = os.getenv(env_key)
                if val:
                    key = val
                    break
        if not key:
            raise RuntimeError(
                f"缺少 API Key, 请设置 {defaults['env_keys']} 或通过 CLI 传入 --api-key"
            )

        model_name = model
        if not model_name:
            for env_key in defaults["model_envs"]:
                val = os.getenv(env_key)
                if val:
                    model_name = val
                    break
        if not model_name:
            model_name = defaults["model"]

        base_url = api_base
        if base_url is None:
            for env_key in defaults["base_envs"]:
                val = os.getenv(env_key)
                if val:
                    base_url = val
                    break
        if base_url is None:
            base_url = defaults["base_url"]

        # ChatOpenAI 支持 base_url 覆盖, 用于兼容接口
        self.llm = ChatOpenAI(
            api_key=key,
            model=model_name,
            temperature=0.2,
            base_url=base_url,
        )

    def invoke_text(self, prompt: str) -> str:
        result = self.llm.invoke(prompt)
        # langchain-openai 返回 BaseMessage
        return getattr(result, "content", str(result))

    def maybe_structured_root_cause(self, prompt: str) -> Optional[Dict[str, Any]]:
        try:
            text = self.invoke_text(prompt + "\n请输出主要根因的简短句子。")
            return {"primary_cause": text, "contributing_factors": []}
        except Exception:
            return None

    def maybe_structured_fixes(self, prompt: str) -> Optional[List[Dict[str, Any]]]:
        try:
            text = self.invoke_text(prompt + "\n给 1-2 条命令形式建议, 简短。")
            return [
                {
                    "command": text,
                    "description": "LLM 建议",
                    "risk_level": "medium",
                    "expected_result": "按建议执行",
                }
            ]
        except Exception:
            return None
