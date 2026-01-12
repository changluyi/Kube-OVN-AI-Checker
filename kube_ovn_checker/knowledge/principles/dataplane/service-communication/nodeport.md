---
# NodePort Service 通信
triggers:
  - nodeport
  - 外部访问
  - 节点端口
  - 30000

# 分类：Pod 到 Service 通信
category: pod_to_service

# 优先级：40 (常见场景)
priority: 40
---

# NodePort Service 通信

## 概述

NodePort 允许通过 `NodeIP:NodePort` 从集群外部访问 Service。Kube-OVN 支持两种 NodePort 实现方式:
1. **集中式网关** (Centralized Gateway): 流量通过特定 Gateway Node
2. **分布式网关** (Distributed Gateway): 每个 Node 都可以转发流量

## 架构对比

### Centralized vs Distributed

| 特性 | 集中式网关 | 分布式网关 |
|------|-----------|-----------|
| 流量路径 | Client → Gateway Node → Backend Pod | Client → Any Node → Backend Pod |
| 性能 | 网关成为瓶颈 | 性能更好 |
| 高可用 | 网关故障 → 不可达 | 任意 Node 可达 |
| 使用场景 | 传统网络 | 云原生/高性能 |

## 通信流程

### 集中式网关 (Centralized)

```
External Client
  ↓ NodeIP:30080
Gateway Node (192.168.1.10:30080)
  ↓ DNAT: 30080 → ClusterIP
OVS Load Balancer
  ↓ DNAT: ClusterIP → Backend Pod
Backend Pod (10.16.0.5:8080)
```

### 分布式网关 (Distributed)

```
External Client
  ↓ Any NodeIP:30080
Node1/Node2/Node3 (任意 Node)
  ↓ DNAT: 30080 → ClusterIP
OVS Load Balancer
  ↓ DNAT: ClusterIP → Backend Pod
Backend Pod (10.16.0.5:8080)
```

## OVS 流表关键路径

### 集中式网关流表

```bash
# Gateway Node - Table 0: NodePort 入口
table=0, priority=150, ip, in_port="eth0", tp_dst=30080,
       actions=goto_table(40)

# Table 40: Load Balancer (DNAT: NodePort → ClusterIP)
table=40, priority=100, ip, tp_dst=30080,
       actions=set_field:10.96.100.50->nw_dst,
                set_field:80->tcp_dst,
                lb_group(vip_10.96.100.50_tcp_80)
```

### 分布式网关流表

```bash
# Any Node - Table 0: NodePort 入口
table=0, priority=150, ip, in_port="eth0", tp_dst=30080,
       actions=goto_table(40)

# Table 40: Load Balancer (直接 DNAT 到 Backend)
table=40, priority=100, ip, tp_dst=30080,
       actions=mod_nw_dst:10.16.0.5,
                mod_tp_dst:8080,
                output:"veth_pod_backend"
```

## 示例配置

### Service YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
spec:
  type: NodePort
  selector:
    app: nginx
  ports:
  - port: 80          # ClusterIP Port
    targetPort: 8080  # Container Port
    nodePort: 30080   # NodePort (可选,默认 30000-32767)
    protocol: TCP
```

### Subnet 配置 (网关模式)

```yaml
# 集中式网关
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default
spec:
  gatewayType: centralized  # 集中式网关
  gatewayNode: "node1"      # 指定网关节点

# 分布式网关
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: ovn-default
spec:
  gatewayType: distributed  # 分布式网关
```

## externalTrafficPolicy

### Cluster (默认)

```yaml
spec:
  type: NodePort
  externalTrafficPolicy: Cluster  # 流量分发到所有 Node 的 Backend
```

**特点**:
- 流量可能跨 Node
- 源 IP 被 SNAT (看不到真实客户端 IP)
- 负载均衡更好

### Local

```yaml
spec:
  type: NodePort
  externalTrafficPolicy: Local  # 流量只转发到本地 Node 的 Backend
```

**特点**:
- 流量只在本地 Node
- 保留真实客户端 IP
- 可能负载不均

## 诊断命令

### 1. NodePort 状态检查

```bash
# 查看 Service
kubectl get svc nginx-svc

# 查看 NodePort 分配
kubectl describe svc nginx-svc | grep NodePort

# 查看监听端口
netstat -tuln | grep 30080
```

### 2. 网关配置检查

```bash
# 查看网关节点
kubectl get nodes -l kube-ovn/role=gateway

# 查看 Subnet 网关类型
kubectl-ko get subnet ovn-default | grep gatewayType
```

### 3. 流表检查

```bash
# 查看 NodePort 流表
ovs-ofctl dump-flows br-int | grep "tp_dst=30080"

# 查看 Table 40 (Load Balancer)
ovs-ofctl dump-flows br-int table=40
```

### 4. 连通性测试

```bash
# 从外部访问 NodePort
curl http://192.168.1.10:30080

# 从集群内访问 NodePort
kubectl exec -it pod-a -- curl http://192.168.1.10:30080

# 测试所有 Node
for node_ip in 192.168.1.10 192.168.1.11 192.168.1.12; do
  curl http://$node_ip:30080
done
```

### 5. 源 IP 检查

```bash
# 查看 Backend Pod 接收到的源 IP
kubectl logs <backend-pod> | grep "RemoteAddr"

# externalTrafficPolicy: Local 时应该看到真实客户端 IP
# externalTrafficPolicy: Cluster 时看到的是 Node IP
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| NodePort 不通 | 防火墙阻止 | `iptables -L -n \| grep 30080` | 开放端口 |
| 只有网关节点可访问 | 配置了集中式网关 | `kubectl-ko get subnet` | 切换分布式网关 |
| 源 IP 不对 | externalTrafficPolicy=Cluster | `kubectl describe svc` | 改为 Local |
| 负载不均 | externalTrafficPolicy=Local | `kubectl get pods -o wide` | 改为 Cluster |
| 连接被拒绝 | Backend Pod 未就绪 | `kubectl get endpoints` | 等待 Pod Ready |

## 端口范围

### 默认范围

```yaml
# Kubernetes 默认
NodePort 范围: 30000-32767
```

### 自定义范围

```bash
# kube-apiserver 配置
--service-node-port-range=20000-40000
```

## 性能特征

| 指标 | 集中式网关 | 分布式网关 |
|------|-----------|-----------|
| 延迟 | 5-10ms | 2-5ms |
| 吞吐量 | 受限于网关 | 所有 Node 总和 |
| 扩展性 | 低 (网关瓶颈) | 高 (水平扩展) |
| 高可用 | 低 (网关单点) | 高 (任意 Node) |

## 安全配置

### 防火墙规则

```bash
# 只允许特定 IP 访问 NodePort
iptables -A INPUT -p tcp --dport 30080 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 30080 -j DROP
```

### NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nodeport-policy
spec:
  podSelector:
    matchLabels:
      app: nginx
  policyTypes:
  - Ingress
  ingress:
  - ports:
    - port: 8080
      protocol: TCP
```

## 相关文档

- **ClusterIP Service**: `clusterip.md`
- **LoadBalancer Service**: `loadbalancer.md`
- **外部访问对比**: `comparison-table.md`
