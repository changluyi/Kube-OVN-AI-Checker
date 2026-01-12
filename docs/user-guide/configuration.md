# ⚙️ 配置指南

本指南详细说明所有配置选项，帮助您根据自己的需求定制 Kube-OVN-LangGraph-Checker。

## 📋 配置文件概述

工具使用 `.env` 文件存储配置，该文件位于项目根目录。

### 创建配置文件

```bash
# 从模板复制
cp .env.example .env

# 编辑配置
vim .env  # 或使用其他编辑器
```

### 配置文件加载顺序

工具按以下顺序查找配置（后面的覆盖前面的）:

1. 内置默认值
2. `.env` 文件
3. 环境变量
4. 命令行参数（暂不支持）

## 🔑 核心配置

### OPENAI_API_KEY (必需)

LLM 服务的 API 密钥。

**获取方式**:

| 提供商 | 获取地址 | 价格 |
|-------|---------|------|
| OpenAI | https://platform.openai.com/api-keys | $0.005/1K tokens |
| Azure OpenAI | Azure Portal | 按使用量 |
| DeepSeek | https://platform.deepseek.com/ | ¥1/1M tokens |
| 智谱 AI | https://open.bigmodel.cn/ | ¥0.1/1M tokens |
| Ollama (本地) | 无需 Key | 免费 |

**配置示例**:
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890

# Azure OpenAI
OPENAI_API_KEY=your-azure-openai-key

# DeepSeek
OPENAI_API_KEY=sk-1234567890abcdef

# 智谱 AI
OPENAI_API_KEY=1234567890abcdef.yourkey
```

**验证方法**:
```bash
# 检查环境变量
echo $OPENAI_API_KEY

# 测试 API 连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

### OPENAI_API_BASE (可选)

自定义 API 端点，用于兼容 OpenAI API 的其他服务。

**默认值**: `https://api.openai.com/v1` (留空使用默认)

**支持的提供商**:

| 提供商 | Base URL | 模型示例 |
|-------|---------|---------|
| OpenAI | `https://api.openai.com/v1` | gpt-4o, gpt-4o-mini |
| Azure OpenAI | `https://<resource>.openai.azure.com/` | gpt-4o |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4/` | glm-4-flash |
| Ollama (本地) | `http://localhost:11434/v1` | llama3, qwen2 |

**配置示例**:

```bash
# Azure OpenAI
OPENAI_API_BASE=https://my-resource.openai.azure.com/

# DeepSeek
OPENAI_API_BASE=https://api.deepseek.com/v1

# 智谱 AI
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4/

# 本地 Ollama
OPENAI_API_BASE=http://localhost:11434/v1
```

**注意事项**:
- URL 必须以 `/` 结尾（某些提供商要求）
- 确保网络可以访问该端点
- 本地 Ollama 需要先启动服务: `ollama serve`

---

### LLM_MODEL (可选)

自定义模型名称。

**默认值**: `gpt-4o`

**推荐配置**:

| 场景 | 推荐模型 | 说明 |
|-----|---------|------|
| 生产环境 | `gpt-4o` | 最佳质量，成本较高 |
| 测试环境 | `gpt-4o-mini` | 快速且便宜，质量略低 |
| 成本敏感 | `deepseek-chat` | 性价比高 |
| 国内用户 | `glm-4-flash` | 快速响应 |
| 本地部署 | `llama3:70b` | 零成本，需要 GPU |

**模型能力对比**:

| 模型 | 上下文长度 | 函数调用 | 推理能力 | 成本 |
|-----|----------|---------|---------|------|
| gpt-4o | 128K | ✅ | ⭐⭐⭐⭐⭐ | $$$ |
| gpt-4o-mini | 128K | ✅ | ⭐⭐⭐⭐ | $ |
| deepseek-chat | 32K | ❌ | ⭐⭐⭐ | $ |
| glm-4-flash | 128K | ✅ | ⭐⭐⭐⭐ | $ |
| llama3:70b | 8K | ❌ | ⭐⭐⭐ | 免费 |

**配置示例**:
```bash
# 使用 GPT-4o（默认）
LLM_MODEL=gpt-4o

# 使用 GPT-4o-mini（经济）
LLM_MODEL=gpt-4o-mini

# 使用 DeepSeek
LLM_MODEL=deepseek-chat

# 使用智谱 AI
LLM_MODEL=glm-4-flash

# 使用本地 Llama 3
LLM_MODEL=llama3:70b
```

