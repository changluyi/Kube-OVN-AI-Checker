---
# ClusterIP Service 通信
triggers:
  - clusterip
  - service
  - 负载均衡
  - ovs lb

# 分类：Pod 到 Service 通信
category: pod_to_service

# 优先级：30 (常见场景)
priority: 30
---

# ClusterIP Service 通信

## 概述

ClusterIP 是 Kubernetes 默认的 Service 类型,提供集群内部的虚拟 IP (VIP) 和负载均衡。Kube-OVN 使用 **OVS Load Balancer** 替代传统的 kube-proxy,实现高性能分布式负载均衡。

## 架构设计

### Service 实现方式对比

| 特性 | kube-proxy (iptables) | Kube-OVN OVS LB |
|------|---------------------|----------------|
| 实现位置 | Node 级别 | 集群级别 (OVN) |
| 数据包路径 | Pod → Node iptables → Backend | Pod → OVS LB → Backend |
| 性能 | 中等 (需要 NAT) | 高 (分布式负载均衡) |
| 更新延迟 | 秒级 | 毫秒级 |
| 同步开销 | 高 (全量更新) | 低 (增量更新) |

## 通信流程

```
Pod A (10.16.0.2)
  ↓ 发送到 Service VIP
OVS br-int
  ↓ Table 40: Load Balancer
OVS Load Balancer
  ↓ DNAT: VIP → Pod IP
Backend Pod B (10.16.0.5)
```

## OVS 流表关键路径

### Load Balancer 流表

```bash
# Table 40: Load Balancer (LB Pipeline)
# DNAT: VIP → Backend Pod IP
table=40, priority=100, ip, nw_dst=10.96.100.50, tp_dst=80,
       actions=lb_group(vip_10.96.100.50_tcp_80)

# Load Balancer Group 定义
# Backend 1: 10.16.0.5:8080
# Backend 2: 10.16.0.6:8080
# Backend 3: 10.16.0.7:8080
```

### 数据包变换

**请求包**:
```
Original:
  dst IP: 10.96.100.50 (Service VIP)
  dst Port: 80

After LB DNAT:
  dst IP: 10.16.0.5 (Backend Pod IP)
  dst Port: 8080 (targetPort)
```

**响应包**:
```
Return:
  src IP: 10.16.0.5
  src Port: 8080

After LB SNAT:
  src IP: 10.96.100.50
  src Port: 80
```

## 示例配置

### Service YAML

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  namespace: default
spec:
  type: ClusterIP
  selector:
    app: nginx
  ports:
  - port: 80          # Service Port
    targetPort: 8080  # Container Port
    protocol: TCP
```

### OVN Load Balancer 查看

```bash
# 查看 Load Balancer 列表
kubectl-ko nbctl lb-list

# 查看 Load Balancer 详细信息
kubectl-ko nbctl lb-lb-addresses <lb-uuid>

# 查看 VIP 后端
kubectl-ko nbctl lb-lb-addresses <lb-uuid> | grep 10.96.100.50
```

## 诊断命令

### 1. Service 状态检查

```bash
# 查看 Service
kubectl get svc nginx-svc

# 查看 Service 详情
kubectl describe svc nginx-svc

# 查看 Endpoints
kubectl get endpoints nginx-svc
```

### 2. Load Balancer 检查

```bash
# 查看 OVS Load Balancer
kubectl-ko nbctl lb-list

# 查找特定 Service 的 LB
kubectl-ko nbctl lb-list | grep nginx-svc

# 查看 LB 后端 Pod
kubectl-ko nbctl lb-lb-addresses <lb-uuid>
```

### 3. 流表检查

```bash
# 查看 Table 40 (Load Balancer)
ovs-ofctl dump-flows br-int table=40

# 查找特定 VIP 的流
ovs-ofctl dump-flows br-int | grep "10.96.100.50"
```

### 4. 连通性测试

```bash
# 从 Pod 访问 Service
kubectl exec -it pod-a -- curl http://10.96.100.50:80

# 查看负载均衡分布
for i in {1..10}; do
  kubectl exec -it pod-a -- curl http://10.96.100.50:80 | grep "Hostname"
done
```

### 5. 数据包追踪

```bash
# 使用 ovn-trace 追踪
kubectl-ko nbctl trace-packet --ovn ovn-default \
  'inport=="pod_a" && ip4.src==10.16.0.2 && ip4.dst==10.96.100.50 && tcp.dst==80'
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| `connection refused` | Endpoints 为空 | `kubectl get endpoints` | 等待 Pod Ready |
| `no route to host` | LB 规则未同步 | `kubectl-ko nbctl lb-list` | 重启 controller |
| 负载不均 | 后端 Pod 数量少 | `kubectl get endpoints` | 增加 Pod 数量 |
| 偶尔超时 | 后端 Pod 不健康 | `kubectl get pods` | 检查 Pod 状态 |
| VIP 不通 | LB 规则缺失 | `ovs-ofctl dump-flows br-int table=40` | 重建 Service |

## 性能特征

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 延迟 | <1ms | OVS LB DNAT 开销 |
| 吞吐量 | 10Gbps+ | 分布式负载均衡 |
| CPU 开销 | 5-15% | 取决于连接数 |
| 更新延迟 | 毫秒级 | 增量更新 |

## 会话保持 (Session Affinity)

### 配置

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
spec:
  sessionAffinity: ClientIP  # 基于 Client IP 保持会话
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800  # 3 小时
```

### 验证

```bash
# 多次请求应该打到同一个 Pod
for i in {1..5}; do
  kubectl exec -it client -- curl http://10.96.100.50 | grep "Pod"
done
```

## 相关文档

- **NodePort Service**: `nodeport.md`
- **LoadBalancer Service**: `loadbalancer.md`
- **Service 对比表**: `comparison-table.md`
