# 代码风格与约定
- 语言：Python 3，偏类型化（TypedDict、Annotated reducer）；注释与 README 使用中文。
- 模块结构：`src/cli` CLI 入口；`src/core` 包含状态、工作流、checkpointer、registry、基类；`src/analyzers/builtin` 提供 General/Tunnel/IPAllocation 等 analyzer；`src/nodes` 定义 LangGraph 节点；`src/llm` 为 LLM 客户端封装。
- 设计原则：简单函数+类，Analyzer 需实现 `get_metadata()` 与 `analyze()`，依赖校验通过 BaseAnalyzer；LangGraph 节点返回 dict 增量状态。
- 配置：LLM provider 支持 openai/glm，可通过环境变量 `LLM_API_KEY/LLM_MODEL/LLM_API_BASE` 或 CLI 参数覆盖。
- 安全：生产只读、人工审核卡点，命令执行需人工确认（见 README 安全原则）。