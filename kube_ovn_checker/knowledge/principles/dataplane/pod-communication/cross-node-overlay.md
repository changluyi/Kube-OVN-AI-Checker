---
# 跨节点 Pod 通信 - Overlay 模式
triggers:
  - 跨节点
  - overlay
  - geneve
  - 隧道
  - pod间通信

# 分类：Pod 间通信 - 跨节点 Overlay
category: pod_to_pod_cross_node

# 优先级：30 (常见场景)
priority: 30
---

# 跨节点 Pod 通信 (Overlay 模式)

## 概述

跨节点 Pod 通信 (Overlay 模式) 使用 Geneve 隧道封装,实现不同节点上的 Pod 互通。这是 Kube-OVN 的默认网络模式。

## 通信流程

```
Pod A (Node1, 10.16.0.2)
  ↓
OVS Node1
  ↓ 封装 Geneve
Geneve Tunnel (Node1 IP → Node2 IP)
  ↓
OVS Node2
  ↓ 解封装 Geneve
Pod B (Node2, 10.16.1.3)
```

## Geneve 封装格式

### 外层数据包 (物理网络)

```
┌─────────────────────────────────┐
│ Ethernet Header                  │
│  src: Node1 MAC                  │
│  dst: Node2 MAC                  │
├─────────────────────────────────┤
│ IP Header                        │
│  src: 192.168.1.10 (Node1)       │
│  dst: 192.168.1.11 (Node2)       │
├─────────────────────────────────┤
│ UDP Header                       │
│  dst port: 6081 (Geneve)         │
├─────────────────────────────────┤
│ Geneve Header (VNI: 0x1)         │
├─────────────────────────────────┤
│ Inner Ethernet (Pod A → Pod B)   │
│ Inner IP (10.16.0.2 → 10.16.1.3) │
└─────────────────────────────────┘
```

## OVS 流表关键路径

### 源节点 (Node1) - Pod A 出口

```bash
# Table 0: 端口 ingress 分类
table=0, priority=100, ip, in_port="veth_pod_a", actions=goto_table(16)

# Table 16: 逻辑网络处理 (LS_IN_L2_LKUP)
table=16, priority=50, ip, nw_dst=10.16.1.3,
       actions=set_field:aa:bb:cc:dd:ee:03->eth_dst,
                goto_table(17)

# Table 17: 逻辑路由处理 (LS_IN_L3_FORWARDING)
table=17, priority=50, ip,
       actions=goto_table(18)

# Table 18: 隧道封装 (LS_IN_STATEFUL)
table=18, priority=100, ip,
       actions=set_field:192.168.1.11->tun_dst,    # Node2 IP
                set_field:0x1->tun_id,             # VNI
                output:"genev_sys_6081"
```

### 目标节点 (Node2) - Pod B 入口

```bash
# Table 0: 隧道入口解封装
table=0, priority=100, tun_src=192.168.1.10,
       actions=goto_table(9)

# Table 9: 隧道处理后
table=9, priority=100, ip,
       actions=goto_table(16)

# Table 16: 逻辑网络查找目标端口 (LS_IN_L2_LKUP)
table=16, priority=50, ip, nw_dst=10.16.1.3,
       actions=output("veth_pod_b")
```

## 关键字段说明

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `tun_dst` | 隧道目标 IP (对端节点 IP) | `192.168.1.11` |
| `tun_id` | 虚拟网络标识 (VNI) | `0x1` |
| `genev_sys_6081` | Geneve 隧道端口 | `genev_sys_6081` |

## 诊断命令

### 1. 检查隧道状态

```bash
# 查看 Geneve 隧道端口
ovs-vsctl list interface | grep -A 5 geneve

# 检查隧道是否 UP
ovs-vsctl get interface genev_sys_6081 link_state
```

### 2. 查看隧道流表

```bash
# 查找隧道相关的流
ovs-ofctl dump-flows br-int | grep -i "tun_dst\|tun_id\|genev"

# 查看 Table 18 (隧道封装)
ovs-ofctl dump-flows br-int table=18
```

### 3. 验证连通性

```bash
# Pod A ping Pod B (跨节点)
kubectl exec -it pod-a -- ping -c 3 10.16.1.3

# 抓包查看 Geneve 封装
tcpdump -i any port 6081 -nn
```

### 4. 追踪数据包路径

```bash
# 使用 ovn-trace
kubectl-ko nbctl trace-packet --ovn ovn-default \
  'inport=="pod_a" && ip4.src==10.16.0.2 && ip4.dst==10.16.1.3'
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| `ping: timeout` | Geneve 隧道断开 | `ovs-vsctl list interface \| grep geneve` | 重启 OVS |
| `no route to host` | 防火墙阻止 UDP 6081 | `iptables -L -n \| grep 6081` | 开放端口 |
| MTU 问题 | 大包分片 | `ping -s 1400 <target>` | 调整 MTU |
| 高延迟 (>10ms) | 隧道性能问题 | `ovs-vsctl get interface genev_sys_6081 statistics` | 检查 CPU |

## 性能特征

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 延迟 | 1-3ms | 隧道封装/解封装开销 |
| 吞吐量 | 10Gbps+ | 现代服务器 CPU |
| CPU 开销 | 10-20% | 取决于流量 |

## MTU 配置

Pod MTU 需要考虑 Geneve 封装开销 (~100 字节):

```bash
# 典型配置
Physical MTU: 1500
Pod MTU: 1400 (1500 - 100)
```

详见: `mtu-configuration.md`

## 端口和协议

| 用途 | 协议 | 端口 | 说明 |
|------|------|------|------|
| Geneve 隧道 | UDP | 6081 | 跨节点封装 |

## 相关文档

- **Underlay 模式**: `cross-node-underlay.md`
- **OVS 流表详解**: `ovs-flow-tables.md`
- **MTU 配置**: `mtu-configuration.md`
