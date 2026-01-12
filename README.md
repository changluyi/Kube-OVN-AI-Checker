# Kube-OVN Checker

> LLM-driven Kube-OVN 网络诊断工具,基于 LangGraph 实现

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.5-green.svg)](https://github.com/langchain-ai/langgraph)
[![LangChain](https://img.shields.io/badge/LangChain-1.2.0-blue.svg)](https://github.com/langchain-ai/langchain)

## 🎯 项目简介

Kube-OVN Checker 是一个智能化的 Kube-OVN 网络诊断工具,通过 LLM (大语言模型) 驱动的多轮交互式诊断,帮助运维人员快速定位和解决 Kube-OVN 集群中的网络问题。

### 核心特性

- ⚡ **T0 快速健康检查** - 10秒内完成核心组件健康状态扫描
- 🤖 **LLM Agent 多轮诊断** - 自主决策收集策略,渐进式推理
- 🛠️ **26 个诊断工具** - 覆盖 Pod、Subnet、Node、Controller、OVN/OVS 等各个层面
- 📚 **知识库驱动** - 内置 Kube-OVN 网络原理知识,精准匹配问题场景
- 📊 **智能分析** - 基于收集的证据自动识别根本原因
- 💡 **可操作建议** - 提供具体的解决方案步骤

---

## 📦 安装

### 前置要求

- Python 3.9+
- 有效的 Kubernetes 集群 (Kube-OVN 已安装)
- kubectl 配置正确 (`KUBECONFIG` 环境变量)
- OpenAI API Key 或兼容的 LLM API (如智谱 GLM)

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/changluyi/Kube-OVN-AI-Checker.git
cd Kube-OVN-AI-Checker

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

---

## ⚙️ 配置

### 环境变量

创建 `.env` 文件或设置环境变量:

```bash
# LLM API 配置 (必需)
export OPENAI_API_KEY="your-openai-api-key"

# 或使用兼容的 API (如智谱 GLM)
export OPENAI_API_BASE="https://open.bigmodel.cn/api/paas/v4"
export OPENAI_API_KEY="your-glm-api-key"

# Kubernetes 配置
export KUBECONFIG="/path/to/kubeconfig"

# 可选: 自定义模型
export LLM_MODEL="glm-4.6"  # 默认: glm-4.6
```

---

## 🚀 快速开始

### 命令行使用

```bash
# 基本用法
./kube-ovn-checker "描述你的网络问题"

# 示例 1: Pod 无法访问外网
./kube-ovn-checker "kube-system下的kube-ovn-pinger-nl2r6 ping 外网114.114.114.114不通"

# 示例 2: Pod 间网络不通
./kube-ovn-checker "default命名空间下的nginx-pod无法访问backend-svc服务"

# 示例 3: 跨节点网络问题
./kube-ovn-checker "node-1上的Pod无法ping通node-2上的Pod"
```

### 诊断输出示例

```bash
./kube-ovn-checker "kube-system下的kube-ovn-pinger-nl2r6 ping 外网114.114.114.114不通"
```

**输出结果：**

```
🔧 Kube-OVN 智能诊断工具

配置信息:
  模型: glm-4.6
  API: https://open.bigmodel.cn/api/paas/v4


╭──────────────────────╮
│ 🚀 Kube-OVN 智能诊断 │
╰──────────────────────╯

📝 问题: kube-system下的kube-ovn-pinger-nl2r6 ping 外网114.114.114.114不通

使用模型: glm-4.6
API Base: https://open.bigmodel.cn/api/paas/v4

🤖 初始化 LLM Agent...

✅ Agent 已就绪

🔍 开始诊断...

Agent 将自主决定使用哪些工具来分析问题...

📊 构建初始上下文...
📚 匹配诊断规则: pod_to_external (置信度: 80.0%)
📚 注入知识库内容...
✅ 自动发现 16 个知识文档
✅ 知识注入成功 (使用知识库)
🔄 开始智能诊断...
➡️  将调用: collect_t0_check(namespace=kube-system, scope=cluster)
💭 思考: 用户报告 kube-ovn-pinger Pod 无法 ping 通外网，这是典型的 Egress NAT 问题。我需要先进行 T0 快速健康检查，了解集群整体状态，然后针对 Egress NAT 进行诊断。
决策: 执行 T0 快速健康检查，了解 Kube-OVN 核心组件状态
预期: 应...
🔧 调用工具: collect_t0_check (namespace=kube-system, scope=cluster)
  📊 [T0] 检查 Deployments...
  📊 [T0] 检查 DaemonSets...
  📊 [T0] 检查 OVN 数据库 Endpoints...
  📊 [T0] 检查 Controller 状态...
  📦 [T0] 获取集群 Pod 统计...
  🌐 [T0] 获取 Subnet 概览...
  🔧 [T0] 获取节点网络配置...
✅ 工具完成: collect_t0_check (已获取)
➡️  将调用: collect_pod_describe(pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system)
💭 思考: T0 检查显示所有 Kube-OVN 组件都健康，说明控制平面正常。现在需要查看具体的 kube-ovn-pinger Pod 状态和日志，了解 ping 失败的具体原因。
决策: 查看 kube-ovn-pinger-nl2r6 Pod 的详细信息和日志
预期: 应该能看到 Pod 运行状...
🔧 调用工具: collect_pod_describe (pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system)
✅ 工具完成: collect_pod_describe (已获取)
➡️  将调用: collect_pod_logs(pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, tail=50, filter_errors=True)
💭 思考: Pod 运行正常，IP 是 10.16.0.6，在 kube-ovn-control-plane 节点上。现在需要查看 pinger 的日志，了解 ping 114.114.114.114 失败的具体错误信息。
决策: 查看 kube-ovn-pinger-nl2r6 的日志
预期: 应该能...
📋 分析日志: collect_pod_logs (pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, tail=50, filter_errors=True)
✅ 工具完成: collect_pod_logs (已获取)
➡️  将调用: collect_pod_logs(pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, tail=10, filter_errors=False)
💭 思考: 从日志看，kube-ovn-pinger 配置的是 ping 1.1.1.1，而且 ping 1.1.1.1 是成功的（loss count 0，average rtt 85ms）。用户说 ping 114.114.114.114 不通，但 pinger 默认配置不是 ping 114.11...
📋 分析日志: collect_pod_logs (pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, tail=10, filter_errors=False)
✅ 工具完成: collect_pod_logs (已获取)
➡️  将调用: collect_ovn_trace(target_type=pod, target_name=kube-system/kube-ovn-pinger-nl2r6, target_ip=114.114.114.114, protocol=icmp)
💭 思考: 从日志确认 pinger 默认 ping 1.1.1.1 是成功的。现在需要使用 ovn-trace 来分析从 Pod (10.16.0.6) ping 114.114.114.114 的流量路径，看看是否在 OVN 层面被阻止。
决策: 使用 ovn-trace 分析从 Pod ping ...
🔧 调用工具: collect_ovn_trace (target_type=pod, target_name=kube-system/kube-ovn-pinger-nl2r6, target_ip=114.114.114.114, protocol=icmp)
✅ 工具完成: collect_ovn_trace (已获取)
➡️  将调用: collect_tcpdump(pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, count=5, filter_expr=icmp and host 114.114.114.114, timeout=10)
💭 思考: ovn-trace 显示流量在逻辑层面被 loopback 检查阻止，但这只是逻辑模拟的限制。需要实际抓包来验证流量是否真正离开 Pod。根据 ovn-trace 的建议，下一步应该在 Pod 的 veth 网卡上抓包。
决策: 在 kube-ovn-pinger Pod 的 veth 网卡...
🔧 调用工具: collect_tcpdump (pod_name=kube-ovn-pinger-nl2r6, namespace=kube-system, count=5, filter_expr=icmp and host 114.114.114.114, timeout=10)
✅ 工具完成: collect_tcpdump (已获取)
➡️  将调用: collect_node_ip_addr(node_name=kube-ovn-control-plane)
💭 思考: 很好！Pod 的 veth 网卡上确实有 ICMP 请求包发出，源 IP 是 10.16.0.6，目标 IP 是 114.114.114.114。这说明流量成功离开了 Pod。现在需要检查这些流量是否真正离开了节点，在节点的物理网卡上抓包验证。
决策: 在节点 kube-ovn-contro...
🔧 调用工具: collect_node_ip_addr (node_name=kube-ovn-control-plane)
✅ 工具完成: collect_node_ip_addr (已获取)
➡️  将调用: collect_node_tcpdump(node_name=kube-ovn-control-plane, interface=eth0, count=5, filter_expr=icmp and host 114.114.114.114, timeout=10)
💭 思考: 节点的物理网卡是 eth0，IP 是 172.18.0.3。现在需要在 eth0 上抓包，验证 ping 114.114.114.114 的流量是否真正离开节点，以及是否经过了 NAT。
决策: 在节点 eth0 网卡上抓包，验证 ping 114.114.114.114 的流量
预期: 应...
🔧 调用工具: collect_node_tcpdump (node_name=kube-ovn-control-plane, interface=eth0, count=5, filter_expr=icmp and host 114.114.114.114, timeout=10)
✅ 工具完成: collect_node_tcpdump (已获取)
➡️  将调用: collect_node_iptables(node_name=kube-ovn-control-plane, table=nat)
💭 思考: 非常好！现在确认了关键信息：
1. Pod veth 上：源 IP 是 10.16.0.6（Pod IP）
2. 节点 eth0 上：源 IP 是 172.18.0.3（节点 IP）

这说明 NAT 工作正常，流量成功离开了节点。但是没有看到 ICMP 回复包，这表明问题在外部网络。让我检查...
🔧 调用工具: collect_node_iptables (node_name=kube-ovn-control-plane, table=nat)
✅ 工具完成: collect_node_iptables (已获取)
➡️  将调用: collect_node_tcpdump(node_name=kube-ovn-control-plane, interface=eth0, count=3, filter_expr=icmp and host 8.8.8.8, timeout=10)
💭 思考: 从 iptables 规则可以看到 OVN 的 NAT 配置，特别是 `-A OVN-POSTROUTING -m set --match-set ovn40subnets src -m set --match-set ovn40subnets dst -j OVN-MASQUERADE` ...
🔧 调用工具: collect_node_tcpdump (node_name=kube-ovn-control-plane, interface=eth0, count=3, filter_expr=icmp and host 8.8.8.8, timeout=10)
✅ 工具完成: collect_node_tcpdump (已获取)
✅ 诊断完成 (耗时 103.8秒, 共 10 轮工具调用)
🎯 提取诊断结果...

✅ 诊断完成


╭─────────────╮
│ 🎯 诊断结果 │
╰─────────────╯

🧠 诊断思维链:

  1. 思考: 用户报告 kube-ovn-pinger Pod 无法 ping 通外网，这是典型的 Egress NAT 问题。我需要先进行 T0 快速健康检查，了解集群整体状态，然后针对 Egress NAT 进行诊断。

决策: 执行 T0 快速健康检查，了解 Kube-OVN 核心组件状态
预期: ...
     → 调用: collect_t0_check(scope=cluster)

  2. 思考: T0 检查显示所有 Kube-OVN 组件都健康，说明控制平面正常。现在需要查看具体的 kube-ovn-pinger Pod 状态和日志，了解 ping 失败的具体原因。

决策: 查看 kube-ovn-pinger-nl2r6 Pod 的详细信息和日志
预期: 应该能看到 Pod 运行...
     → 调用: collect_pod_describe(pod_name=kube-ovn-pinger-nl2r6)

  3. 思考: Pod 运行正常，IP 是 10.16.0.6，在 kube-ovn-control-plane 节点上。现在需要查看 pinger 的日志，了解 ping 114.114.114.114 失败的具体错误信息。

决策: 查看 kube-ovn-pinger-nl2r6 的日志
预期: 应该...
     → 调用: collect_pod_logs(pod_name=kube-ovn-pinger-nl2r6, tail=50, filter_errors=True)

  4. 思考: 从日志看，kube-ovn-pinger 配置的是 ping 1.1.1.1，而且 ping 1.1.1.1 是成功的（loss count 0，average rtt 85ms）。用户说 ping 114.114.114.114 不通，但 pinger 默认配置不是 ping 114.11...
     → 调用: collect_pod_logs(pod_name=kube-ovn-pinger-nl2r6, tail=10, filter_errors=False)

  5. 思考: 从日志确认 pinger 默认 ping 1.1.1.1 是成功的。现在需要使用 ovn-trace 来分析从 Pod (10.16.0.6) ping 114.114.114.114 的流量路径，看看是否在 OVN 层面被阻止。

决策: 使用 ovn-trace 分析从 Pod ping...
     → 调用: collect_ovn_trace(target_type=pod, target_name=kube-system/kube-ovn-pinger-nl2r6, target_ip=114.11...)

  6. 思考: ovn-trace 显示流量在逻辑层面被 loopback 检查阻止，但这只是逻辑模拟的限制。需要实际抓包来验证流量是否真正离开 Pod。根据 ovn-trace 的建议，下一步应该在 Pod 的 veth 网卡上抓包。

决策: 在 kube-ovn-pinger Pod 的 veth 网...
     → 调用: collect_tcpdump(pod_name=kube-ovn-pinger-nl2r6, count=5, filter_expr=icmp and host 114.114.114.1...)

  7. 思考: 很好！Pod 的 veth 网卡上确实有 ICMP 请求包发出，源 IP 是 10.16.0.6，目标 IP 是 114.114.114.114。这说明流量成功离开了 Pod。现在需要检查这些流量是否真正离开了节点，在节点的物理网卡上抓包验证。

决策: 在节点 kube-ovn-contr...
     → 调用: collect_node_ip_addr(node_name=kube-ovn-control-plane)

  8. 思考: 节点的物理网卡是 eth0，IP 是 172.18.0.3。现在需要在 eth0 上抓包，验证 ping 114.114.114.114 的流量是否真正离开节点，以及是否经过了 NAT。

决策: 在节点 eth0 网卡上抓包，验证 ping 114.114.114.114 的流量
预期: ...
     → 调用: collect_node_tcpdump(node_name=kube-ovn-control-plane, interface=eth0, count=5, filter_expr=icmp and ...)

  9. 思考: 非常好！现在确认了关键信息：
1. Pod veth 上：源 IP 是 10.16.0.6（Pod IP）
2. 节点 eth0 上：源 IP 是 172.18.0.3（节点 IP）

这说明 NAT 工作正常，流量成功离开了节点。但是没有看到 ICMP 回复包，这表明问题在外部网络。让我检...
     → 调用: collect_node_iptables(node_name=kube-ovn-control-plane, table=nat)

  10. 思考: 从 iptables 规则可以看到 OVN 的 NAT 配置，特别是 `-A OVN-POSTROUTING -m set --match-set ovn40subnets src -m set --match-set ovn40subnets dst -j OVN-MASQUERADE` ...
     → 调用: collect_node_tcpdump(node_name=kube-ovn-control-plane, interface=eth0, count=3, filter_expr=icmp and ...)

──────────────────────────────────────────────────────────────────────

📋 问题: kube-system 下的 kube-ovn-pinger-nl2r6 Pod ping 外网 114.114.114.114 不通

🔍 根因: 外部网络问题，不是 Kube-OVN 配置问题

📊 诊断轮次: 10
🔧 调用工具: collect_node_ip_addr, collect_node_iptables, collect_node_tcpdump, collect_ovn_trace, collect_pod_describe, collect_pod_logs, collect_t0_check, collect_tcpdump

💾 保存报告...
✅ 已保存: diagnosis_report_20260112_092912.json


╭─────────────╮
│ ✨ 诊断完成 │
```

---

## 🏗️ 项目结构

```
Kube-OVN-AI-Checker/
├── kube_ovn_checker/
│   ├── collectors/              # 数据收集器
│   │   ├── k8s_client.py        # Kubernetes 客户端封装
│   │   ├── t0_collector.py      # T0 快速健康检查
│   │   └── resource_collector.py # 26+ 资源收集方法
│   │
│   ├── analyzers/               # LLM 分析器
│   │   ├── llm_agent_analyzer.py # LangGraph ReAct Agent
│   │   └── tools/               # LangChain Tools 封装
│   │
│   ├── knowledge/               # 知识库
│   │   ├── principles/          # 网络原理文档
│   │   │   ├── dataplane/       # 数据平面知识
│   │   │   │   ├── node-communication/  # Egress, Ingress, Join 网络
│   │   │   │   ├── pod-communication/    # Pod 间通信
│   │   │   │   └── service-communication/ # Service 通信
│   │   │   └── control-plane/  # 控制平面知识
│   │   ├── llm_retriever.py     # LLM 知识检索
│   │   └── injector.py          # 知识注入器
│   │
│   ├── reporters/               # 报告生成器
│   │   └── diagnostic_reporter.py
│   │
│   ├── llm/                    # LLM 客户端
│   │   └── client.py
│   │
│   └── cli/                    # 命令行接口
│       └── main.py
│
├── docs/                       # 详细文档
│   ├── architecture/overview.md
│   ├── user-guide/
│   └── developer-guide/
│
└── kube-ovn-checker            # 命令行入口
```

---

## 🛠️ 功能特性详解

### 1. T0 快速健康检查 (10秒)

自动检查以下核心组件:

**Deployments (3个)**:
- kube-ovn-controller
- kube-ovn-pinger
- kube-ovn-monitor

**DaemonSets (3个)**:
- kube-ovn-cni
- ovs-ovn
- ovs-others

**Endpoints (3个)**:
- kube-ovn-controller
- ovn-nb
- ovn-sb

对于不健康的组件,自动收集详细日志和事件信息。

### 2. 26 个 LangChain Tools

#### Pod 工具 (4个)
- `collect_pod_logs` - 收集 Pod 日志
- `collect_pod_describe` - 收集 Pod 详细信息
- `collect_pod_events` - 收集 Pod 事件
- `collect_tcpdump` - Pod 网卡抓包

#### Subnet 工具 (2个)
- `collect_subnet_status` - 收集 Subnet 状态和 IP 使用率
- `collect_subnet_ips` - 列出 Subnet 下的所有 IP

#### Node 工具 (6个)
- `collect_node_info` - 收集节点基本信息
- `collect_node_network_config` - 收集网络配置 (MTU, CIDR)
- `collect_node_ip_addr` - 收集 IP 地址
- `collect_node_ip_route` - 收集路由表
- `collect_node_iptables` - 收集 iptables 规则
- `collect_node_tcpdump` - 节点网卡抓包

#### Controller 日志 (6个)
- `collect_controller_logs` - kube-ovn-controller 日志
- `collect_cni_logs` - kube-ovn-cni 日志
- `collect_ovn_nb_logs` - ovn-nb 日志
- `collect_ovn_sb_logs` - ovn-sb 日志
- `collect_pinger_logs` - pinger 日志
- `collect_monitor_logs` - monitor 日志

#### OVN/OVS 诊断 (8个)
- `collect_ovn_nb_status` - OVN 北向 DB 状态
- `collect_ovn_sb_status` - OVN 南向 DB 状态
- `collect_ovs_status` - OVS 状态
- `collect_ovs_bridge_status` - OVS 桥接状态
- `collect_logical_router_status` - 逻辑路由器状态
- `collect_logical_switch_status` - 逻辑交换机状态
- `collect_loadbalancer_status` - 负载均衡器状态
- `collect_ovn_trace` - OVN 逻辑流量追踪

---

## 📚 知识库覆盖

### 数据平面知识 (Dataplane)

#### Node 通信
- **Egress NAT** - Pod 访问外部网络 (分布式 vs 集中式网关)
- **Ingress** - 外部网络访问 Pod
- **Join 网络** - Pod 访问 Kubernetes 服务

#### Pod 通信
- **同节点通信** - Same Node Pod 通信
- **跨节点 Overlay** - Geneve 隧道通信
- **跨节点 Underlay** - 物理网络直接路由
- **MTU 配置** - MTU 问题诊断
- **OVS 流表** - OpenFlow 流表分析

#### Service 通信
- **ClusterIP** - 集群内部服务访问
- **NodePort** - 节点端口访问
- **LoadBalancer** - 负载均衡器访问

### 控制平面知识 (Control Plane)

- Kube-OVN Controller 架构
- OVN NB/SB 数据库
- CRD 资源管理
- IPAM 机制

---

## 🎓 典型使用场景

### 场景 1: Pod 无法访问外部网络

```bash
./kube-ovn-checker "default命名空间的nginx Pod无法访问外部API"

# Agent 会自动:
# 1. T0 健康检查
# 2. 查看 Pod 日志
# 3. 检查 Egress NAT 配置 (iptables)
# 4. 验证 Node 网关路由
# 5. 抓包验证流量路径
# 6. 给出诊断结论
```

### 场景 2: Pod 间网络不通

```bash
./kube-ovn-checker "frontend Pod无法访问backend服务"

# Agent 会自动:
# 1. T0 健康检查
# 2. 检查 Subnet 状态
# 3. 分析 OVN 逻辑路由
# 4. ovn-trace 流量追踪
# 5. 检查 OVS 流表
# 6. 验证 Service/Endpoint
```

### 场景 3: 跨节点网络问题

```bash
./kube-ovn-checker "node1上的Pod无法ping通node2上的Pod"

# Agent 会自动:
# 1. T0 健康检查
# 2. 检查 Geneve 隧道状态
# 3. 验证节点网络配置
# 4. 检查 MTU 配置
# 5. 分析路由表
# 6. 抓包验证隧道封装
```

---
