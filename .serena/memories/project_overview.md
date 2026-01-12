# 项目概览
- 目标：Kube-OVN 场景下的 LangGraph + LLM 智能诊断助手，定位为 SRE 辅助工具，提供只读信息收集、分析、方案生成与人工审核，不直接操作生产。
- 架构：LangGraph 有向图（采集→分类→分析→根因→修复建议→人工审核→执行→验证→报告），可通过 checkpoint 恢复；Analyzer Registry 支持多种分析器。
- 主要功能：症状语义理解、信息收集、分类选择 analyzer、深度分析、根因提取、修复建议生成、人工审核卡点、可选执行与验证。
- 技术栈：Python（TypedDict、LangGraph、LangChain/OpenAI ChatOpenAI 封装）、PyYAML、Rich、filelock、dotenv。
- 运行入口：`python -m src.cli.main ...`，或脚本 `./scripts/run_mvp_demo.sh`（包装 API Key/模型选择、线程恢复等）。
- 知识与安全：强调 YAML 规则作为结构化知识，AI 只读采集，生产环境必须人工确认；README 提供核心理念和安全准则。