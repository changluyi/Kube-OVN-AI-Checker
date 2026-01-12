---
# LoadBalancer Service 通信
triggers:
  - loadbalancer
  - 外部负载均衡
  - metallb
  - 云负载均衡

# 分类：Pod 到 Service 通信
category: pod_to_service

# 优先级：50 (云环境使用)
priority: 50
---

# LoadBalancer Service 通信

## 概述

LoadBalancer Service 类型自动为 Service 创建一个外部负载均衡器 (如 MetalLB、云厂商 LB)。Kube-OVN 本身不实现 LoadBalancer,而是与外部 LB 控制器集成。

## 架构设计

### 组件交互

```
External LB Controller (MetalLB/Cloud LB)
  ↓ 配置 LB 规则
Physical Load Balancer
  ↓ 转发流量
Node NodePort (30080)
  ↓ DNAT: NodePort → ClusterIP
OVS Load Balancer
  ↓ DNAT: ClusterIP → Backend Pod
Backend Pod (10.16.0.5:8080)
```

### Kube-OVN 的角色

Kube-OVN 负责:
1. ✅ 集群内负载均衡 (OVS Load Balancer)
2. ✅ NodePort 流量转发
3. ❌ **不负责** 外部 LB 实现 (由 MetalLB/云厂商实现)

## 常见 LB 实现

### MetalLB (裸金属/本地集群)

#### Layer 2 模式

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
spec:
  type: LoadBalancer
  loadBalancerIP: 192.168.1.100  # 指定外部 IP
  selector:
    app: nginx
  ports:
  - port: 80
    targetPort: 8080
```

**流量路径**:
```
Client → 192.168.1.100:80 (VIP)
  ↓ ARP: 192.168.1.100 → Node MAC
Node (Master Node)
  ↓ NodePort: 80 → 30080
OVS Load Balancer
  ↓ DNAT to Backend
Backend Pod
```

**特点**:
- 使用 ARP 协议
- 单节点故障转移 (通过 Leader Election)
- 适合小规模集群

#### Layer 3 模式 (BGP)

```yaml
# MetalLB ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: metallb-config
  namespace: metallb-system
data:
  config: |
    address-pools:
    - name: default
      protocol: bgp
      addresses:
      - 192.168.1.100-192.168.1.200
```

**流量路径**:
```
Client → 192.168.1.100:80 (VIP)
  ↓ BGP Route
Router (物理路由器)
  ↓ ECMP (Equal Cost Multi-Path)
Nodes (所有 Node)
  ↓ NodePort
OVS Load Balancer
Backend Pod
```

**特点**:
- 使用 BGP 路由
- 真正的负载均衡 (ECMP)
- 适合大规模集群

### 云厂商 LB (AWS/GCP/Azure)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"  # AWS NLB
spec:
  type: LoadBalancer
  selector:
    app: nginx
  ports:
  - port: 80
    targetPort: 8080
```

**流量路径**:
```
Internet Client
  ↓ DNS: nginx-svc.elb.amazonaws.com
Cloud Load Balancer (ALB/NLB)
  ↓ Target Group: Nodes
Node NodePort
  ↓ OVS Load Balancer
Backend Pod
```

## OVS 流表关键路径

### LoadBalancer → NodePort 转发

```bash
# NodePort 入口 (由外部 LB 流量触发)
table=0, priority=150, ip, in_port="eth0", tp_dst=30080,
       actions=goto_table(40)

# Table 40: Load Balancer (DNAT 到 Backend)
table=40, priority=100, ip, tp_dst=30080,
       actions=mod_nw_dst:10.16.0.5,
                mod_tp_dst:8080,
                output:"veth_pod_backend"
```

**注意**: Kube-OVN 只处理 NodePort 之后的流量,**外部 LB 到 NodePort 的部分由 LB 控制器处理**。

## 示例配置

### MetalLB Layer 2 配置

```yaml
# metallb-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  namespace: metallb-system
  name: metallb-config
data:
  config: |
    address-pools:
    - name: default
      protocol: layer2
      addresses:
      - 192.168.1.100-192.168.1.150
```

