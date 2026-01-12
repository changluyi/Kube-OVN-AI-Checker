# 🚀 快速开始

欢迎使用 Kube-OVN-LangGraph-Checker！本指南将帮助您在 **5 分钟内**完成第一次 Kube-OVN 网络诊断。

## 📋 前置要求

在开始之前，请确保您的环境满足以下要求：

- ✅ **Python 3.9 或更高版本**
- ✅ **kubectl 已配置**，能够访问您的 Kubernetes 集群
- ✅ **LLM API Key** (OpenAI / Azure OpenAI / DeepSeek / 智谱 AI / Ollama)

### 快速检查

```bash
# 检查 Python 版本
python --version  # 应该 >= 3.9

# 检查 kubectl 配置
kubectl cluster-info  # 应该显示集群信息

# 检查 kubectl 连接
kubectl get nodes  # 应该显示节点列表
```

## 🎯 5 步快速体验

### 步骤 1: 克隆仓库 (30 秒)

```bash
git clone https://github.com/xxx/kube-ovn-langgraph-checker.git
cd kube-ovn-langgraph-checker
```

### 步骤 2: 安装依赖 (1-2 分钟)

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

**预期输出**:
```
Successfully installed kube-ovn-checker-0.1.0
```

### 步骤 3: 配置 API Key (30 秒)

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填入您的 API Key
# vim .env  # 或使用其他编辑器
```

**`.env` 文件内容**:
```bash
# 最小配置示例
OPENAI_API_KEY=sk-proj-your-api-key-here

# 如果使用其他提供商，还需要设置:
# OPENAI_API_BASE=https://api.deepseek.com/v1  # DeepSeek 示例
# LLM_MODEL=deepseek-chat
```

**获取 API Key**:
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/
- 智谱 AI: https://open.bigmodel.cn/

### 步骤 4: 验证安装 (30 秒)

```bash
# 查看帮助信息
./kube-ovn-checker --help
```

**预期输出**:
```
Kube-OVN-LangGraph-Checker - 智能网络诊断工具

用法: kube-ovn-checker "问题描述"
  或: echo "问题" | kube-ovn-checker
  或: kube-ovn-checker (交互式输入)

选项:
  --help    显示此帮助信息
  --version 显示版本信息
```

### 步骤 5: 第一次诊断 (2-3 分钟)

```bash
# 运行第一次诊断
./kube-ovn-checker "帮我检查 kube-ovn-controller 的状态"
```

**预期输出**:

```
🧠 Kube-OVN 智能诊断工具 v0.1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%  10s

🎯 诊断进度

✓ T0 快速检查完成 (10.2s)
  - 检查了 3 个 Deployments
  - 检查了 3 个 DaemonSets
  - 检查了 3 个 Endpoints

🤖 AI 正在分析...

第 1 轮: 分析 T0 结果...
  Thought: 所有核心组件健康，没有明显问题

第 2 轮: 收集详细信息...
  ✓ 收集 kube-ovn-controller 日志
  ✓ 收集 Pod 状态

第 3 轮: 验证假设...
  ✓ 收集 OVN DB 状态

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%  45s

🎯 诊断结果

📍 问题: kube-ovn-controller 状态正常

🔍 根本原因:
  组件运行正常，没有发现异常

✅ 状态: 健康

💡 建议:
  - 定期检查组件健康状态
  - 监控日志中的错误信息

📊 统计信息:
  - 诊断轮数: 3
  - 工具调用: 5 次
  - 总耗时: 45 秒

💾 报告已保存: diagnosis_report_20260111_143022.json
```

## 🎉 恭喜！

您已经成功完成了第一次诊断！

## 📖 下一步

现在您已经完成了快速开始，接下来可以：

### 1. 阅读完整文档

- 📖 [安装指南](installation.md) - 详细的安装方法和环境配置
- ⚙️ [配置指南](configuration.md) - 所有配置选项和 LLM 提供商设置
- 🔧 [故障排除](troubleshooting.md) - 常见问题和解决方案

### 2. 了解诊断基础

- 📚 [诊断基础](diagnosis-basics.md) - 理解 T0/T1/T2 分层诊断
- 📊 [结果解读](understanding-results.md) - 如何理解诊断结果
- 🛡️ [安全考虑](security-considerations.md) - 只读限制和数据隐私

### 3. 查看真实案例

- 📋 [案例库](examples/) - 5+ 真实诊断案例，展示工具如何解决实际问题

## ❓ 遇到问题？

### 常见问题

**Q: 安装失败，提示依赖错误？**

```bash
# 升级 pip
pip install --upgrade pip

# 使用虚拟环境
python -m venv venv
source venv/bin/activate
pip install -e .
```

**Q: API Key 验证失败？**

```bash
# 检查环境变量
echo $OPENAI_API_KEY

# 测试 API 连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Q: kubectl 连接失败？**

```bash
# 检查 kubeconfig
kubectl cluster-info
kubectl config current-context

# 切换到正确的集群
kubectl config use-context your-cluster-name
```

### 获取帮助

- 📖 查看 [故障排除指南](troubleshooting.md)
- 🐛 提交 [GitHub Issue](https://github.com/xxx/kube-ovn-langgraph-checker/issues)
- 💬 加入社区讨论

## 🚀 开始诊断

现在您已经准备好了！尝试诊断一些常见问题：

```bash
# 检查 Pod 通信问题
./kube-ovn-checker "Pod A 无法访问 Pod B"

# 检查网络连通性
./kube-ovn-checker "跨节点 Pod 无法通信"

# 检查 IP 耗尽
./kube-ovn-checker "新 Pod 一直 Pending，提示 IP 不足"

# 检查 Controller 问题
./kube-ovn-checker "kube-ovn-controller 一直重启"
```

## 💡 提示

1. **问题描述越具体，诊断越准确**
   ```
   ✅ 好: "Pod nginx-deploy-xxx 在 default 命名空间无法访问 10.16.0.5"
   ❌ 差: "网络有问题"
   ```

2. **使用中文或英文都可以**
   工具支持中英文问题描述。

3. **查看完整诊断过程**
   报告会保存为 JSON 文件，包含完整的思维链和证据。

4. **信任但要验证**
   工具给出建议后，请人工审核再执行修复操作。

---

**下一步**: [安装指南](installation.md) | [配置指南](configuration.md) | [故障排除](troubleshooting.md)