---

## 🌡️ 性能调优

### TEMPERATURE (可选)

控制 LLM 输出的随机性。

- **范围**: 0.0 - 1.0
- **默认值**: 0.0

**说明**:
- `0.0`: 完全确定性输出（推荐）
- `0.3-0.7`: 适度随机
- `0.8-1.0`: 高度随机，不推荐

**配置示例**:
```bash
# 确定性输出（推荐）
TEMPERATURE=0.0

# 适度随机（探索性诊断）
TEMPERATURE=0.3
```

**建议**: 保持默认值 `0.0` 以获得稳定的结果。

---

### MAX_ROUNDS (可选)

Agent 收集证据和推理的最大轮数。

- **默认值**: 10
- **推荐值**: 3-7（大多数问题）
- **最大值**: 20

**说明**:
- 大多数问题在 3-5 轮内解决
- 复杂问题可能需要 7-10 轮
- 增加轮数会延长诊断时间和增加 API 成本

**配置示例**:
```bash
# 快速诊断（3 轮）
MAX_ROUNDS=3

# 标准诊断（10 轮，默认）
MAX_ROUNDS=10

# 深度诊断（15 轮）
MAX_ROUNDS=15
```

---

### TOOL_TIMEOUT (可选)

单个工具执行的最大时间（秒）。

- **默认值**: 30
- **推荐值**: 30-60

**说明**:
- 超时后工具会被终止
- 增加超时可以处理慢速集群
- 过长的超时会降低用户体验

**配置示例**:
```bash
# 快速响应（20 秒）
TOOL_TIMEOUT=20

# 标准响应（30 秒，默认）
TOOL_TIMEOUT=30

# 大型集群（60 秒）
TOOL_TIMEOUT=60
```

---

### MAX_CONCURRENT_TOOLS (可选)

同时执行的工具最大数量。

- **默认值**: 5
- **推荐值**: 3-10

**说明**:
- 并发执行可以提高速度
- 过高的并发会增加资源消耗
- T0 检查会自动并发所有工具

**配置示例**:
```bash
# 保守并发（3）
MAX_CONCURRENT_TOOLS=3

# 标准并发（5，默认）
MAX_CONCURRENT_TOOLS=5

# 激进并发（10）
MAX_CONCURRENT_TOOLS=10
```

---

## 🐘 Kubernetes 配置

### KUBECONFIG (可选)

Kubernetes 配置文件路径。

**默认行为**: 使用 `~/.kube/config`

**多集群配置**:

```bash
# 方法 1: 环境变量
export KUBECONFIG=/path/to/cluster1-config

# 方法 2: 切换上下文
kubectl config use-context cluster2

# 方法 3: 合并多个配置
export KUBECONFIG=/path/to/config1:/path/to/config2
```

---

## 📊 日志和调试

### LOG_LEVEL (可选)

控制日志输出的详细程度。

- **默认值**: `INFO`
- **可选值**: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**说明**:
- `DEBUG`: 详细的调试信息，包括所有 API 调用
- `INFO`: 一般信息，包括诊断进度
- `WARNING`: 仅警告信息
- `ERROR`: 仅错误信息

**配置示例**:
```bash
# 调试模式
LOG_LEVEL=DEBUG

# 标准模式（默认）
LOG_LEVEL=INFO

# 静默模式
LOG_LEVEL=ERROR
```

**使用场景**:
- 开发和调试: `DEBUG`
- 日常使用: `INFO`
- 自动化脚本: `WARNING` 或 `ERROR`

---

### DIAGNOSIS_REPORT_DIR (可选)

诊断报告保存目录。

- **默认值**: 当前目录 (`./`)

**配置示例**:
```bash
# 保存到当前目录
DIAGNOSIS_REPORT_DIR=./

# 保存到特定目录
DIAGNOSIS_REPORT_DIR=./diagnosis_reports

# 保存到绝对路径
DIAGNOSIS_REPORT_DIR=/var/log/kube-ovn-checker
```

**报告命名格式**:
```
diagnosis_report_YYYYMMDD_HHMMSS.json
```

---

## 🚀 高级配置

