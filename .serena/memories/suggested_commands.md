# 常用命令
- 安装依赖：`pip install -r requirements.txt`
- 运行 MVP 演示（默认 glm，需 API Key）：`LLM_API_KEY=... ./scripts/run_mvp_demo.sh "Pod cannot start" demo-1 [--resume|--provider openai --model gpt-4o-mini]`
- 直接运行 CLI：`python -m src.cli.main --api-key $LLM_API_KEY --input "症状描述" --thread-id demo-1 [--resume] [--analyzer general|tunnel|ip_allocation] [--provider glm|openai --api-base ... --model ...] [--pretty/--no-pretty]`
- 查看代码结构：`find src -maxdepth 2 -type f`
- 代码搜索：`rg "keyword" src`
- 检查 requirements：`cat requirements.txt`
- 若使用 checkpoint 恢复：添加 `--resume` 并保持相同 `--thread-id`。