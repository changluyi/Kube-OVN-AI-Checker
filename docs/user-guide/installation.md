# 📦 安装指南

本指南将帮助您在各种环境中安装 Kube-OVN-LangGraph-Checker。

## 📋 系统要求

### 最低要求

| 组件 | 最低版本 | 说明 |
|-----|---------|------|
| **Python** | 3.9 | 推荐 3.11+ |
| **内存** | 500MB | 可用内存 |
| **磁盘** | 100MB | 安装空间 |
| **网络** | 稳定连接 | 访问 LLM API 和 Kubernetes 集群 |

### 推荐配置

| 组件 | 推荐配置 | 说明 |
|-----|---------|------|
| **Python** | 3.11+ | 更好的性能和特性支持 |
| **内存** | 2GB | 大型集群诊断 |
| **kubectl** | 最新版 | Kubernetes 命令行工具 |
| **LLM API** | gpt-4o 或兼容服务 | 最佳诊断质量 |

### Kubernetes 集群要求

- **版本**: Kubernetes 1.20+
- **网络**: Kube-OVN 已安装
- **权限**: 对集群的只读访问权限
- **节点**: 至少 1 个节点（用于测试）

## 🔧 安装方法

### 方法 1: pip 安装（推荐）

适用于大多数用户，简单快捷。

```bash
# 使用 pip 安装
pip install kube-ovn-checker

# 验证安装
kube-ovn-checker --version
```

**升级**:
```bash
pip install --upgrade kube-ovn-checker
```

**卸载**:
```bash
pip uninstall kube-ovn-checker
```

---

### 方法 2: 从源码安装（开发模式）

适用于开发者或需要最新功能的用户。

```bash
# 1. 克隆仓库
git clone https://github.com/xxx/kube-ovn-langgraph-checker.git
cd kube-ovn-langgraph-checker

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖（开发模式）
pip install -e .
```

**开发模式的优势**:
- ✅ 代码修改立即生效，无需重新安装
- ✅ 可以直接编辑代码
- ✅ 便于调试和开发

---

### 方法 3: Docker 容器

适用于需要隔离环境或批量部署的场景。

```bash
# 1. 构建镜像
docker build -t kube-ovn-checker:latest .

# 2. 运行容器
docker run --rm \
  -v ~/.kube:/root/.kube:ro \
  -e OPENAI_API_KEY=your-api-key \
  kube-ovn-checker:latest \
  "帮我检查集群状态"

# 3. 使用 Docker Compose（可选）
docker-compose up -d
```

**`Dockerfile` 示例**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装工具
COPY . .
RUN pip install -e .

# 挂载 kubeconfig
VOLUME ["/root/.kube"]

# 设置环境变量
ENV OPENAI_API_KEY=""

# 默认命令
CMD ["kube-ovn-checker", "--help"]
```

---

## 🔐 环境验证

安装完成后，请验证所有组件是否正常工作。

### 1. 验证 Python 环境

```bash
# 检查 Python 版本
python --version
# 应该输出: Python 3.9.x 或更高

# 检查 pip 版本
pip --version
```

### 2. 验证 kubectl 配置

```bash
# 检查集群信息
kubectl cluster-info
# 应该显示: Kubernetes control plane is running...

# 检查节点状态
kubectl get nodes
# 应该显示节点列表和状态

# 检查当前上下文
kubectl config current-context
# 应该显示: cluster-name

# 检查 Kube-OVN 组件
kubectl get pods -n kube-system | grep kube-ovn
# 应该显示: kube-ovn-controller, kube-ovn-cni 等
```

### 3. 验证 LLM API Key

```bash
# 检查环境变量
echo $OPENAI_API_KEY
# 应该显示您的 API Key（或配置文件中的值）

# 测试 API 连接（可选）
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
# 应该显示: 可用模型列表
```

### 4. 验证工具安装

```bash
# 检查工具版本
./kube-ovn-checker --version
# 应该显示: Kube-OVN-LangGraph-Checker v0.1.0

# 查看帮助信息
./kube-ovn-checker --help
```

## ⚙️ 详细配置

### 配置文件

工具使用 `.env` 文件存储配置，从 `.env.example` 复制：

```bash
cp .env.example .env
vim .env  # 编辑配置
```

**最小配置**:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
```

**完整配置示例**: 见 [配置指南](configuration.md)

### Kubernetes 权限