### DISABLE_CACHE (可选)

禁用 Kubernetes API 结果缓存。

- **默认值**: `false` (启用缓存)
- **推荐**: 保持启用以提高性能

**配置示例**:
```bash
# 启用缓存（默认，推荐）
DISABLE_CACHE=false

# 禁用缓存（调试时）
DISABLE_CACHE=true
```

**缓存机制**:
- Pod 列表: 缓存 30 秒
- Node 信息: 缓存 60 秒
- Subnet 状态: 缓存 60 秒

---

### CACHE_TTL (可选)

缓存过期时间（秒）。

- **默认值**: 30
- **推荐值**: 30-120

**配置示例**:
```bash
# 短缓存（30 秒，默认）
CACHE_TTL=30

# 长缓存（120 秒）
CACHE_TTL=120
```

---

## 📝 完整配置示例

### 场景 1: OpenAI 生产环境

```bash
# .env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
OPENAI_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o
TEMPERATURE=0.0
MAX_ROUNDS=10
LOG_LEVEL=INFO
```

---

### 场景 2: DeepSeek 开发环境

```bash
# .env
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
OPENAI_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
TEMPERATURE=0.0
MAX_ROUNDS=7
LOG_LEVEL=DEBUG
```

---

### 场景 3: 本地 Ollama（离线/隐私）

```bash
# .env
OPENAI_API_BASE=http://localhost:11434/v1
LLM_MODEL=llama3:70b
OPENAI_API_KEY=ollama  # Ollama 不需要真实 Key
TEMPERATURE=0.0
MAX_ROUNDS=5
```

---

### 场景 4: 智谱 AI（国内用户）

```bash
# .env
OPENAI_API_KEY=xxxxxxxxxxxxx.yourkey
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=glm-4-flash
TEMPERATURE=0.0
MAX_ROUNDS=8
```

---

## 🔒 安全最佳实践

### 1. 保护 API Key

```bash
# ❌ 错误: 在命令行中暴露 Key
export OPENAI_API_KEY=sk-proj-xxx
./kube-ovn-checker "test"

# ✅ 正确: 使用 .env 文件
echo 'OPENAI_API_KEY=sk-proj-xxx' > .env
chmod 600 .env
```

### 2. 最小权限原则

- 使用只读 Kubernetes 账户
- 限制 API Key 的权限和速率
- 定期轮换 API Key

### 3. 敏感环境

```bash
# 设置文件权限
chmod 600 .env

# 使用密钥管理服务（生产环境）
# HashiCorp Vault, AWS Secrets Manager 等
```

---

## ✅ 配置验证

### 检查清单

在开始使用前，确保：

- [ ] `.env` 文件已创建
- [ ] `OPENAI_API_KEY` 已设置
- [ ] API Key 有效且有余额
- [ ] kubectl 可以连接集群
- [ ] 有足够的集群权限（只读即可）

### 验证命令

```bash
# 1. 检查配置文件
ls -la .env

# 2. 检查环境变量
env | grep OPENAI

# 3. 测试 API 连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 4. 测试 kubectl 连接
kubectl get nodes

# 5. 运行简单诊断
./kube-ovn-checker "test"
```

---

## 🐛 常见配置问题

### Q1: 配置不生效？

**检查**:
```bash
# 确认 .env 文件位置
ls -la .env

# 确认环境变量
echo $OPENAI_API_KEY

# 确认文件权限
ls -l .env
```

**解决**:
- 确保 `.env` 在项目根目录
- 重新加载环境变量
- 检查文件权限

---

### Q2: API Key 验证失败？

**检查**:
```bash
# 测试 API 连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**可能原因**:
- API Key 错误
- 账户余额不足
- 网络连接问题
- API 端点配置错误

---

### Q3: 模型不兼容？

**症状**:
```
Error: Model 'xxx' does not exist or you do not have access
```

**解决**:
- 检查模型名称是否正确
- 确认 API Key 有该模型的访问权限
- 查看提供商的模型列表

---

## 📚 更多资源

- [快速开始](quick-start.md)
- [安装指南](installation.md)
- [故障排除](troubleshooting.md)
- [安全考虑](security-considerations.md)

---

**下一步**: [故障排除](troubleshooting.md) | [诊断基础](diagnosis-basics.md)
