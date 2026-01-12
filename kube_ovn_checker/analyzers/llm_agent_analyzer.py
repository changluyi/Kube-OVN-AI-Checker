"""
LLM Agent 分析器 - 多轮交互模式

设计理念：
- LLM 作为大脑，主动决策需要收集什么资源
- 收集器作为工具，供 LLM 调用
- 支持多轮交互，渐进式推理
- 基于 LangGraph agent 实现
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.errors import GraphRecursionError

from .tools import get_k8s_tools
from ..collectors import K8sResourceCollector
# 规则系统（兜底机制）
from ..knowledge.rules import get_all_rules, match_rule
# 知识注入器（T0 轻量级知识注入）
from ..knowledge.injector import KnowledgeInjector
# 数据解析和格式化工具
from ..utils.parsers import (
    parse_diagnosis_from_message,
    parse_text_diagnosis,
    format_tool_args,
    extract_output_error,
    extract_ai_message,
    make_json_safe,
    create_fallback_diagnosis
)


load_dotenv()


class LLMAgentAnalyzer:
    """LLM Agent 分析器 - 多轮交互模式"""

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_rounds: int = 10
    ):
        """
        初始化 Agent 分析器

        Args:
            model: OpenAI 模型名称
            temperature: 温度参数
            api_key: OpenAI API key
            base_url: API base URL
            max_rounds: 最大交互轮数 (防止无限循环)
        """
        self.model_name = model
        self.temperature = temperature
        self.max_rounds = max_rounds

        # 初始化 LLM
        llm_kwargs = {
            "model": model,
            "temperature": temperature,
        }

        if api_key:
            llm_kwargs["api_key"] = api_key
        else:
            llm_kwargs["api_key"] = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not llm_kwargs["api_key"]:
                raise ValueError(
                    "API_KEY not found in environment variables. "
                    "Please set LLM_API_KEY or OPENAI_API_KEY."
                )

        if not base_url:
            base_url = os.getenv("LLM_API_BASE")

        if base_url:
            llm_kwargs["base_url"] = base_url

        self.llm = ChatOpenAI(**llm_kwargs)

        # 获取工具
        self.tools = get_k8s_tools()

        # 创建 agent (添加 max_iterations 限制防止无限循环)
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._get_system_prompt_static(),
            debug=False  # 关闭调试模式,避免输出大量事件信息
        )

    def _get_system_prompt_static(self) -> str:
        """获取静态系统提示 (用于 agent 初始化)

        这个提示在 agent 创建时设置,作为基础系统消息
        具体的 T0 数据和用户问题会在 diagnose 时动态添加
        """
        return """你是 Kube-OVN 网络诊断专家。

## 诊断策略

### 1. 渐进式诊断流程
```
T0 (10秒) → 快速健康检查,找出不健康的组件
   ↓
(按需)  → 深度分析 (OVN DB、网络抓包、性能指标)
```

### 2. 关键组件说明

**核心组件**:
- **kube-ovn-controller**: 核心控制器,负责网络策略翻译和 IPAM 管理
- **kube-ovn-cni**: CNI 服务器,负责本地网络配置
- **ovn-nb**: OVN 北向数据库,存储逻辑网络配置
- **ovn-sb**: OVN 南向数据库,存储物理网络配置

**诊断优先级**:
1. Controller 日志 - 查看控制平面错误
2. Pod/Node 状态 - 查看资源层面问题
3. Subnet/IP - 查看网络资源分配
4. OVN DB - 查看底层网络配置

### 3. 诊断原则

**渐进式收集**:
- 从 T0(快速)到 T1(详细)到 T2(深度)
- 每一步都要有明确目的
- 避免过度收集

**对症下药**:
- 只收集相关数据
- 如果某个方向正常,立即切换方向
- 不要盲目收集所有信息

**证据驱动**:
- 基于日志、事件、配置分析
- 不猜测,不假设
- 每个结论都要有证据支持

