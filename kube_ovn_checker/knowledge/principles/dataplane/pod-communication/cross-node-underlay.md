---
# 跨节点 Pod 通信 - Underlay 模式
triggers:
  - 跨节点
  - underlay
  - vlan
  - 物理网络
  - 路由模式

# 分类：Pod 间通信 - 跨节点 Underlay
category: pod_to_pod_cross_node

# 优先级：40 (较少使用)
priority: 40
---

# 跨节点 Pod 通信 (Underlay 模式)

## 概述

跨节点 Pod 通信 (Underlay 模式) 直接使用物理网络路由,无需隧道封装。Pod IP 在物理网络中可直接路由,性能最优但需要物理网络设备支持。

## 通信流程

```
Pod A (Node1, 192.168.1.20)
  ↓
OVS Node1
  ↓ 直接路由 (无封装)
Physical Network (L2/L3)
  ↓
OVS Node2
  ↓ 直接路由
Pod B (Node2, 192.168.1.21)
```

## 数据包格式

### 简单模式 (无 VLAN)

```
Ethernet Header:
  src MAC: Pod A MAC
  dst MAC: Gateway MAC

IP Header:
  src IP: 192.168.1.20 (Pod A)
  dst IP: 192.168.1.21 (Pod B)

Payload: Application Data
```

### VLAN 模式

```
Ethernet Header:
  src MAC: Pod A MAC
  dst MAC: Gateway MAC
  VLAN Tag: 100

IP Header:
  src IP: 192.168.1.20
  dst IP: 192.168.1.21

Payload: Application Data
```

**特点**:
- ✅ 无隧道封装开销
- ✅ 单层 MAC (物理)
- ✅ 性能最优,延迟最低 (<1ms)
- ✅ 需要物理网络支持 Pod IP 路由

## OVS 流表关键路径

### 节点流表 (路由模式)

```bash
# Table 0: 物理网卡 ingress
table=0, priority=100, ip, in_port="br-phy", actions=goto_table(16)

# Table 16: L3 路由查找
table=16, priority=50, ip, nw_dst=192.168.1.21,
       actions=goto_table(17)

# Table 17: 直接转发到物理网络
table=17, priority=100, ip,
       actions=mod_dl_dst:bb:cc:dd:ee:ff,  # 目标网关 MAC
                output:"eth0"               # 物理网卡

# 反向流表 (物理网络到 Pod)
table=0, priority=100, ip, in_port="eth0", dl_dst="aa:bb:cc:dd:ee:ff",
       actions=goto_table(16)

table=16, priority=50, ip, nw_dst=192.168.1.20,
       actions=output("veth_pod_a")
```

### VLAN 模式流表

```bash
# Table 0: 物理网卡 ingress
table=0, priority=100, ip, in_port="br-phy", actions=goto_table(16)

# Table 16: VLAN 处理
table=16, priority=100, dl_vlan=100,
       actions=strip_vlan, goto_table(17)

# Table 17: 直接转发
table=17, priority=50, ip, nw_dst=192.168.1.21,
       actions=output("veth_pod_b")

# 反向流表 (Pod 到物理网络)
table=0, priority=100, ip, in_port="veth_pod_a",
       actions=set_field:100->vlan_tag,
                push_vlan:100,
                output:"br-phy"
```

## 关键字段说明

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `mod_dl_dst` | 修改目标 MAC 为网关 MAC | `bb:cc:dd:ee:ff` |
| `vlan_tag` | VLAN 标签 | `100` |
| `br-phy` | 物理网桥端口 | `br-phy` |

## 诊断命令

### 1. 检查物理网络配置

```bash
# 查看物理网卡绑定
ovs-vsctl list interface | grep -A 5 "eth0\|br-phy"

# 查看 VLAN 配置
ovs-vsctl list port | grep -i vlan
```

### 2. 查看路由流表

```bash
# 查找物理网络相关的流
ovs-ofctl dump-flows br-int | grep -i "br-phy\|eth0"

# 查看 Table 17 (路由转发)
ovs-ofctl dump-flows br-int table=17
```

### 3. 验证连通性

```bash
# Pod A ping Pod B (跨节点,物理 IP)
kubectl exec -it pod-a -- ping -c 3 192.168.1.21

# 查看路由表
kubectl exec -it pod-a -- ip route
```

### 4. 检查 ARP

```bash
# 查看 Pod 的 ARP 表
kubectl exec -it pod-a -- ip neigh

# 抓包查看 ARP
tcpdump -i any -nn -e arp
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| `ping: timeout` | 物理网络不可达 | `ping <gateway>` | 检查物理连接 |
| `no route to host` | 缺少路由 | `ip route` | 添加默认路由 |
| ARP 失败 | VLAN 配置错误 | `ovs-vsctl list port` | 修正 VLAN ID |
| `network unreachable` | 物理网络未配置 | `ip addr show br-phy` | 配置桥接网络 |

## 性能特征

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 延迟 | <1ms | 无封装开销 |
| 吞吐量 | 10Gbps+ | 接近物理网络极限 |
| CPU 开销 | 5-10% | 仅 L2/L3 转发 |

## MTU 配置

Underlay 模式 MTU 配置:

```bash
# 无 VLAN 模式
Physical MTU: 1500
Pod MTU: 1500 (与物理网络一致)

# VLAN 模式
Physical MTU: 1500
Pod MTU: 1496 (1500 - 4 字节 VLAN 标签)
```

详见: `mtu-configuration.md`

## 配置要求

### 网络设备

| 组件 | 要求 |
|------|------|
| 物理交换机 | 支持 VLAN 或 Pod IP 路由 |
| 路由器 | 支持 Pod 网段路由 |
| 网关 | 配置 ARP 代理 (可选) |

### Subnet 配置

```yaml
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: underlay-subnet
spec:
  cidr: 192.168.1.0/24
  gateway: 192.168.1.1
  vlan: 100                    # VLAN ID (可选)
  gatewayType: distributed      # 分布式网关
  natOutgoing: false           # 不使用 NAT
```

## 与 Overlay 对比

| 特性 | Overlay | Underlay |
|------|---------|----------|
| **封装** | Geneve 隧道 | 无封装 |
| **流表路径** | Table 0→16→17→18 | Table 0→16→17 |
| **MAC 地址** | 内外两层 | 单层 (物理) |
| **路由方式** | 逻辑路由 (OVN) | 物理路由 |
| **性能** | 有封装开销 | 无封装开销 |
| **网络要求** | 任意 IP 网络 | 需要物理网络支持 Pod IP |

## 相关文档

- **Overlay 模式**: `cross-node-overlay.md`
- **OVS 流表详解**: `ovs-flow-tables.md`
- **MTU 配置**: `mtu-configuration.md`
