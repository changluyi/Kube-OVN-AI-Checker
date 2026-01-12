---
# Egress NAT (Pod 访问外部网络)
triggers:
  - egress
  - nat
  - 出网
  - 外部访问
  - snat

# 分类：Pod 到外部网络通信
category: pod_to_external

# 优先级：30 (常见场景)
priority: 30
---

# Egress NAT (Pod 访问外部网络)

## 概述

Egress NAT 允许 Pod 访问集群外部网络。Kube-OVN 支持两种 NAT 模式:

### 关键区别

**重要**: 两种模式的 Egress NAT **都由 Node iptables MASQUERADE 实现**，与 OVN NAT (`lr-nat-list`) **无关**！

| 模式 | NAT 实现位置 | 哪些 Node 有 iptables 规则 | 说明 |
|------|------------|---------------------------|------|
| **分布式网关** | Node iptables | **所有 Node** | 每个 Node 的 iptables 都添加 MASQUERADE 规则 |
| **集中式网关** | Node iptables | **仅 activeNode** | 只有 Subnet 的 `activeNode` (Gateway Node) 有 MASQUERADE 规则 |

**核心机制**:
- ❌ **不使用** OVN NAT (`lr-nat-list` 不包含 Egress 规则)
- ✅ NAT 由 **Node iptables POSTROUTING** 链的 `MASQUERADE` 规则实现
- ✅ Kube-OVN Controller 根据 Subnet 的 `status.activeNode` 动态配置 iptables

## 架构设计

### 流量路径对比

#### 分布式网关 (Distributed Gateway)

**核心机制**: NAT 完全由 **Node iptables** 实现，OVN 内部**没有任何 NAT 配置**。

```
Pod (10.16.0.2)
  ↓ 发送到 8.8.8.8:53 (外部 IP)
本地 Node OVS (br-int)
  ↓ 路由到 Node 管理口 (ovs0/eth0)
Node iptables (POSTROUTING 链)
  ↓ MASQUERADE: 10.16.0.2 → 192.168.1.10
Node 管理口 (eth0)
  ↓ 发送到外部网络
External Network (Internet)
```

**数据包变换**:
```
原始包 (进入 OVS):
  src IP: 10.16.0.2 (Pod IP)
  dst IP: 8.8.8.8

经过 Node iptables MASQUERADE 后:
  src IP: 192.168.1.10 (Node IP)  ← iptables 修改
  dst IP: 8.8.8.8
```

**关键点**:
- ❌ OVN `lr-nat-list` **为空** (没有任何 Egress NAT 规则)
- ✅ NAT 由 **Node iptables** 的 `POSTROUTING` 链处理
- ✅ 流量路径: `Pod → OVS → Node 网络栈 → iptables → 外部`
- ✅ 所有 Node 都有相同的 iptables MASQUERADE 规则

#### 集中式网关 (Centralized Gateway)

**核心机制**: NAT 由 **activeNode (Gateway Node) 的 iptables** 实现，其他 Node 没有 MASQUERADE 规则。

```
Pod (10.16.0.2) 在 Node A
  ↓ 发送到 8.8.8.8
Node A OVS
  ↓ 隧道封装 (Geneve) 发送到 activeNode (Node B)
Node B (activeNode) OVS
  ↓ 路由到 Node B 网络栈
Node B iptables (POSTROUTING 链)
  ↓ MASQUERADE: 10.16.0.2 → 192.168.1.11 (Node B IP)
Node B 物理网卡
  ↓ 发送到外部网络
External Network
```

**数据包变换**:
```
原始包 (在 Node A):
  src IP: 10.16.0.2 (Pod IP)
  dst IP: 8.8.8.8

经过 Node B (activeNode) iptables MASQUERADE 后:
  src IP: 192.168.1.11 (activeNode IP)  ← iptables 修改
  dst IP: 8.8.8.8
```

**关键点**:
- ❌ OVN `lr-nat-list` **不包含** Egress SNAT 规则
- ✅ NAT 由 **activeNode 的 iptables** 处理
- ✅ 只有 Subnet 的 `status.activeNode` 有 MASQUERADE 规则
- ✅ 通过**策略路由**将 Pod 流量引导到 activeNode
- ✅ 流量路径: `Pod → OVS → 策略路由 → 隧道 → activeNode → iptables MASQUERADE → 外部`

**activeNode 选择与策略路由**:
```bash
# 1. 查看 Subnet 的 activeNode
kubectl-ko get subnet ovn-default -o jsonpath='{.status.activeNode}'
# 输出: node1  (Gateway Node)

# 2. 只有 activeNode (node1) 上有 iptables MASQUERADE 规则
ssh node1 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0

# 3. 非活跃 Node 上没有该 Subnet 的 MASQUERADE 规则
ssh node2 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# (无输出)

# 4. OVN 逻辑路由策略确保 Pod 流量转发到 activeNode
kubectl-ko nbctl lr-policy-list ovn-cluster
# 输出示例 (集中式网关):
# 10001 (ip4.src == 10.16.0.0/16) -> allow-stateless (转发到 activeNode)
```

