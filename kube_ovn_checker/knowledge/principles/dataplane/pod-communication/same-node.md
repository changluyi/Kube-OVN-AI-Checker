---
# 同节点 Pod 通信场景
triggers:
  - 同节点
  - 本地通信
  - pod ping
  - 节点内pod

# 分类：Pod 间通信 - 同节点
category: pod_to_pod_same_node

# 优先级：30 (常见场景)
priority: 30
---

# 同节点 Pod 通信

## 概述

同节点 Pod 通信是指两个 Pod 运行在同一个 Kubernetes 节点上时的网络通信路径。这是最简单、性能最好的 Pod 通信方式,无需隧道封装,延迟 <1ms。

## 通信流程

```
Pod A (10.16.0.2)
  ↓ veth pair
Host vethxxx
  ↓
OVS br-int (Table 0 → 16)
  ↓ L2 转发
Host vethyyy
  ↓ veth pair
Pod B (10.16.0.3)
```

## OVS 流表关键路径

### 基本流表规则

```bash
# Table 0: 端口 ingress 分类
table=0, priority=100, ip, in_port="veth_pod_a", actions=goto_table(16)

# Table 16: L2 转发 (LS_IN_L2_LKUP)
# 直接查 MAC 表转发到目标 Pod 的 veth port
table=16, priority=50, dl_dst="aa:bb:cc:dd:ee:03", actions=output("veth_pod_b")
```

### 数据包格式

```
Ethernet Header:
  src MAC: Pod A MAC
  dst MAC: Pod B MAC

IP Header:
  src IP: 10.16.0.2
  dst IP: 10.16.0.3

Payload: Application Data
```

**特点**:
- ✅ 无隧道封装
- ✅ 使用原始 Pod IP 和 MAC
- ✅ 性能最优,延迟最低 (<1ms)
- ✅ 吞吐量接近线速

## 诊断命令

### 1. 基础连通性测试

```bash
# Pod A ping Pod B
kubectl exec -it pod-a -- ping -c 3 10.16.0.3

# 查看 Pod 路由
kubectl exec -it pod-a -- ip route
```

### 2. 查看 OVS 流表

```bash
# 查看完整流表
ovs-ofctl dump-flows br-int

# 查找特定 Pod 的流
ovs-ofctl dump-flows br-int | grep "veth_pod_a"

# 查看 Table 16 (L2 转发)
ovs-ofctl dump-flows br-int table=16
```

### 3. 查看 OVS 端口

```bash
# 查看 veth pair
ovs-vsctl list interface | grep veth

# 查看端口绑定
ovs-vsctl list port | grep pod_a
```

### 4. 验证数据包路径

```bash
# 使用 ovn-trace 追踪
kubectl-ko nbctl trace-packet --ovn ovn-default \
  'inport=="pod_a" && ip4.src==10.16.0.2 && ip4.dst==10.16.0.3'
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| `ping: timeout` | veth pair 错误 | `ip addr show vethxxx` | 重启 Pod 或 CNI |
| `network unreachable` | OVS 流表缺失 | `ovs-ofctl dump-flows br-int` | 重启 OVS |
| `permission denied` | NetworkPolicy 阻止 | `kubectl get networkpolicy` | 修改或删除 NetworkPolicy |
| 高延迟 (>5ms) | CPU 资源不足 | `top` 或 `htop` | 增加 Node 资源 |

## 性能特征

| 指标 | 典型值 |
|------|--------|
| 延迟 | <1ms |
| 吞吐量 | 10Gbps+ |
| CPU 开销 | 5-10% |

## 相关文档

- **跨节点通信**: `cross-node-overlay.md` / `cross-node-underlay.md`
- **OVS 流表详解**: `ovs-flow-tables.md`
- **MTU 配置**: `mtu-configuration.md`
