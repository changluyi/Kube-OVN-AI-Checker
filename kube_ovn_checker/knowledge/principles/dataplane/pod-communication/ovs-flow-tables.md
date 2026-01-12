---
# OVS 流表详解
triggers:
  - 流表
  - ovs流表
  - table
  - openflow
  - pipeline

# 分类：通用技术文档
category: general

# 优先级：20 (核心技术)
priority: 20
---

# OVS 流表详解

## 概述

OVS (Open vSwitch) 使用 OpenFlow 流表规则处理数据包。Kube-OVN 基于 OVN 逻辑 pipeline 生成具体的 OVS 流表规则。

## OVS Pipeline 架构

### 流表处理流程

```
Packet Ingress
  ↓
Table 0: Ingress Port Classification
  ↓
Table 1-8: Processing (various)
  ↓
Table 9: Tunnel Handling (Overlay)
  ↓
Table 16: LS_IN_L2_LKUP (L2 Lookup)
  ↓
Table 17: LS_IN_L3_FORWARDING (L3 Forwarding)
  ↓
Table 18: LS_IN_STATEFUL (Stateful Processing)
  ↓
Table 19-64: Additional Processing
  ↓
Packet Egress
```

## 核心表号说明

| Table 号 | OVN 逻辑表 | 作用 | 常见操作 |
|---------|-----------|------|---------|
| **0** | Ingress | 端口分类,基础过滤 | `goto_table(16)` |
| **9** | Tunnel Handling | 隧道入口处理 (Overlay) | `goto_table(16)` |
| **16** | LS_IN_L2_LKUP | L2 查找 (MAC 学习) | `set_field:xx->eth_dst` |
| **17** | LS_IN_L3_FORWARDING | L3 路由 (IP 转发) | `goto_table(18)` |
| **18** | LS_IN_STATEFUL | 隧道封装,连接跟踪 | `set_field:xx->tun_dst` |

## 流表规则结构

### 基本语法

```bash
table=<table_id>, priority=<priority>, <match_conditions>, actions=<actions>
```

### 匹配条件 (Match)

| 字段 | 说明 | 示例 |
|------|------|------|
| `ip` | IP 协议 | `ip` |
| `in_port` | 入端口 | `in_port="veth_pod_a"` |
| `nw_src` | 源 IP | `nw_src=10.16.0.2` |
| `nw_dst` | 目标 IP | `nw_dst=10.16.1.3` |
| `dl_src` | 源 MAC | `dl_src=aa:bb:cc:dd:ee:02` |
| `dl_dst` | 目标 MAC | `dl_dst=aa:bb:cc:dd:ee:03` |
| `tun_src` | 隧道源 IP (Overlay) | `tun_src=192.168.1.10` |
| `tun_id` | VNI (Overlay) | `tun_id=0x1` |
| `dl_vlan` | VLAN ID (Underlay) | `dl_vlan=100` |

### 动作 (Actions)

| 动作 | 说明 | 示例 |
|------|------|------|
| `output` | 输出到端口 | `output:"veth_pod_b"` |
| `goto_table` | 跳转到表 | `goto_table(18)` |
| `set_field` | 设置字段 | `set_field:aa:bb:cc:dd:ee:03->eth_dst` |
| `drop` | 丢弃数据包 | `actions=drop` |
| `mod_vlan_vid` | 修改 VLAN ID | `mod_vlan_vid:100` |
| `strip_vlan` | 去除 VLAN | `strip_vlan` |

## 关键流表示例

### 1. 同节点 Pod 通信

```bash
# Table 0: 端口 ingress
table=0, priority=100, ip, in_port="veth_pod_a",
       actions=goto_table(16)

# Table 16: L2 转发
table=16, priority=50, dl_dst=aa:bb:cc:dd:ee:03,
       actions=output("veth_pod_b")
```

### 2. 跨节点 Overlay

```bash
# 源节点 - Table 18: 隧道封装
table=18, priority=100, ip,
       actions=set_field:192.168.1.11->tun_dst,
                set_field:0x1->tun_id,
                output:"genev_sys_6081"

# 目标节点 - Table 0: 隧道解封装
table=0, priority=100, tun_src=192.168.1.10,
       actions=goto_table(9)
```

### 3. 跨节点 Underlay

```bash
# Table 17: 直接路由
table=17, priority=100, ip,
       actions=mod_dl_dst:bb:cc:dd:ee:ff,
                output:"eth0"
```

## 诊断命令

### 查看流表

```bash
# 查看所有流表
ovs-ofctl dump-flows br-int

# 查看特定表
ovs-ofctl dump-flows br-int table=16

# 查看特定端口的流
ovs-ofctl dump-flows br-int | grep "veth_pod_a"

# 查找隧道相关流
ovs-ofctl dump-flows br-int | grep -i "tun_dst\|tun_id"

# 统计流表数量
ovs-ofctl dump-flows br-int | wc -l
```

### 监控流表命中

```bash
# 查看流表统计
ovs-ofctl dump-flows br-int -m | grep -v "n_packets=0"

# 持续监控
watch -n 1 'ovs-ofctl dump-flows br-int -m | grep "veth_pod_a"'
```

### 追踪数据包

```bash
# 使用 ovn-trace (推荐)
kubectl-ko nbctl trace-packet --ovn ovn-default \
  'inport=="pod_a" && ip4.src==10.16.0.2 && ip4.dst==10.16.1.3'

# 使用 ovs-appctl
ovs-appctl ofproto/trace br-int \
  "in_port=veth_pod_a,ip,nw_src=10.16.0.2,nw_dst=10.16.1.3"
```

## 流表调优

### 流表数量控制

| 指标 | 建议值 | 说明 |
|------|--------|------|
| 总流表数 | < 10000 | 避免流表爆炸 |
| 单 Pod 流表数 | < 50 | 减少规则数量 |
| 优先级层级 | < 10 | 简化优先级 |

### 常见优化

```bash
# 1. 清理未使用的流表
ovs-ofctl del-flows br-int

# 2. 重新生成流表 (重启 OVS)
systemctl restart openvswitch

# 3. 调整流表超时
ovs-vsctl set Open_vSwitch . other_config:max-idle=300000
```

## 常见问题

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 流表缺失 | OVN 同步失败 | 重启 kube-ovn-controller |
| 流表不生效 | 优先级冲突 | 调整规则优先级 |
| 性能下降 | 流表过多 | 优化 Subnet 配置 |
| 数据包丢包 | `actions=drop` 规则 | 检查 NetworkPolicy |

## 参考资料

- [OVN Pipeline 文档](https://docs.ovn.org/en/latest/ref/pipeline.html)
- [OVS OpenFlow 参考](https://docs.openvswitch.org/en/latest/ref/ovs-ofctl.8/)

## 相关文档

- **同节点通信**: `same-node.md`
- **跨节点 Overlay**: `cross-node-overlay.md`
- **跨节点 Underlay**: `cross-node-underlay.md`