**工具优先级**（网络问题）:
1. ovn-trace（首选）- 逻辑路径分析
2. tcpdump - 实际流量验证（在 ovn-trace 之后）
3. OVN DB - 配置验证
4. 日志 - 控制平面分析

## 工作流程

你的诊断过程应该遵循以下步骤:

1. **分析 T0 结果**:
   - 识别哪些组件不健康
   - 找出异常模式 (如多个 Pod 失败 = 控制器问题)
   - 确定最可能的问题方向

2. **规划数据收集**:
   - 基于 T0 结果形成假设
   - 选择最相关的工具验证假设
   - 考虑收集成本 (时间、数据量)

3. **执行收集**:
   - 一次调用一个工具
   - 说明为什么需要这个数据
   - 记录预期结果

4. **分析结果**:
   - 对比预期和实际
   - 更新或推翻假设
   - 决定下一步

5. **收敛到根因**:
   - 当有足够证据时停止
   - 给出具体的、可操作的解决建议
   - 标注相关组件和严重程度

## 输出格式

### 中间步骤 (推理过程)
```
思考: [基于当前数据的分析]
决策: 需要收集 [具体工具]
预期: [这个数据应该显示什么]
原因: [为什么需要这个数据来验证假设]
```

### 重要：思考可见性
每次决定调用工具前，必须输出一行简短的中文思考，以“思考:”开头，不能为空。

### 停止条件 ⚠️ 重要

当你满足以下任一条件时，**立即停止调用工具**，直接给出最终诊断：

1. **已有足够证据**: 你已经收集到足够的信息来确定根本原因
2. **找到明确根因**: 已经识别出具体的问题和原因
3. **问题不存在**: 证据显示用户报告的问题实际上不存在（例如日志显示一切正常）
4. **已有结论**: 无论是确认问题还是确认没有问题，都应该立即给出结论
5. **达到5轮**: 如果已经进行了5轮工具调用，必须基于现有信息给出结论

**特别注意**: 如果日志和数据表明用户报告的问题不存在（例如 ping 显示正常、Pod 运行正常），
这本身就是一个有价值的诊断结论，应该立即停止并告知用户"系统运行正常，未发现报告的问题"。

### 最终诊断 (直接回复，不再调用工具)

当满足停止条件时，使用以下格式**直接回复**（不要调用任何工具）：

**诊断结果:**

**问题:** [清晰的问题描述]

**根本原因:** [根本原因分析]

**证据:**
- [证据1: 具体的日志、事件或配置]
- [证据2: 具体的日志、事件或配置]

**解决方案:** [具体的、可操作的解决步骤]

**相关组件:** [kube-ovn-controller, ovn-nb, 等]

**验证方法:** [如何验证问题已解决]

## 重要提醒

- 🎯 **目标导向**: 每一步都要明确目的,不要盲目收集
- ⏱️ **时间敏感**: 每次工具调用控制在 5 秒内
- 🧠 **保持理性**: 证据不足时继续收集,不要急于下结论
- 📝 **清晰表达**: 说明推理过程,便于用户理解
- 🛑 **及时停止**: 3-5轮后必须给出结论，避免无限循环

