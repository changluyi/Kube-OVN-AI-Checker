---
# MTU 配置详解
triggers:
  - mtu
  - 最大传输单元
  - 分片
  - 包大小
  - packet size

# 分类：通用技术文档
category: general

# 优先级：30 (常见配置问题)
priority: 30
---

# MTU 配置详解

## 概述

MTU (Maximum Transmission Unit) 决定了网络数据包的最大尺寸。Kube-OVN 中正确配置 MTU 对避免 IP 分片、保证网络性能至关重要。

## MTU 层级关系

```
应用层数据
  ↓
Pod MTU (1400/1500)
  ↓
封装开销 (Geneve/VLAN)
  ↓
物理网卡 MTU (1500/9000)
  ↓
物理网络传输
```

## Overlay 模式 MTU

### 计算公式

```
Pod MTU = Physical MTU - Encapsulation Overhead
```

### 封装开销分解

| 协议层 | 字节数 |
|--------|--------|
| Ethernet Header | 14 |
| IP Header | 20 |
| UDP Header | 8 |
| Geneve Header | 8 |
| Geneve Options | ~50 (OVN 使用) |
| **总计** | **~100 字节** |

### 典型配置

```yaml
# 物理网络 1500 MTU
Physical MTU: 1500
Pod MTU: 1400  (1500 - 100)

# 物理网络 9000 MTU (Jumbo Frame)
Physical MTU: 9000
Pod MTU: 8900  (9000 - 100)
```

### 配置方法

```bash
# 方法 1: Subnet 配置
kubectl-ko edit subnet ovn-default
spec:
  mtu: 1400

# 方法 2: 全局配置
kubectl edit configmap kube-ovn-config -n kube-system
data:
  DEFAULT_MTU: "1400"
```

## Underlay 模式 MTU

### 无 VLAN 模式

```
Pod MTU = Physical MTU
```

**示例**:
```yaml
Physical MTU: 1500
Pod MTU: 1500  # 与物理网络一致
```

### VLAN 模式

```
Pod MTU = Physical MTU - VLAN Header (4 bytes)
```

**示例**:
```yaml
Physical MTU: 1500
Pod MTU: 1496  (1500 - 4)
```

## MTU 问题诊断

### 症状 1: 小包通,大包不通

```bash
# 测试不同包大小
kubectl exec -it pod-a -- ping -c 3 10.16.0.3        # 56 bytes, ✅
kubectl exec -it pod-a -- ping -c 3 -s 1400 10.16.0.3 # 1400 bytes, ❌
```

**原因**: MTU 配置过小或过大

**解决方案**:
```bash
# 检查 MTU
kubectl exec -it pod-a -- ip link show eth0 | grep mtu

# 调整 MTU
kubectl-ko subnet update ovn-default --mtu 1400
```

### 症状 2: 性能下降

**原因**: IP 分片导致性能下降

**解决方案**:
```bash
# 检查分片统计
tcpdump -i any -nn 'ip[6] & 0x3fff != 0'  # 捕获分片包

# 调整 MTU 避免分片
kubectl-ko subnet update ovn-default --mtu 1400
```

## 验证 MTU 配置

### 1. 检查 Pod MTU

```bash
kubectl exec -it <pod> -- ip link show eth0
# 输出: 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1400 qdisc...
```

### 2. 检查节点 MTU

```bash
# 物理网卡
ip link show eth0 | grep mtu

# OVS 网桥
ip link show br-int | grep mtu
```

### 3. MTU 路径测试

```bash
# ping 测试 (不产生分片的最大包)
kubectl exec -it pod-a -- ping -c 3 -M do -s 1472 <target-ip>

# curl 测试
kubectl exec -it pod-a -- curl -I http://<target-ip>:8080
```

## 推荐配置

### 标准网络 (1500 MTU)

| 场景 | Pod MTU | 说明 |
|------|---------|------|
| Overlay | 1400 | 考虑 Geneve 开销 |
| Underlay (无 VLAN) | 1500 | 与物理网络一致 |
| Underlay (VLAN) | 1496 | 减去 VLAN 标签 |

### Jumbo Frame (9000 MTU)

| 场景 | Pod MTU | 说明 |
|------|---------|------|
| Overlay | 8900 | 适合高性能场景 |
| Underlay (无 VLAN) | 9000 | 最大性能 |
| Underlay (VLAN) | 8996 | 减去 VLAN 标签 |

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 大包不通 | MTU 过大 | 降低 Pod MTU |
| 性能下降 | MTU 过小导致分片 | 提高 Pod MTU |
| 跨节点失败 | 物理网络 MTU 不一致 | 统一网络 MTU |
| Service 不可达 | MTU 配置错误 | 检查 MTU 匹配 |

## 性能影响

| MTU 配置 | 吞吐量 | CPU 开销 | 备注 |
|---------|--------|---------|------|
| 1400 (Overlay) | 9.5 Gbps | 18% | 标准配置 |
| 8900 (Overlay Jumbo) | 12 Gbps | 15% | 推荐 |
| 1500 (Underlay) | 11.8 Gbps | 10% | 最佳性能 |

## 配置检查清单

```bash
# ✓ 1. 检查物理网卡 MTU
ip link show eth0 | grep mtu

# ✓ 2. 检查 OVS 网桥 MTU
ip link show br-int | grep mtu

# ✓ 3. 检查 Pod MTU
kubectl exec -it <pod> -- ip link show eth0 | grep mtu

# ✓ 4. 检查 Subnet 配置
kubectl-ko get subnet <subnet-name> -o yaml | grep mtu

# ✓ 5. 测试不同包大小
kubectl exec -it <pod> -- ping -c 3 -s 1400 <target-ip>

# ✓ 6. 检查分片
tcpdump -i any -nn 'ip[6] & 0x3fff != 0'
```

## 参考资料

- [Kube-OVN MTU 配置](https://kubeovn.github.io/docs/en/latest/enhancements/jumboframe/)
- [Kubernetes Pod MTU 最佳实践](https://kubernetes.io/docs/concepts/cluster-administration/networking/)

## 相关文档

- **跨节点 Overlay**: `cross-node-overlay.md`
- **跨节点 Underlay**: `cross-node-underlay.md`