## NAT 模式对比

### 分布式网关 (推荐)

**NAT 实现**: 完全由 **Node iptables** 实现，**不使用** OVN NAT。

```yaml
# Subnet 配置
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default
spec:
  cidr: 10.16.0.0/16
  gateway: 10.16.0.1
  gatewayType: distributed   # 分布式网关
```

**NAT 行为**:
- ❌ **不使用** OVN NAT (执行 `kubectl-ko nbctl lr-nat-list` 看不到 Egress 规则)
- ✅ NAT 由 **所有 Node 的 iptables** 实现
- ✅ 每个 Node 独立处理本地 Pod 的 Egress 流量
- ✅ 所有 Node 的 iptables 规则相同

**Node iptables 规则示例**:
```bash
# 在任意 Node 上查看 NAT 规则 (所有 Node 都有)
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0

# Kube-OVN 会自动添加类似规则:
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0

# 在 node1, node2, node3... 所有 Node 上都能看到这条规则
```

**特点**:
- ✅ 性能好 (本地 iptables 处理，无隧道开销)
- ✅ 高可用 (每个 Node 独立，无单点)
- ✅ 扩展性好 (水平扩展)
- ✅ 简单 (依赖标准 Linux iptables)

### 集中式网关

**NAT 实现**: 由 **OVN Logical Router** 实现，`lr-nat-list` 包含 SNAT 规则。

```yaml
# Subnet 配置
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default
spec:
  cidr: 10.16.0.0/16
  gateway: 10.16.0.1
  natOutgoing: true          # 必须启用,否则无法访问外部
  gatewayType: centralized   # 集中式网关
  gatewayNode: "node1"       # 指定网关节点
```

**NAT 行为**:
- ❌ **不使用** OVN NAT (执行 `kubectl-ko nbctl lr-nat-list` **看不到** Egress SNAT 规则)
- ✅ NAT 由 **activeNode 的 iptables** 实现 (其他 Node 没有)
- ✅ 通过策略路由确保 Pod 流量到达 activeNode
- ⚠️ 所有 Egress 流量必须经过 activeNode

**Node iptables 规则对比**:
```bash
# 1. 在 activeNode (node1) 上查看 - 有 MASQUERADE 规则
ssh node1 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0

# 2. 在其他 Node (node2) 上查看 - 没有该 Subnet 的规则
ssh node2 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# (无输出)

# 3. OVN NAT 不包含 Egress 规则
kubectl-ko nbctl lr-nat-list ovn-cluster
# (无 Egress SNAT 规则, 可能只有 DNAT 规则)
```

**特点**:
- ✅ 统一管理 (只有 activeNode 处理 NAT)
- ✅ 保证源 IP 统一 (都是 activeNode IP)
- ❌ 性能较差 (需要隧道 + 策略路由开销)
- ❌ 单点故障 (activeNode 故障需要切换)
- ❌ 扩展性差 (activeNode 成为瓶颈)

## OVS 流表关键路径

### 分布式网关流表

**重要**: 两种模式都 **没有 NAT 相关的 OVS 流表**，NAT 完全由 iptables 处理。

```bash
# OVS 流表只负责路由，不做 NAT
# Table 18: 路由到 Node 管理口 (不修改源 IP)
table=18, priority=50, ip, nw_dst=8.8.8.8,
       actions=output("eth0")  # 或 ovs0/ens192

# NAT 由 Node iptables 处理:
sudo iptables -t nat -L POSTROUTING -n -v
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0
```

**验证**:
```bash
# 1. 查看 OVS 流表 - 没有 NAT 相关的流
ovs-ofctl dump-flows br-int | grep "mod_nw_src\|set_field.*nw_src"
# (无输出)

# 2. 查看 OVN NAT - 不包含 Egress SNAT
kubectl-ko nbctl lr-nat-list ovn-cluster
# (无 Egress SNAT 规则)

# 3. 查看 Node iptables - 有 NAT 规则
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0
```

### 集中式网关流表与策略路由

集中式网关通过 **OVN 逻辑路由策略 + 隧道** 将流量引导到 activeNode，然后由 activeNode 的 iptables 处理 NAT。