记住:像专家一样思考，基于证据给出结论。当你已经理解问题时，立即停止工具调用并给出诊断。
"""

    async def diagnose(
        self,
        user_query: str,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        多轮诊断流程

        Args:
            user_query: 用户问题
            progress_callback: 进度回调函数 callback(message)

        Returns:
            {
                "status": "completed" | "max_rounds_reached" | "failed",
                "rounds": List[Dict],
                "diagnosis": Dict,
                "collected_data": Dict
            """
        if progress_callback:
            progress_callback(f"📊 构建初始上下文...")

        # Phase 1: 匹配诊断规则（使用 LLM 智能分类 + 置信度）
        try:
            # 根据用户查询匹配诊断规则，获取置信度
            rule_name, confidence = match_rule(user_query)
            rules = get_all_rules()
            rule = rules.get(rule_name, "")

            # 显示分类结果和置信度
            if confidence > 0:
                progress_callback(f"📚 匹配诊断规则: {rule_name} (置信度: {confidence:.1%})")
            else:
                # confidence == 0 表示 LLM 调用失败
                progress_callback(f"⚠️ LLM 分类失败，使用默认规则: {rule_name}")

            # 低置信度警告
            if 0 < confidence < 0.5:
                progress_callback(f"⚠️ 分类置信度较低 ({confidence:.1%})，可能需要更多信息")

            # 🆕 如果是 general 场景，直接返回友好响应，不调用 Agent
            if rule_name == "general":
                if progress_callback:
                    progress_callback(f"💬 通用查询")

                # 返回简单的提示信息
                return {
                    "status": "general",
                    "rounds": 0,
                    "diagnosis": {
                        "raw_content": "请描述您遇到的具体网络问题，例如：\n• Pod 无法访问外部网络\n• 两个 Pod 之间无法通信\n• Service 无法访问\n• IP 地址冲突\n"
                    },
                    "collected_data": {"tools": []},
                    "matched_rule": "general"
                }

        except Exception as e:
            import warnings
            warnings.warn(f"Failed to match diagnostic rule: {e}")
            rule = ""
            if progress_callback:
                progress_callback(f"⚠️ 规则匹配失败，使用基础模式")

        # Phase 2: T0 知识注入（轻量级：架构 + 场景文档）
        try:
            if progress_callback:
                progress_callback(f"📚 注入知识库内容...")

            # 初始化知识注入器
            injector = KnowledgeInjector()

            # 获取兜底规则（用于知识注入失败时）
            rules = get_all_rules()
            fallback_rule = rules.get(rule_name, "")

            # 注入 T0 知识（架构文档 + 场景相关文档）
            # 返回: (knowledge_text, success)
            knowledge_text, injection_success = injector.inject_t0(
                category=rule_name,
                fallback_rule=fallback_rule
            )

            # 显示注入结果
            if injection_success:
                if progress_callback:
                    progress_callback(f"✅ 知识注入成功 (使用知识库)")
            else:
                if progress_callback:
                    progress_callback(f"⚠️ 知识注入失败，使用兜底规则")

            # 生成包含知识的 SystemMessage
            system_message = SystemMessage(content=knowledge_text)

        except Exception as e:
            import warnings
            warnings.warn(f"知识注入异常，使用兜底规则: {e}")

            # 兜底机制：使用静态规则
            rules = get_all_rules()
            fallback_rule = rules.get(rule_name, "")
            system_message = SystemMessage(
                content=f"## 网络连通性诊断规则\n{fallback_rule}"
            )

            if progress_callback:
                progress_callback(f"⚠️ 知识注入异常，使用兜底规则")

        # 初始消息 - 包含系统消息（知识库内容）和用户消息
        initial_messages = [
            system_message,
            HumanMessage(content=f"""## 当前任务

用户问题: {user_query}

请基于上述知识库内容，根据用户问题进行诊断。
""")
        ]

        # 初始状态
        session_state = {
            "messages": initial_messages,
            "collected_data": {"tools": []},
            "round": 0
        }

        rounds = []
        tool_call_count = 0
        # LangGraph recursion_limit 是图节点执行上限，不等同于诊断轮数；
        # 提高默认值以避免正常多工具调用时过早触发 GraphRecursionError
        recursion_limit = max(40, self.max_rounds * 4 + 5)

        if progress_callback:
            progress_callback(f"🔄 开始智能诊断...")

        # 单次调用 - 使用 astream_events 追踪完整诊断流程
        try:
            import time
            start_time = time.time()

            # 用于存储最新一轮的 AI 消息，在工具调用前显示思考
            pending_ai_message = None

            async for event in self.agent.astream_events(
                session_state,
                version="v1",
                config={"recursion_limit": recursion_limit}
            ):
                event_type = event["event"]
                event_data = event.get("data", {})

                # 处理工具调用开始事件
                if event_type == "on_tool_start":
                    # 提取工具信息
                    tool_input = event_data.get("input", {}) if event_data else {}
                    tool_name = event.get("name") or event_data.get("name")
                    if not tool_name and isinstance(tool_input, dict):
                        tool_name = tool_input.get("name")
                    tool_name = tool_name or "unknown"

                    # 🆕 捕获当前轮次的详细信息
                    current_round = {
                        "tool_name": tool_name,
                        "tool_input": make_json_safe(tool_input)
                    }

                    # 先显示待处理的 AI 消息（思考内容）
                    if pending_ai_message:
                        content_raw = pending_ai_message.content or ""
                        if isinstance(content_raw, list):
                            content_raw = " ".join([str(c) for c in content_raw])
                        content_preview = str(content_raw).strip()

                        # 完整的思考内容存储到 rounds
                        current_round["thought"] = str(content_raw).strip()

                        # 清理换行符，使输出更紧凑（仅用于进度显示）
                        if progress_callback:
                            content_display = content_preview.replace('\n', ' ').replace('\r', ' ')
                            while '  ' in content_display:
                                content_display = content_display.replace('  ', ' ')

                            # 限制长度
                            if len(content_display) > 150:
                                content_display = content_display[:150] + "..."

                            if content_display:
                                if not content_display.startswith("思考"):
                                    content_display = f"思考: {content_display}"
                                progress_callback(f"💭 {content_display}")

                        # 清除待处理消息
                        pending_ai_message = None

                    # 🆕 将当前轮次添加到 rounds 列表
                    rounds.append(current_round)

                    # 格式化工具参数
                    tool_args = format_tool_args(tool_input)
                    if not tool_args:
                        tool_args = format_tool_args(event_data)

                    if progress_callback:
                        name_with_args = f"{tool_name} ({tool_args})" if tool_args else tool_name
                        if "logs" in tool_name.lower():
                            progress_callback(f"📋 分析日志: {name_with_args}")
                        else:
                            progress_callback(f"🔧 调用工具: {name_with_args}")

                    tool_call_count += 1

                # 处理工具调用结束事件
                elif event_type == "on_tool_end":
                    tool_name = event.get("name") or event_data.get("name") or "unknown"
                    output = event_data.get("output")

                    # 记录输出
                    session_state["collected_data"]["tools"].append(
                        {"name": tool_name, "output": make_json_safe(output)}
                    )

                    # Phase 2: 简化 - 不需要动态知识注入
                    # 规则已在初始阶段注入，这里保持空操作
                    pass

                    if progress_callback:
                        error_info = extract_output_error(output)
                        if error_info:
                            progress_callback(f"✅ 工具完成: {tool_name} (error={error_info})")
                        else:
                            progress_callback(f"✅ 工具完成: {tool_name} (已获取)")

                # 处理 LLM 模型结束事件 - 获取 AI 响应
                elif event_type == "on_chat_model_end":
                    output = event_data.get("output")

                    # 尝试从事件中提取 AIMessage
                    ai_msg = None

                    # 方法1: 检查事件本身是否有消息
                    if "message" in event and isinstance(event["message"], AIMessage):
                        ai_msg = event["message"]

                    # 方法2: 从 output 中提取
                    if not ai_msg:
                        ai_msg = extract_ai_message(output)

                    # 方法3: 检查 input 中的消息
                    if not ai_msg and isinstance(output, dict):
                        input_data = event_data.get("input", {})
                        if isinstance(input_data, dict) and "messages" in input_data:
                            messages = input_data["messages"]
                            if messages and isinstance(messages, list):
                                # 找最后一个 AIMessage
                                for msg in reversed(messages):
                                    if isinstance(msg, AIMessage):
                                        ai_msg = msg
                                        break

                    if ai_msg:
                        # 检查是否有工具调用
                        tool_calls = getattr(ai_msg, "tool_calls", None)
                        if not tool_calls and hasattr(ai_msg, "additional_kwargs"):
                            tool_calls = ai_msg.additional_kwargs.get("tool_calls")

                        if tool_calls:
                            # 有工具调用 - 保存这个消息，等工具调用开始时显示思考内容
                            pending_ai_message = ai_msg

                            # 同时显示即将调用的工具
                            if progress_callback:
                                call_descriptions = []
                                for tc in tool_calls:
                                    name = tc.get("name", "unknown")
                                    args = tc.get("args") or tc.get("arguments") or {}
                                    arg_items = []
                                    if isinstance(args, dict):
                                        for k, v in args.items():
                                            arg_items.append(f"{k}={v}")
                                    arg_text = ", ".join(arg_items)
                                    call_descriptions.append(
                                        f"{name}({arg_text})" if arg_text else name
                                    )
                                progress_callback(f"➡️  将调用: {', '.join(call_descriptions)}")
                        else:
                            # 无工具调用 - 最终诊断
                            elapsed = time.time() - start_time
                            if progress_callback:
                                progress_callback(f"✅ 诊断完成 (耗时 {elapsed:.1f}秒, 共 {tool_call_count} 轮工具调用)")
                                progress_callback(f"🎯 提取诊断结果...")

                            diagnosis = parse_diagnosis_from_message(ai_msg)

                            return {
                                "status": "completed",
                                "rounds": rounds,
                                "diagnosis": diagnosis,
                                "collected_data": session_state["collected_data"],
                                "matched_rule": rule_name
                            }

            # 如果事件流自然结束但没有得到最终结论
            elapsed = time.time() - start_time
            if progress_callback:
                progress_callback(f"⚠️ 事件流结束 (耗时 {elapsed:.1f}秒, 共 {tool_call_count} 轮)")

            fallback_diag = create_fallback_diagnosis(session_state["collected_data"])

            return {
                "status": "completed",
                "rounds": rounds,
                "diagnosis": fallback_diag,
                "collected_data": session_state["collected_data"],
                "matched_rule": rule_name,
                "fallback": True
            }
        except GraphRecursionError as e:
            if progress_callback:
                progress_callback(f"⚠️ 达到递归上限 {recursion_limit}, 停止诊断: {e}")
            return {
                "status": "max_rounds_reached",
                "error": f"recursion_limit {recursion_limit} reached: {e}",
                "rounds": rounds,
                "collected_data": session_state["collected_data"]
            }
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ 诊断失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "failed",
                "error": str(e),
                "rounds": rounds,
                "collected_data": session_state["collected_data"]
            }

    # 简化版：移除复杂知识注入相关方法
    # - _should_inject_knowledge
    # - _extract_search_keywords
    # - _match_knowledge_docs
    # - _extract_doc_id_from_knowledge
    # 这些方法不再需要，因为规则已在初始阶段注入


    async def diagnose_stream(
        self,
        user_query: str
    ):
        """
        流式诊断 - 生成器模式

        逐步返回诊断过程，适合实时展示

        Yields:
            Dict: 每一步的中间结果
        """
        # Phase 1: 匹配诊断规则（简化版）
        try:
            rule_name, _ = match_rule(user_query)  # 不需要置信度
            rules = get_all_rules()
            rule = rules.get(rule_name, "")
        except Exception:
            rule = ""

        # 初始消息 - 包含系统消息（诊断规则）
        initial_messages = [
            SystemMessage(content=f"## 网络连通性诊断规则\n{rule}"),
            HumanMessage(content=f"""## 当前任务

用户问题: {user_query}

请根据用户问题和诊断规则进行诊断。
""")
        ]

        session_state = {
            "messages": initial_messages,
            "collected_data": {"tools": []},
            "round": 0
        }

        # 使用 astream 逐步获取结果
        async for event in self.agent.astream(session_state):
            yield event

            # 检查是否完成
            if "__end__" in event:
                break