工具只需要 **只读权限**，以下是必需的权限：

**ClusterRole 示例**:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kube-ovn-checker
rules:
# Pod 相关
- apiGroups: [""]
  resources: ["pods", "pods/log", "pods/status"]
  verbs: ["get", "list", "watch"]

# Node 相关
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list"]

# Event 相关
- apiGroups: [""]
  resources: ["events"]
  verbs: ["get", "list", "watch"]

# Kube-OVN CRD
- apiGroups: ["kubeovn.io"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]

# Deployment/DaemonSet
- apiGroups: ["apps"]
  resources: ["deployments", "daemonsets", "statefulsets"]
  verbs: ["get", "list"]
```

**创建权限**:
```bash
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: kube-ovn-checker
rules:
  # (见上文完整规则)
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: kube-ovn-checker
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: kube-ovn-checker
subjects:
  - kind: ServiceAccount
    name: default
    namespace: default
EOF
```

### 多集群配置

如果您有多个 Kubernetes 集群，可以：

**方法 1: 使用 KUBECONFIG**
```bash
export KUBECONFIG=/path/to/cluster1-kubeconfig
./kube-ovn-checker "检查集群1"
```

**方法 2: 切换上下文**
```bash
# 查看所有上下文
kubectl config get-contexts

# 切换到特定集群
kubectl config use-context cluster2

# 运行诊断
./kube-ovn-checker "检查集群2"
```

## 🐛 常见安装问题

### 问题 1: 依赖安装失败

**症状**:
```
ERROR: Could not find a version that satisfies the requirement...
```

**解决方案**:

1. **升级 pip**:
```bash
pip install --upgrade pip
```

2. **使用虚拟环境**:
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

3. **使用国内镜像** (中国大陆):
```bash
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

4. **检查 Python 版本**:
```bash
python --version  # 必须是 3.9+
```

---

### 问题 2: 权限不足

**症状**:
```
PermissionError: [Errno 13] Permission denied
```

**解决方案**:

1. **使用用户安装**:
```bash
pip install --user kube-ovn-checker
```

2. **使用虚拟环境** (推荐):
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

3. **使用 sudo** (不推荐):
```bash
sudo pip install kube-ovn-checker
```

---

### 问题 3: kubectl 无法连接

**症状**:
```
Unable to connect to the server: dial tcp: lookup xxx on 53: server misbehaving
```

**解决方案**:

1. **检查 kubeconfig**:
```bash
kubectl config view
```

2. **测试集群连接**:
```bash
kubectl cluster-info
kubectl get nodes
```

3. **切换上下文**:
```bash
kubectl config use-context correct-cluster-name
```

4. **检查网络**:
```bash
ping kubernetes-api-server
```

---

### 问题 4: API Key 无效

**症状**:
```
Error: AuthenticationError: Incorrect API key provided
```

**解决方案**:

1. **验证 API Key**:
```bash
echo $OPENAI_API_KEY
# 应该显示您的 Key
```

2. **检查账户余额**:
登录提供商控制台检查余额

3. **重新生成 API Key**:
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/

4. **测试 API 连接**:
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

### 问题 5: 虚拟环境激活失败

**症状** (Windows):
```
venv\Scripts\activate : 无法加载文件，因为在此系统上禁止运行脚本
```

**解决方案**:

```powershell
# 临时允许脚本执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 然后激活
venv\Scripts\activate
```

---

## 🚀 下一步

安装完成后，请继续阅读：

1. ⚙️ [配置指南](configuration.md) - 详细的配置选项
2. 🚀 [快速开始](quick-start.md) - 5 分钟第一次诊断
3. 🔧 [故障排除](troubleshooting.md) - 常见问题解决

## 💡 提示

### 安装建议

1. **始终使用虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. **保持依赖更新**
   ```bash
   pip install --upgrade kube-ovn-checker
   ```

3. **固定版本** (生产环境)
   ```bash
   pip install kube-ovn-checker==0.1.0
   ```

### 验证清单

在开始使用前，确保：

- [ ] Python 3.9+ 已安装
- [ ] 工具已成功安装 (`kube-ovn-checker --version`)
- [ ] `.env` 文件已配置
- [ ] kubectl 可以连接集群
- [ ] LLM API Key 有效
- [ ] 有足够的集群权限

---

**下一步**: [配置指南](configuration.md) | [快速开始](quick-start.md) | [故障排除](troubleshooting.md)