```bash
# ====== 非 activeNode ======
# OVN 逻辑路由策略匹配 Pod IP，引导到 activeNode
kubectl-ko nbctl lr-policy-list ovn-cluster
# 10001 (ip4.src == 10.16.0.0/16) -> 转发到 activeNode

# OVS 流表: 隧道封装到 activeNode
table=18, priority=100, ip, nw_dst=8.8.8.8,
       actions=set_field:192.168.1.11->tun_dst,    # activeNode IP
                set_field:0x1->tun_id,
                output:"genev_sys_6081"

# ====== activeNode ======
# 接收隧道流量，路由到本地网络栈
table=18, priority=50, ip, nw_dst=8.8.8.8,
       actions=output("eth0")

# NAT 由 activeNode 的 iptables 处理:
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0
```

**关键区别**:
- **分布式网关**: OVN 策略路由匹配 Pod IP，直接路由到本地 Node 网络栈
- **集中式网关**: OVN 策略路由匹配 Pod IP，通过隧道转发到 activeNode

## NAT 规则查看

### 查看 Node iptables NAT (两种模式都使用)

**重要**: 两种模式的 Egress NAT **都由 Node iptables MASQUERADE 实现**！

```bash
# 查看 Node 的 POSTROUTING 规则
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0

# 分布式网关 - 所有 Node 都有:
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0

# 集中式网关 - 只有 activeNode 有:
ssh node1 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# MASQUERADE  all  --  10.16.0.0/16  0.0.0.0/0

ssh node2 "sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0"
# (无输出)
```

### 查看 OVN NAT 规则 (不包含 Egress SNAT)

**关键**: OVN NAT (`lr-nat-list`) **不包含** Egress SNAT 规则，可能只有 DNAT 规则 (用于 NodePort/LoadBalancer)。

```bash
# 查看 OVN NAT 规则
kubectl-ko nbctl lr-nat-list ovn-cluster

# 两种模式都不包含 Egress SNAT:
# (可能只有 DNAT 规则, 用于 Service)
# TYPE         EXTERNAL_IP        LOGICAL_IP            EXTERNAL_PORT
# dnat_and_snat  192.168.1.100      10.16.0.5             tcp=80
```

### 查看 OVN 逻辑路由策略 (区分流量路径)

```bash
# 查看 OVN 逻辑路由策略
kubectl-ko nbctl lr-policy-list ovn-cluster

# 分布式网关 - 策略直接路由到本地:
# (可能没有特殊策略)

# 集中式网关 - 策略引导到 activeNode:
# 10001 (ip4.src == 10.16.0.0/16) -> 允许并转发到 activeNode
```

### NAT 类型说明

| 类型 | 说明 | 使用场景 | 验证方法 |
|------|------|---------|---------|
| **Node iptables MASQUERADE** | Egress SNAT (主要) | **两种模式都使用** | `sudo iptables -t nat -L POSTROUTING` |
| **OVN 逻辑路由策略** | 流量路径引导 | 集中式网关 | `kubectl-ko nbctl lr-policy-list` |
| **OVN NAT DNAT** | Service 入网 | NodePort/LoadBalancer | `kubectl-ko nbctl lr-nat-list` |

## 诊断命令

### 1. 区分网关模式

```bash
# 查看 Subnet 的网关类型
kubectl-ko describe subnet ovn-default | grep gatewayType

# 输出示例:
# gatewayType: distributed    # 分布式网关
# 或
# gatewayType: centralized    # 集中式网关
```

### 2. NAT 规则检查

#### 集中式网关

```bash
# 查看 OVN NAT 规则 (应该有 SNAT)
kubectl-ko nbctl lr-nat-list ovn-cluster

# 查看 Subnet NAT 配置
kubectl-ko describe subnet ovn-default | grep natOutgoing
```

#### 分布式网关

```bash
# 查看 Node iptables NAT 规则
sudo iptables -t nat -L POSTROUTING -n -v | grep 10.16.0

# 检查是否有 MASQUERADE 规则
```

### 3. Gateway 配置检查

```bash
# 查看网关节点
kubectl get nodes -l kube-ovn/role=gateway

# 查看所有 Subnet
kubectl-ko get subnet
```

### 4. 流表检查

#### 集中式网关

```bash
# 查看 Gateway Node 的 NAT 流表
ovs-ofctl dump-flows br-int | grep "mod_nw_src\|set_field.*nw_src"

# 查看 OVN Logical Router NAT
kubectl-ko nbctl lr-nat-list ovn-cluster
```

#### 分布式网关

```bash
# 查看路由流表 (应该直接输出到物理网卡)
ovs-ofctl dump-flows br-int table=18

# 检查是否有到外部 IP 的路由流
```

### 5. 连通性测试

```bash
# Pod 访问外部网络
kubectl exec -it <pod> -- curl -I http://example.com

# Pod DNS 解析
kubectl exec -it <pod> -- nslookup google.com

# Ping 外部 IP
kubectl exec -it <pod> -- ping -c 3 8.8.8.8
```

