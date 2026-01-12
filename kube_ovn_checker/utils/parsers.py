"""
数据解析和格式化工具

提供通用的数据解析、格式化和转换功能。
"""

import json
import re
from typing import Any, Dict, Optional, List

from langchain_core.messages import AIMessage


def parse_diagnosis_from_message(ai_message: AIMessage) -> Dict[str, Any]:
    """从 AIMessage 中提取诊断结果

    Args:
        ai_message: LLM 返回的最终 AI 消息 (无 tool_calls)

    Returns:
        解析后的诊断字典
    """
    content = ai_message.content

    # 尝试解析 JSON (兼容旧格式)
    try:
        # 查找 JSON 代码块
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
            return json.loads(json_str)
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
            return json.loads(json_str)
        else:
            # 尝试直接解析
            return json.loads(content)
    except:
        # 如果不是 JSON，解析纯文本格式（新格式）
        return parse_text_diagnosis(content)


def parse_text_diagnosis(content: str) -> Dict[str, Any]:
    """解析纯文本格式的诊断结果

    支持格式：
    **问题:** xxx
    **根本原因:** xxx
    **严重度:** xxx
    **证据:**
    - xxx
    - xxx
    **解决方案:** xxx
    **相关组件:** xxx
    **验证方法:** xxx

    Args:
        content: LLM 返回的纯文本诊断内容

    Returns:
        结构化的诊断字典
    """
    diagnosis = {
        "problem": "",
        "root_cause": "",
        "severity": "medium",
        "evidence": [],
        "solution": "",
        "related_components": [],
        "verification": "",
        "raw_content": content
    }

    # 提取各个字段 - 使用更灵活的正则表达式
    # 模型可能输出 **字段:** 或 *字段:* 或 *字段：:（中文冒号）
    patterns = {
        "problem": [
            r"\*{0,2}问题\*{0,2}[：:]\s*(.+)",  # *问题*: 或 **问题**: 后跟内容
        ],
        "root_cause": [
            r"\*{0,2}根本原因\*{0,2}[：:]\s*(.+)",
        ],
        "severity": [
            r"\*{0,2}严重度\*{0,2}[：:]\s*(.+)",
        ],
        "solution": [
            r"\*{0,2}解决方案\*{0,2}[：:]\s*(.+)",
        ],
        "related_components": [
            r"\*{0,2}相关组件\*{0,2}[：:]\s*(.+)",
        ],
        "verification": [
            r"\*{0,2}验证方法\*{0,2}[：:]\s*(.+)",
        ],
    }

    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                value = match.group(1).strip()
                # 去除可能残留的 ** 前缀
                value = re.sub(r"^\*+\s*", "", value)
                diagnosis[field] = value
                break

    # 提取证据列表 - 支持多种格式
    evidence_patterns = [
        r"\*\*证据\*\*:\s*\n((?:-\s*.+\n?)*)(?:\n\n|\n\*|\Z)",  # **证据:** 后跟列表
        r"\*\*证据\*\*：\s*\n((?:-\s*.+\n?)*)(?:\n\n|\n\*|\Z)",  # **证据**： 后跟列表
    ]
    for pattern in evidence_patterns:
        evidence_match = re.search(pattern, content, re.MULTILINE)
        if evidence_match:
            evidence_text = evidence_match.group(1)
            # 提取每一行证据
            evidence_list = [
                line.strip().lstrip("-").strip()
                for line in evidence_text.split("\n")
                if line.strip() and line.strip().startswith("-")
            ]
            if evidence_list:
                diagnosis["evidence"] = evidence_list
            break

    # 如果解析失败，至少保留原始内容
    if not diagnosis.get("problem"):
        diagnosis["analysis"] = content

    return diagnosis


def format_tool_args(tool_input: Any) -> str:
    """格式化工具参数，兼容多种事件结构

    Args:
        tool_input: 工具输入参数（可能是 dict、list、str 等多种格式）

    Returns:
        格式化后的参数字符串
    """
    args_raw = None
    if isinstance(tool_input, list) and tool_input:
        tool_input = tool_input[0]
    if isinstance(tool_input, dict):
        args_raw = (
            tool_input.get("arguments")
            or tool_input.get("args")
            or tool_input.get("input")
            or tool_input.get("kwargs")
        )
        if args_raw is None:
            # 某些事件直接把参数放在 input 顶层
            args_raw = {
                k: v for k, v in tool_input.items()
                if k not in {"name", "type"}
            }
    elif isinstance(tool_input, str):
        args_raw = tool_input

    # 尝试将字符串解析为 JSON
    if isinstance(args_raw, str):
        try:
            args_raw = json.loads(args_raw)
        except Exception:
            return args_raw

    if isinstance(args_raw, dict):
        parts = []
        for k, v in args_raw.items():
            parts.append(f"{k}={v}")
        return ", ".join(parts)
    return ""


