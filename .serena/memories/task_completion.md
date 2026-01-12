# 任务完成检查
- 若有代码变更：运行必要的单元/集成测试（项目当前无测试套件，可考虑最少运行关键脚本如 `python -m src.cli.main --help` 验证 CLI 正常）。
- 确认依赖未缺失：`pip install -r requirements.txt` 成功；必要时验证 LLM 配置变量存在。
- 如涉及 LangGraph 流程调整，至少用 `run_mvp_demo.sh` 或最小示例输入跑通一次，确认节点流转与 checkpoint 正常。
- 保留/更新 README 或 docs 如影响用户用法；强调安全原则未被破坏。
- 不要在用户未要求时执行 git 提交/推送。