### 6. 抓包验证 NAT

#### 集中式网关

```bash
# 在 Gateway Node 上抓包,应该看到 SNAT 后的源 IP
tcpdump -i eth0 -nn host 8.8.8.8

# 应该看到:
# IP 192.168.1.11 > 8.8.8.8  (Gateway Node IP,不是 Pod IP)
```

#### 分布式网关

```bash
# 在本地 Node 上抓包
tcpdump -i eth0 -nn host 8.8.8.8

# 可能看到:
# IP 10.16.0.2 > 8.8.8.8      (保持 Pod IP,如果网络可路由)
# 或
# IP 192.168.1.10 > 8.8.8.8   (Node IP,如果有 iptables MASQUERADE)
```

## 常见问题

### 集中式网关常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| `no route to host` | OVN NAT 规则未配置 | `kubectl-ko nbctl lr-nat-list` | 检查 `natOutgoing: true` |
| 无法访问外部 | Gateway 不可达 | `kubectl get nodes -l kube-ovn/role=gateway` | 检查 Gateway 状态 |
| 源 IP 不对 | SNAT IP 错误 | `tcpdump -i eth0 -nn` (Gateway Node) | 修正 SNAT IP |
| 隧道不通 | Geneve 隧道问题 | `ovs-vsctl show` | 检查隧道配置 |

### 分布式网关常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| Pod IP 无法访问外部 | 物理网络不可路由 Pod IP | `ip route get 8.8.8.8` | 配置 iptables MASQUERADE |
| 源 IP 是 Pod IP | 无 SNAT,这是正常的 | `tcpdump -i eth0 -nn` | 如需统一 IP,配置 MASQUERADE |
| 部分节点可访问,部分不可 | 部分节点路由配置问题 | 在各 Node 上检查 `ip route` | 统一 Node 路由配置 |
| 无法跨网段访问 | 缺少默认路由 | `ip route` | 添加默认网关 |

## 配置示例

### 集中式网关配置 (需要 OVN NAT)

```yaml
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default-centralized
spec:
  cidr: 10.16.0.0/16
  gateway: 10.16.0.1
  natOutgoing: true                    # 必须启用
  gatewayType: centralized             # 集中式网关
  gatewayNode: "node1"                 # 指定 Gateway Node
```

**验证**:
```bash
# 应该看到 OVN NAT 规则
kubectl-ko nbctl lr-nat-list ovn-cluster
# TYPE         EXTERNAL_IP        LOGICAL_IP
# snat         192.168.1.11        10.16.0.0/16
```

### 分布式网关配置 (可选 iptables NAT)

```yaml
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default-distributed
spec:
  cidr: 10.16.0.0/16
  gateway: 10.16.0.1
  gatewayType: distributed             # 分布式网关
  # natOutgoing 不影响 Egress 流量
```

**如果需要 NAT (Pod IP 是私有 IP)**:
```bash
# 在每个 Node 上配置 iptables MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 10.16.0.0/16 -o eth0 -j MASQUERADE

# 或使用 iptables-persistent 持久化
sudo apt-get install iptables-persistent
sudo netfilter-persistent save
```

### Underlay 网络 (不需要 NAT)

```yaml
# 如果使用物理网络 IP (Underlay),不需要 NAT
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: underlay-subnet
spec:
  cidr: 192.168.1.0/24                # 物理网络可路由的 IP
  gateway: 192.168.1.1
  gatewayType: distributed
  natOutgoing: false                   # 禁用 OVN NAT
  # Pod IP 可以直接路由,无需 SNAT
```

## 性能特征

| 指标 | 分布式 SNAT | 集中式 SNAT |
|------|-----------|-----------|
| 延迟 | 5-10ms | 10-20ms |
| 吞吐量 | 所有节点总和 | Gateway 限制 |
| CPU 开销 | 10-20% | 15-30% (Gateway) |
| 扩展性 | 高 (水平扩展) | 低 (Gateway 瓶颈) |

## NAT 与 iptables

### Kube-OVN vs 传统 kube-proxy

| 特性 | kube-proxy (iptables) | Kube-OVN (OVS) |
|------|----------------------|----------------|
| NAT 位置 | Node iptables | OVS 流表 |
| 性能 | 中等 | 高 |
| 更新延迟 | 秒级 | 毫秒级 |
| 同步开销 | 高 (全量) | 低 (增量) |

### 优点

- ✅ **性能更好**: OVS 流表比 iptables 快
- ✅ **更新更快**: 增量更新 vs 全量更新
- ✅ **集中管理**: OVN 统一管理 NAT 规则

## 相关文档

- **Join 网络**: `join-network.md`
- **Ingress**: `ingress.md`
- **外部访问对比**: `comparison-table.md`