def extract_output_error(output: Any) -> str:
    """从工具输出中提取 error 字段，便于诊断

    Args:
        output: 工具输出（可能是 ToolMessage、dict、str 等）

    Returns:
        提取的错误信息字符串
    """
    if output is None:
        return ""

    # 优先处理 ToolMessage 或类似对象
    if hasattr(output, "content"):
        try:
            output = output.content
        except Exception:
            output = str(output)

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except Exception:
            return ""

    if isinstance(output, dict):
        error = output.get("error")
        if error:
            return str(error)
    return ""


def extract_ai_message(output: Any) -> Optional[AIMessage]:
    """从 ChatResult/AIMessage 中提取 AIMessage，兼容不同事件结构

    Args:
        output: LLM 输出（可能是 AIMessage、dict、ChatResult 等）

    Returns:
        提取到的 AIMessage，如果无法提取则返回 None
    """
    if output is None:
        return None

    if isinstance(output, AIMessage):
        return output

    # 处理字典类型的 output (例如 LLMResult)
    if isinstance(output, dict):
        # 检查是否有直接的消息
        if "messages" in output:
            messages = output["messages"]
            if messages and isinstance(messages, list):
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    return last_msg

        # 检查 generations 字段
        generations = output.get("generations")
        if generations and isinstance(generations, list):
            for gen_list in generations:
                if not gen_list:
                    continue
                gen = gen_list[0]
                if isinstance(gen, dict):
                    # 字典形式的 generation
                    msg = gen.get("message")
                    if isinstance(msg, AIMessage):
                        return msg
                else:
                    # 对象形式的 generation
                    msg = getattr(gen, "message", None)
                    if isinstance(msg, AIMessage):
                        return msg

    # ChatResult: output.generations -> List[List[ChatGeneration]]
    if hasattr(output, "generations"):
        try:
            generations = output.generations
        except Exception:
            generations = None
        if generations:
            for gen_list in generations:
                if not gen_list:
                    continue
                gen = gen_list[0]
                msg = getattr(gen, "message", None)
                if isinstance(msg, AIMessage):
                    return msg

    return None


def make_json_safe(obj: Any, max_len: int = 4000) -> Any:
    """递归转换为可 JSON 序列化的结构

    Args:
        obj: 任意 Python 对象
        max_len: 字符串最大长度，超过则截断

    Returns:
        可 JSON 序列化的对象
    """
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        return obj if len(obj) <= max_len else obj[:max_len] + "..."

    if hasattr(obj, "dict"):
        try:
            obj = obj.dict()
        except Exception:
            obj = str(obj)

    if isinstance(obj, dict):
        return {k: make_json_safe(v, max_len) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [make_json_safe(v, max_len) for v in obj]

    text = str(obj)
    return text if len(text) <= max_len else text[:max_len] + "..."


def create_fallback_diagnosis(collected: Dict[str, Any]) -> Dict[str, Any]:
    """在未达成显式诊断时，基于已收集数据生成兜底诊断

    Args:
        collected: 收集到的工具输出数据

    Returns:
        兜底诊断字典
    """
    diagnosis = {
        "problem": "未能在限定轮数内完成诊断，提供兜底结论",
        "root_cause": "",
        "severity": "medium",
        "evidence": [],
        "solution": "请根据兜底结论和证据继续人工分析",
        "related_components": [],
        "verification": "检查下方证据或重新运行诊断"
    }

    tools = collected.get("tools") if isinstance(collected, dict) else []
    if tools:
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            out = item.get("output")
            if isinstance(out, dict):
                if out.get("error"):
                    diagnosis["evidence"].append(f"{name}: error={out.get('error')}")
                if out.get("success") is False and out.get("error"):
                    diagnosis["root_cause"] = "部分诊断工具执行失败，需检查集群访问或日志路径"
                    diagnosis["severity"] = "high"
            elif isinstance(out, str) and out:
                if "error" in out.lower():
                    diagnosis["evidence"].append(f"{name}: {out}")
        if not diagnosis["root_cause"] and diagnosis["evidence"]:
            diagnosis["root_cause"] = "已收集工具输出，但模型未给出结论；请根据证据人工研判"
    else:
        diagnosis["root_cause"] = "未收集到有效工具输出"
        diagnosis["severity"] = "low"

    return diagnosis
