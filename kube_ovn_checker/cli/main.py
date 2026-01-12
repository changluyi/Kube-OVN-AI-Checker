#!/usr/bin/env python3
"""
Kube-OVN 智能诊断工具 - 极简版

最简设计:
- 输入: 只有一个问题文本
- 处理: LLM Agent 自主决定使用哪些工具(包括 T0)
- 输出: 诊断结果和解决方案
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

from kube_ovn_checker.analyzers.llm_agent_analyzer import LLMAgentAnalyzer
from rich.console import Console
from rich.panel import Panel


load_dotenv()

console = Console()


async def diagnose(user_query: str, model: str = None):
    """
    执行诊断 - 让 Agent 自主决策

    Args:
        user_query: 用户问题描述
        model: LLM 模型名称
    """

    print_header("🚀 Kube-OVN 智能诊断")

    # 显示用户问题
    console.print(f"[bold]📝 问题:[/bold] {user_query}")
    console.print()

    # 检查 API Key
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]❌ 未找到 API Key[/red]")
        console.print()
        console.print("[yellow]请在 .env 文件中配置:[/yellow]")
        console.print("  OPENAI_API_KEY=sk-your-key")
        console.print("  LLM_MODEL=gpt-4o")
        console.print()
        return 1

    # 获取模型配置
    model_name = model or os.getenv("LLM_MODEL", "gpt-4o")
    api_base = os.getenv("LLM_API_BASE")

    console.print(f"[dim]使用模型: {model_name}[/dim]")
    if api_base:
        console.print(f"[dim]API Base: {api_base}[/dim]")
    console.print()

    # 初始化 Analyzer
    console.print("[bold]🤖 初始化 LLM Agent...[/bold]")
    console.print()

    try:
        analyzer = LLMAgentAnalyzer(
            model=model_name,
            temperature=0.0,
            max_rounds=10  # 最大诊断轮数
        )

        console.print("[green]✅ Agent 已就绪[/green]")
        console.print()

    except Exception as e:
        console.print(f"[red]❌ 初始化失败: {e}[/red]")
        return 1

    # 执行诊断 - Agent 自主决定调用哪些工具
    console.print("[bold]🔍 开始诊断...[/bold]")
    console.print()
    console.print("[dim]Agent 将自主决定使用哪些工具来分析问题...[/dim]")
    console.print()

    # 进度回调函数
    def progress_callback(message: str):
        """实时显示进度"""
        console.print(f"[dim]{message}[/dim]")

    try:
        # 直接调用 diagnose，Agent 会自主决策
        result = await analyzer.diagnose(
            user_query=user_query,
            progress_callback=progress_callback
        )

        status = result.get("status", "unknown")

        # 🆕 如果是 general 查询,简单打印提示即可,不需要诊断框架
        if status == "general":
            diagnosis = result.get("diagnosis", {})
            content = diagnosis.get("raw_content", "")
            console.print()
            console.print(content)
            console.print()
            return 0

        console.print()
        console.print("[green]✅ 诊断完成[/green]")
        console.print()

    except Exception as e:
        console.print(f"[red]❌ 诊断失败: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1

    # 打印诊断结果
    print_diagnosis_result(result)

    # 保存报告
    save_report(user_query, result)

    print_header("✨ 诊断完成")

    return 0


def print_header(title: str):
    """打印标题"""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()


def print_diagnosis_result(result: dict):
    """打印诊断结果"""
    console.print()
    console.print(Panel("[bold cyan]🎯 诊断结果[/bold cyan]", expand=False))
    console.print()

    status = result.get("status", "unknown")

    # 🆕 显示思维链总结
    if status == "completed":
        rounds = result.get("rounds", [])
        if rounds and isinstance(rounds, list) and len(rounds) > 0:
            console.print("[bold]🧠 诊断思维链:[/bold]")
            console.print()

            # 提取每一轮的思考过程
            for i, round_data in enumerate(rounds, 1):
                if isinstance(round_data, dict):
                    # 获取思考内容
                    thought = round_data.get("thought", "")
                    tool_name = round_data.get("tool_name", "")
                    tool_input = round_data.get("tool_input", {})

                    # 显示思考步骤
                    if thought or tool_name:
                        # 步骤编号
                        console.print(f"  [cyan]{i}.[/cyan]", end="")

                        # 显示思考
                        if thought:
                            # 限制长度，避免过长
                            thought_display = thought[:150] + "..." if len(thought) > 150 else thought
                            console.print(f" {thought_display}")

                        # 显示工具调用
                        if tool_name:
                            # 简化工具参数显示
                            if tool_input:
                                input_summary = ", ".join(f"{k}={v}" for k, v in tool_input.items() if k not in ["namespace", "timeout"])
                                if len(input_summary) > 80:
                                    input_summary = input_summary[:80] + "..."
                                console.print(f"     → [dim]调用: {tool_name}({input_summary})[/dim]")
                            else:
                                console.print(f"     → [dim]调用: {tool_name}[/dim]")

                        console.print()

            # 添加分隔线
            console.print("[dim]" + "─" * 70 + "[/dim]")
            console.print()

    if status == "completed":
        diagnosis = result.get("diagnosis", {})
        is_fallback = result.get("fallback", False)

        if is_fallback:
            console.print("[dim]（使用兜底诊断，模型未给出最终结论）[/dim]")
            console.print()

        # 检查是否有有效诊断内容
        has_diagnosis = (
            diagnosis.get("problem") or
            diagnosis.get("root_cause") or
            diagnosis.get("solution") or
            diagnosis.get("analysis") or
            diagnosis.get("raw_content")
        )

        if has_diagnosis:
            # 打印问题
            if diagnosis.get("problem"):
                console.print(f"[bold]📋 问题:[/bold] {diagnosis['problem']}")
                console.print()

            # 打印根因
            if diagnosis.get("root_cause"):
                console.print(f"[bold]🔍 根因:[/bold] {diagnosis['root_cause']}")
                console.print()

            # 打印分析结果（如果没有根因）
            elif diagnosis.get("analysis"):
                console.print(f"[bold]🔍 分析:[/bold] {diagnosis['analysis']}")
                console.print()

            # 打印解决方案
            if diagnosis.get("solution"):
                console.print(f"[bold]💡 解决方案:[/bold] {diagnosis['solution']}")
                console.print()

            # 显示证据
            evidence = diagnosis.get("evidence", [])
            if evidence and isinstance(evidence, list) and evidence[0]:
                console.print(f"[bold]📝 证据:[/bold]")
                for item in evidence:
                    if item:
                        console.print(f"   • {item}")
                console.print()

            # 如果有原始内容但没有结构化字段，显示原始内容
            elif not diagnosis.get("problem") and diagnosis.get("raw_content"):
                console.print(f"[bold]📋 诊断结论:[/bold]")
                console.print(diagnosis['raw_content'])
                console.print()
        else:
            console.print("[yellow]⚠️  未获取到详细诊断内容[/yellow]")
            console.print()

        # 显示诊断统计
        rounds = result.get("rounds", [])
        if rounds:
            if isinstance(rounds, int):
                console.print(f"[dim]📊 诊断轮次: {rounds}[/dim]")
            else:
                console.print(f"[dim]📊 诊断轮次: {len(rounds)}[/dim]")

            # 统计工具调用 - 从 collected_data 中获取
            collected_data = result.get("collected_data", {})
            tools_data = collected_data.get("tools", [])
            if tools_data:
                tools_used = set()
                for item in tools_data:
                    if isinstance(item, dict):
                        name = item.get("name")
                        if name:
                            tools_used.add(name)

                if tools_used:
                    console.print(f"[dim]🔧 调用工具: {', '.join(sorted(tools_used))}[/dim]")

        console.print()

    elif status == "max_rounds_reached":
        console.print("[yellow]⚠️  达到最大诊断轮数[/yellow]")
        error = result.get("error")
        if error:
            console.print(f"[dim]原因: {error}[/dim]")
        console.print()

    else:
        error = result.get("error", "Unknown error")
        console.print(f"[red]❌ 诊断失败: {error}[/red]")
        console.print()


def save_report(user_query: str, result: dict):
    """保存诊断报告"""
    import json
    import time

    console.print("[bold]💾 保存报告...[/bold]")

    report = {
        "query": user_query,
        "diagnosis": result,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = f"diagnosis_report_{timestamp}.json"

    try:
        # 先清理可能存在的代理字符（surrogate pairs）
        cleaned_report = _clean_surrogates(_make_json_safe(report))

        with open(report_file, "w", encoding="utf-8", errors="replace") as f:
            json.dump(cleaned_report, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✅ 已保存: {report_file}[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️  保存报告失败: {e}[/yellow]")
    console.print()


def _clean_surrogates(obj):
    """清理可能存在的代理字符（surrogate pairs）"""
    if isinstance(obj, str):
        # 编码为 UTF-8，忽略无效字符，再解码回来
        try:
            return obj.encode('utf-8', errors='ignore').decode('utf-8')
        except:
            # 如果还是失败，返回空字符串
            return ""

    if isinstance(obj, dict):
        return {k: _clean_surrogates(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_clean_surrogates(v) for v in obj]

    return obj


def _make_json_safe(obj, max_len: int = 4000):
    """将结果递归转换为可 JSON 序列化的结构"""
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        return obj if len(obj) <= max_len else obj[:max_len] + "..."

    if isinstance(obj, dict):
        return {k: _make_json_safe(v, max_len) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v, max_len) for v in obj]

    # LangChain 等对象转字符串
    text = str(obj)
    return text if len(text) <= max_len else text[:max_len] + "..."


async def main_async(query: str = None, model: str = None):
    """异步主函数"""

    # 获取问题
    if not query:
        if not sys.stdin.isatty():
            # 从管道读取
            query = sys.stdin.read().strip()
        else:
            # 交互式输入
            console.print("[bold]请输入您的问题:[/bold]")
            query = input().strip()

    if not query:
        console.print("[yellow]⚠️  请提供问题描述[/yellow]")
        console.print()
        console.print("[dim]示例:[/dim]")
        console.print("  ./kube-ovn-checker \"kube-ovn-controller Pod 一直重启\"")
        console.print("  echo \"网络问题\" | ./kube-ovn-checker")
        console.print()
        return 1

    # 执行诊断
    return await diagnose(query, model)


def main():
    """CLI 主入口"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="kube-ovn-checker",
        description="Kube-OVN 智能诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "kube-ovn-controller Pod 一直重启"
  echo "网络问题" | %(prog)s
  %(prog)s
        """
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="问题描述"
    )

    parser.add_argument(
        "--model",
        help="LLM 模型"
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main_async(args.query, args.model))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  用户中断[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
