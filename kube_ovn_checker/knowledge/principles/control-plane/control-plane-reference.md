# Kube-OVN 核心概念速查表

> 本文档提供 Kube-OVN 控制平面的核心概念、数据结构映射和常用命令的快速参考。

## 目录

- [概念映射表](#概念映射表)
- [数据结构映射](#数据结构映射)
- [生命周期状态](#生命周期状态)
- [常用诊断命令](#常用诊断命令)
- [配置参数速查](#配置参数速查)
- [错误代码速查](#错误代码速查)

---

## 概念映射表

### Kubernetes → OVN 概念映射

| Kubernetes 概念 | OVN 概念 | 映射规则 |
|----------------|---------|---------|
| **Pod** | Logical Switch Port | `<pod-name>_<namespace>` |
| **Subnet** | Logical Switch | Subnet.metadata.name |
| **VPC** | Logical Router | `<vpc-name>-lr` |
| **NetworkPolicy** | ACL | `np-<policy-name>-<uid>` |
| **Service (ClusterIP)** | Load Balancer | `<namespace>_<service-name>` |
| **Service (NodePort)** | Load Balancer + NAT | `<namespace>_<service-name>-np` |
| **Node** | Logical Switch | `join` (默认) |
| **IPAM** | Logical Switch Port addresses | `addresses: "<mac> <ip>"` |
| **Gateway** | Logical Router Port | `<subnet>-lrp` |

### 网络类型对比

| 网络类型 | tunnelType | MTU | 适用场景 | 性能 |
|---------|-----------|-----|---------|------|
| **Overlay (Geneve)** | geneve | 1400 | 虚拟化环境、云平台 | 中等 |
| **Overlay (VXLAN)** | vxlan | 1450 | 兼容老设备 | 中等 |
| **Underlay (VLAN)** | vlan | 1500 | 物理网络直通 | 高 |
| **Underlay (SR-IOV)** | (无需隧道) | 9000 | 高性能计算 | 极高 |

### 网关类型对比

| 网关类型 | gatewayType | 优点 | 缺点 | 使用场景 |
|---------|-------------|------|------|---------|
| **分布式网关** | distributed | 流量本地转发、低延迟 | 每个 Node 需要公网 IP | 生产环境首选 |
| **集中式网关** | centralized | 节省公网 IP、易管理 | 网关节点瓶颈、跨节点延迟 | 测试环境、IP 紧张 |

---

## 数据结构映射

### Pod Annotation → OVN LSP

| Pod Annotation | 含义 | OVN LSP 字段 | 示例值 |
|---------------|------|-------------|--------|
| `ip_address` | Pod IP | addresses[1] | `10.16.0.5` |
| `mac_address` | Pod MAC | addresses[0] | `00:00:00:A5:C2:31` |
| `subnet` | 所属子网 | external_ids | `ovn-default` |
| `gateway` | 子网网关 | (不在 LSP) | `10.16.0.1` |
| `ipam.kubeovn.io/ip-addr` | 固定 IP | addresses[1] | `10.16.0.100` |
| `ipam.kubeovn.io/subnet` | 指定子网 | external_ids | `custom-subnet` |

**代码示例**:
```go
// 来源: pkg/controller/pod/controller.go
pod.Annotations = map[string]string{
    "ip_address":  ipStr,
    "mac_address": macStr,
    "subnet":      subnetName,
    "gateway":     gateway,
    "cidr":        cidr,
}
```

### Subnet CRD → OVN Logical Switch

| Subnet 字段 | OVN LS 字段 | 转换规则 |
|------------|------------|---------|
| `metadata.name` | `name` | 直接映射 |
| `spec.cidr` | `other_config:subnet` | `10.16.0.0/16` |
| `spec.gateway` | `other_config:gateway` | `10.16.0.1` |
| `spec.mtu` | `other_config:mtu` | `1400` |
| `spec.excludeIps` | (不在 LS) | 用于 IPAM |
| `spec.vpc` | (不在 LS) | 关联到 LR |

**创建命令**:
```bash
ovn-nbctl ls-add ovn-default \
  -- set Logical_Switch ovn-default other_config:subnet=10.16.0.0/16 \
  -- set Logical_Switch ovn-default other_config:gateway=10.16.0.1
```

### IP CRD → OVN LSP Addresses

| IP CRD 字段 | LSP addresses 格式 | 示例 |
|------------|-------------------|------|
| `spec.ipAddress` | `<ip>` | `10.16.0.5` |
| `spec.macAddress` | `<mac> <ip>` | `00:00:00:A5:C2:31 10.16.0.5` |
| `spec.v6IpAddress` | `<mac> <ipv4> <ipv6>` | `00:00:00:A5:C2:31 10.16.0.5 fd00::5` |

**安全配置**:
```bash
# port_security 确保 Pod 只能使用分配的 IP/MAC
ovn-nbctl lsp-set-port-security my-pod_default \
  "00:00:00:A5:C2:31 10.16.0.5"
```

### NetworkPolicy → OVN ACL

| NetworkPolicy 字段 | OVN ACL 字段 | 生成规则示例 |
|-------------------|--------------|-------------|
| `podSelector` | (不存储在 ACL) | 用于过滤 Pod |
| `policyTypes.ingress` | `direction: "from-lport"` | 入站规则 |
| `policyTypes.egress` | `direction: "to-lport"` | 出站规则 |
| `ingress.from[].ports` | `match: "tcp.dst == 80"` | 端口匹配 |
| `ingress.from[].from` | `match: "ip4.src == $addr_set"` | 来源匹配 |
| `policyTypes[0]` | `action: "drop"` (默认拒绝) | 默认策略 |

**ACL 优先级**:
```
priority 1000: 明确 allow 规则
priority    1: 明确 drop 规则
priority    0: 默认 drop 规则
```

### Service → OVN Load Balancer

| Service 字段 | OVN LB 字段 | 示例 |
|-------------|------------|------|
| `spec.clusterIP` | `vips["<ip>:<port>"]` | `10.96.0.1:80` |
| `spec.ports[].port` | VIP 端口 | `80` |
| `spec.ports[].protocol` | `protocol` | `tcp` |
| `endpoints[].ip` | backend IP | `10.16.0.5:80` |
| `endpoints[].port` | backend 端口 | `80` |

**VIP 格式**:
```yaml
vips:
  "10.96.0.1:80": "10.16.0.5:80,10.16.0.6:80,10.16.0.7:80"
  "10.96.0.1:443": "10.16.0.5:443,10.16.0.8:443"
```

---

## 生命周期状态

### Pod 网络状态

| Pod Phase | 网络状态 | 说明 |
|-----------|---------|------|
| `Pending` | IP 未分配 | Controller 正在处理 |
| `Pending` | IP 已分配 | OVN LSP 已创建,等待 CNI |
| `Running` | 网络就绪 | veth 创建,OVS 端口绑定 |
| `Failed` | IP 释放 | OVN LSP 删除 |
| `Succeeded` | IP 释放 | (同 Failed) |

### Subnet 状态

| Subnet Phase | availableIPs | 说明 |
|--------------|--------------|------|
| `Initializing` | N/A | 正在创建 OVN LS |
| `Ready` | > 0 | 子网就绪,可分配 IP |
| `Terminating` | 0 | 正在删除子网 |
| `Failed` | 0 | 子网创建失败 |

### IP CRD 状态

| IP Phase | 说明 | 清理策略 |
|----------|------|---------|
| `Using` | IP 正在使用 | Pod 删除后转为 Released |
| `Released` | IP 已释放 | GC 360s 后删除 CRD |

### VPC 状态

| VPC Phase | logicalRouter | 说明 |
|-----------|---------------|------|
| `Initializing` | 不存在 | 正在创建 LR |
| `Ready` | 存在 | VPC 就绪 |
| `Updating` | 存在 | 正在更新路由 |
| `Terminating` | 存在 | 正在删除 LR |

---

## 常用诊断命令

### Controller 相关

```bash
# 查看 Controller 状态
kubectl get deploy kube-ovn-controller -n kube-system

# 查看 Controller 日志
kubectl logs -n kube-system deploy/kube-ovn-controller --tail=100 -f

# 查看 Controller 性能指标
kubectl port-forward -n kube-system svc/kube-ovn-monitor 10660 :10660
curl http://localhost:10660/metrics | grep controller
```

### Subnet/IP 相关

```bash
# 查看所有 Subnet
kubectl-ko get subnet

# 查看 Subnet 详情
kubectl-ko get subnet ovn-default -o yaml

# 查看 IP 使用情况
kubectl-ko get ip -A

# 查看特定 Pod 的 IP
kubectl-ko get ip -n kube-system -l podName=my-pod

# 统计 IP 使用率
kubectl-ko get subnet -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.availableIPs}{"\n"}{end}'
```

### OVN 数据库相关

```bash
# 查看 NB DB 内容
kubectl-ko nbctl show

# 查看 Logical Switch
kubectl-ko nbctl ls-list

# 查看 Logical Switch Port
kubectl-ko nbctl lsp-list ovn-default

# 查看 ACL
kubectl-ko nbctl acl-list

# 查看 Load Balancer
kubectl-ko nbctl lb-list

# 查看 SB DB 流表
kubectl-ko sbctl lf-list
```

### 网络诊断

```bash
# 测试 Pod 连通性
kubectl exec -it <pod-name> -- ping <target-ip>

# 查看 OVS 端口
kubectl exec -n kube-system <ovs-node> -- ovs-vsctl show

# 查看 OVS 流表
kubectl exec -n kube-system <ovs-node> -- ovs-ofctl dump-flows br-int

# 查看端口绑定
kubectl-ko sbctl port-binding list
```

---

## 配置参数速查

### Controller 关键参数

| 参数 | 默认值 | 说明 | 调优建议 |
|------|--------|------|---------|
| `--worker-num` | 3 | Worker goroutine 数 | 大集群可增加到 5-10 |
| `--gc-interval` | 360 | GC 间隔(秒) | 可降低到 180 加快回收 |
| `--inspect-interval` | 20 | 资源检查间隔(秒) | 不建议修改 |
| `--ovn-timeout` | 60 | OVN 命令超时(秒) | 慢环境可增加到 120 |
| `--enable-pprof` | false | 性能分析 | 调试时启用 |
| `--pprof-port` | 10660 | pprof 端口 | 默认即可 |

### Daemon 关键参数

| 参数 | 默认值 | 说明 | 调优建议 |
|------|--------|------|---------|
| `--mtu` | 0 (自动计算) | Pod MTU | Geneve: 1400, VXLAN: 1450 |
| `--enable-mirror` | false | 流量镜像 | 调试时启用 |
| `--ovs-vsctl-concurrency` | 100 | ovs-vsctl 并发 | 高负载环境可增加 |
| `--cni-conf-name` | 01-kube-ovn.conflist | CNI 配置文件 | 默认即可 |

### IPAM 参数

| 参数 | 默认值 | 说明 | 影响 |
|------|--------|------|------|
| 顺序分配 | false | 是否顺序分配 IP | 可提高缓存命中率 |
| GC 延迟 | 360s | IP 释放后延迟删除 | 减少 Pod 重建 IP 变化 |
| 冲突检测 | false | 是否启用 ARP 检测 | 启用会降低性能 |

---

## 错误代码速查

### 常见错误信息

| 错误信息 | 含义 | 根因 | 解决方案 |
|---------|------|------|---------|
| `Failed to allocate IP` | IP 分配失败 | Subnet IP 耗尽 | 扩容 CIDR 或清理无用 Pod |
| `no available IP in subnet` | 无可用 IP | Subnet 耗尽 | 同上 |
| `transaction error` | OVN 事务错误 | DB 冲突/过载 | 重试或扩容 NB |
| `connection refused` | DB 连接拒绝 | ovn-central 未就绪 | 检查 Central 状态 |
| `timeout` | 操作超时 | DB 慢/网络慢 | 增加超时时间 |
| `lsp already exists` | 端口已存在 | 重复创建 | 检查 IP CRD |
| `invalid CIDR` | CIDR 无效 | 配置错误 | 修正 CIDR 格式 |
| `gateway not reachable` | 网关不可达 | 网关配置错误 | 检查 gatewayType |

### Controller 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| `--v=2` | 默认日志 | 常规信息 |
| `--v=4` | 调试日志 | IP 分配过程 |
| `--v=6` | 详细日志 | OVN 事务详情 |
| `--v=8` | 追踪日志 | API 调用详情 |

### Event 消息

| Event 类型 | 严重度 | 说明 |
|-----------|--------|------|
| `Failed` | 高 | 操作失败,需人工介入 |
| `Warning` | 中 | 潜在问题,需关注 |
| `Normal` | 低 | 正常信息 |

**常见 Event**:
```
Normal:  Created IP CRD
Normal:  Allocated IP 10.16.0.5
Normal:  Created Logical Switch Port

Warning:  Subnet availableIPs < 100
Warning:  IP release delayed

Failed:  Failed to allocate IP
Failed:  Failed to create LSP
```

---

## 数据转换示例

### Pod 创建时的数据流

```yaml
# 1. Kubernetes Pod
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  namespace: default
spec:
  containers:
  - name: nginx
    image: nginx

# ↓ kube-ovn-controller 处理

# 2. IP CRD
apiVersion: kubeovn.io/v1
kind: IP
metadata:
  name: my-pod.default
  namespace: kube-system
spec:
  podName: my-pod
  namespace: default
  ipAddress: 10.16.0.5
  macAddress: 00:00:00:A5:C2:31
  subnet: ovn-default

# ↓ Controller 写入 OVN

# 3. OVN Logical Switch Port
# 命令: ovn-nbctl lsp-add ovn-default my-pod_default
#       ovn-nbctl lsp-set-addresses my-pod_default "00:00:00:A5:C2:31 10.16.0.5"
#       ovn-nbctl lsp-set-port-security my-pod_default "00:00:00:A5:C2:31 10.16.0.5"

# ↓ ovn-northd 转换

# 4. OVN Logical Flow
# table=30, priority=100
# match="arp.tpa == 10.16.0.5 && arp.op == 1"
# actions="eth.dst = eth.src; arp.op = 2; arp.tha = arp.sha; \
#          arp.sha = 00:00:00:A5:C2:31; \
#          arp.tpa = 10.16.0.5; outport = inport; \
#          inport = \"\"; output;"

# ↓ ovn-controller 下发

# 5. OpenFlow (在 ovs-vswitchd)
# ovs-ofctl: add-flow br-int "priority=100 arp, \
#           arp_tpa=10.16.0.5 actions=move:NXM_OF_ETH_SRC[]->NXM_OF_ETH_DST[], \
#           mod_dl_src:00:00:00:A5:C2:31, load:0x2->NXM_OF_ARP_OP[], \
#           move:NXM_NX_ARP_SHA[]->NXM_OF_ARP_THA[], \
#           load:0x000000A5C231->NXM_OF_ARP_SHA[], \
#           load:0x0a100005->NXM_NX_ARP_TPA[], \
#           load:0->NXM_OF_IN_PORT[], output:NXM_OF_IN_PORT[]"

# ↓ Pod Annotation 更新

# 6. Pod Annotation (回写到 Pod)
metadata:
  annotations:
    ip_address: "10.16.0.5"
    mac_address: "00:00:00:A5:C2:31"
    subnet: "ovn-default"
    gateway: "10.16.0.1"
    cidr: "10.16.0.0/16"
```

### NetworkPolicy 转换

```yaml
# 1. Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: backend
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 80

# ↓ Controller 转换

# 2. OVN Address Set
# name: a_ip4_addr_a_16982471633887286017
# addresses: ["10.16.0.5", "10.16.0.6"]  # frontend Pods

# 3. OVN ACL
# name: np-allow-from-frontend-16982471633887286017
# action: allow-from-lport
# direction: from-lport
# match: "ip4.src == $a_ip4_addr_a_16982471633887286017 && tcp.dst == 80"
# priority: 1000
# external_ids: {"kube-ovn/np": "allow-from-frontend"}

# ↓ ovn-northd 转换

# 4. Logical Flow (table 11, ingress)
# match="ip4.src == $a_ip4_addr_a_16982471633887286017 && \
#        tcp && tcp.dst == 80 && \
#        ip4.dst == 10.16.0.10"  # backend Pod IP
# actions="next;"
# priority=1000
```

---

## 总结

### 快速参考清单

#### Pod 网络问题诊断清单

- [ ] 检查 Pod Phase 和 Events
- [ ] 检查 Subnet availableIPs
- [ ] 检查 IP CRD 是否存在
- [ ] 检查 OVN LSP 是否创建
- [ ] 检查 Pod Annotation 是否完整
- [ ] 检查 CNI 日志

#### Controller 健康检查清单

- [ ] 检查 Controller Pod 状态
- [ ] 检查 Leader Election 状态
- [ ] 检查 WorkQueue 深度
- [ ] 检查 OVN DB 连接
- [ ] 检查 GC 是否正常运行
- [ ] 检查性能指标 (CPU/内存)

#### OVN 数据库检查清单

- [ ] 检查 ovn-central 健康
- [ ] 检查 ovn-northd 运行状态
- [ ] 检查 NB/SB 同步状态
- [ ] 检查 Raft 集群状态
- [ ] 检查事务延迟
- [ ] 检查表大小和索引

### 关键命令记忆卡

```bash
# Controller 日志
kubectl logs -n kube-system deploy/kube-ovn-controller

# Subnet IP 使用
kubectl get subnet ovn-default -o jsonpath='{.status.availableIPs}'

# OVN 状态
kubectl-ko nbctl show
kubectl-ko sbctl show

# OVN 端口
kubectl-ko nbctl lsp-list ovn-default

# OVN ACL
kubectl-ko nbctl acl-list

# OVN 流表
kubectl-ko sbctl lf-list | grep "ls_in_acl"
```

---

**文档版本**: v1.0
**最后更新**: 2026-01-08
**适用版本**: Kube-OVN v1.16.x
