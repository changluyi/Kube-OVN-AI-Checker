# 🚀 开发环境设置

本指南帮助您搭建 Kube-OVN-LangGraph-Checker 的开发环境。

## 📋 系统要求

### 必需
- Python 3.9+
- Poetry 或 pip
- Git
- 代码编辑器 (VS Code / PyCharm)

### 推荐
- Docker (用于测试)
- kubectl (用于本地测试)
- Kind 或 Minikube (本地 K8s 集群)

## 🔧 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/xxx/kube-ovn-langgraph-checker.git
cd kube-ovn-langgraph-checker
```

### 2. 创建虚拟环境

```bash
# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 使用 poetry (推荐)
poetry install
```

### 3. 安装开发依赖

```bash
# 开发模式安装
pip install -e ".[dev]"

# 或使用 poetry
poetry install --with dev
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 5. 验证安装

```bash
# 运行测试
pytest tests/ -v

# 运行工具
./kube-ovn-checker --help
```

## 🛠️ 开发工具配置

### VS Code

**推荐扩展**:
- Python
- Pylance
- Python Test Explorer
- GitLens

**`.vscode/settings.json`**:
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"]
}
```

**`.vscode/launch.json`** (调试配置):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug CLI",
      "type": "python",
      "request": "launch",
      "module": "kube_ovn_checker.cli.main",
      "args": ["测试问题"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Run Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/"],
      "console": "integratedTerminal"
    }
  ]
}
```

### PyCharm

1. 打开项目后，设置 Python 解释器为虚拟环境
2. Settings → Tools → Python Integrated Tools → Testing → pytest
3. Run → Edit Configurations → 添加 Python 配置

## 💻 代码风格

### 格式化

```bash
# Black (格式化)
black kube_ovn_checker/

# isort (导入排序)
isort kube_ovn_checker/

# 一键格式化
black kube_ovn_checker/ && isort kube_ovn_checker/
```

### Linting

```bash
# Pylint (代码质量)
pylint kube_ovn_checker/

# mypy (类型检查)
mypy kube_ovn_checker/
```

### Pre-commit Hooks

```bash
# 安装 pre-commit
pip install pre-commit

# 安装 hooks
pre-commit install

# 手动运行
pre-commit run --all-files
```

**`.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.9

  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

## 🧪 测试

### 运行测试

```bash
# 所有测试
pytest tests/

# 单个测试文件
pytest tests/test_tool_registration.py

# 带覆盖率
pytest --cov=kube_ovn_checker tests/

# 详细输出
pytest -v tests/
```

### 编写测试

见 [testing.md](testing.md)

## 🐛 调试

### 本地调试 CLI

```bash
# 设置环境变量
export LOG_LEVEL=DEBUG

# 运行
python -m kube_ovn_checker.cli.main "测试问题"
```

### 调试 LangGraph Agent

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用 ipdb (更好用)
import ipdb; ipdb.set_trace()
```

### 查看 LangGraph 执行图

```python
from kube_ovn_checker.analyzers.llm_agent_analyzer import LLMAgentAnalyzer

analyzer = LLMAgentAnalyzer()

# 生成状态图
analyzer.graph.get_graph().print_ascii()
```

## 📦 常用开发任务

### 添加新工具

见 [adding-tools.md](adding-tools.md)

### 修改知识库

```bash
# 知识库位置
ls kube_ovn_checker/knowledge/principles/
ls kube_ovn_checker/knowledge/workflows/

# 编辑文档后，重新安装
pip install -e .
```

### 运行集成测试

```bash
# 需要 Kind 集群
kind create cluster --name test

# 运行集成测试
pytest tests/integration/

# 清理
kind delete cluster --name test
```

## 🚀 下一步

- 阅读 [code-structure.md](code-structure.md) 了解代码组织
- 查看 [adding-tools.md](adding-tools.md) 学习如何扩展
- 阅读 [contributing.md](contributing.md) 了解贡献流程

---

**相关文档**: [代码结构](code-structure.md) | [添加工具](adding-tools.md) | [测试指南](testing.md)