### Service 配置

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
spec:
  type: LoadBalancer
  # loadBalancerIP: 192.168.1.100  # 可选,指定 IP
  selector:
    app: nginx
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
```

### 验证

```bash
# 查看 LoadBalancer IP
kubectl get svc nginx-svc
# NAME       TYPE           EXTERNAL-IP      PORT(S)
# nginx-svc  LoadBalancer   192.168.1.100     80:30080/TCP

# 从外部访问
curl http://192.168.1.100:80
```

## 诊断命令

### 1. LoadBalancer 状态

```bash
# 查看 Service
kubectl get svc nginx-svc

# 查看 External IP 分配
kubectl describe svc nginx-svc | grep "LoadBalancer"

# 查看 MetalLB 日志
kubectl logs -n metallb-system -l app=metallb-controller
```

### 2. BGP/ARP 状态 (MetalLB)

```bash
# 查看 BGP Peer 状态
kubectl exec -n metallb-system speaker-xxx -- birdc show protocols

# 查看 ARP 表
ip neigh show | grep "192.168.1.100"
```

### 3. 云厂商 LB 状态

```bash
# AWS ELB
aws elb describe-load-balancers --load-balancer-names <elb-name>

# GCP Forwarding Rule
gcloud compute forwarding-rules list
```

### 4. 连通性测试

```bash
# 从外部访问
curl http://192.168.1.100:80

# 查看负载均衡分布
for i in {1..10}; do
  curl http://192.168.1.100:80 | grep "Hostname"
done
```

### 5. 流量追踪

```bash
# NodePort 部分使用 ovn-trace
kubectl-ko nbctl trace-packet --ovn ovn-default \
  'inport=="eth0" && ip4.dst==192.168.1.100 && tcp.dst==80'
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| External IP 一直是 Pending | MetalLB 未就绪 | `kubectl get pods -n metallb-system` | 等待 MetalLB Ready |
| 无法访问 External IP | 防火墙阻止 | `iptables -L -n \| grep 192.168.1.100` | 开放防火墙 |
| 流量只到一个 Node | Layer 2 模式限制 | `kubectl get configmap -n metallb-system` | 切换 Layer 3 (BGP) |
| 源 IP 不对 | SNAT 配置问题 | `kubectl logs <backend-pod>` | 检查 externalTrafficPolicy |
| BGP 未建立 | Router 配置错误 | `kubectl exec speaker-xxx -- birdc show proto` | 检查 BGP 配置 |

## 性能特征

| LB 类型 | 延迟 | 吞吐量 | 扩展性 |
|---------|------|--------|--------|
| MetalLB L2 | 5-10ms | 受限于单节点 | 低 |
| MetalLB L3 (BGP) | 2-5ms | 所有节点总和 | 高 |
| 云厂商 LB | 10-50ms | 云厂商限制 | 高 |

## externalTrafficPolicy

### Cluster (默认)

```yaml
spec:
  type: LoadBalancer
  externalTrafficPolicy: Cluster  # 流量分发到所有 Node 的 Backend
```

**影响**:
- ✅ 负载均衡好
- ❌ 看不到真实客户端 IP (SNAT)

### Local

```yaml
spec:
  type: LoadBalancer
  externalTrafficPolicy: Local  # 流量只转发到本地 Node 的 Backend
```

**影响**:
- ✅ 保留真实客户端 IP
- ❌ 可能负载不均

## 健康检查

### MetalLB Health Check

```yaml
# MetalLB 自动监控 NodePort
# 如果 Backend Pod 不就绪,流量不会转发到该 Node
```

### 云厂商 LB Health Check

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  annotations:
    # AWS NLB health check
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol: "TCP"
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-port: "8080"
spec:
  type: LoadBalancer
```

## 相关文档

- **ClusterIP Service**: `clusterip.md`
- **NodePort Service**: `nodeport.md`
- **MetalLB 官方文档**: https://metallb.universe.tf/
- **Kube-OVN 外部访问**: `../pod-to-node-communication/egress.md`
