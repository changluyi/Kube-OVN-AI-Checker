---
# Ingress (外部网络访问 Pod)
triggers:
  - ingress
  - 外部访问pod
  - dnat
  - 入网
  - 公网访问

# 分类：外部到 Pod 通信
category: pod_to_external

# 优先级：40 (常见场景)
priority: 40
---

# Ingress (外部网络访问 Pod)

## 概述

Ingress 允许外部网络访问集群内的 Pod 服务。Kube-OVN 支持两种实现方式:
1. **NAT Dnat** (使用 Gateway Node + DNAT 规则)
2. **Ingress Controller** (Nginx/Traefik/HAProxy 等)

## 架构设计

### NAT DNAT 模式

```
Internet Client (203.0.113.10)
  ↓ 访问 192.168.1.100:80 (Public IP)
Gateway Node (192.168.1.10)
  ↓ DNAT: 192.168.1.100 → 10.16.0.5:8080
OVS Load Balancer
  ↓ 负载均衡
Backend Pods (10.16.0.5, 10.16.0.6, 10.16.0.7)
```

### Ingress Controller 模式

```
Internet Client
  ↓ DNS: app.example.com
Ingress Controller (NodePort/LoadBalancer)
  ↓ HTTP Routing (Host/Path)
Service (ClusterIP)
  ↓ OVS Load Balancer
Backend Pods
```

## NAT DNAT 配置

### 1. 准备 Public IP

```bash
# 假设 Gateway Node 有 Public IP:
# eth0: 192.168.1.10 (Private)
# eth0:1 203.0.113.100 (Public - Alias IP)
```

### 2. 配置 DNAT 规则

```bash
# 使用 OVN NB CLI 添加 DNAT 规则
kubectl-ko nbctl lr-nat-add ovn-cluster dnat \
  203.0.113.100 \
  10.16.0.5

# 查看 DNAT 规则
kubectl-ko nbctl lr-nat-list ovn-cluster

# 输出:
# TYPE         EXTERNAL_IP    LOGICAL_IP
# dnat         203.0.113.100   10.16.0.5
```

### 3. 配置端口转发 (可选)

```bash
# DNAT with Port
kubectl-ko nbctl lr-nat-add ovn-cluster dnat \
  203.0.113.100:80 \
  10.16.0.5:8080
```

### 4. 验证

```bash
# 从外部访问
curl http://203.0.113.100:80

# 应该访问到 Pod (10.16.0.5:8080)
```

## Ingress Controller 配置

### 使用 Nginx Ingress Controller

#### 1. 安装 Nginx Ingress

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

#### 2. 配置 Ingress 资源

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  namespace: default
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com        # 域名
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx-svc      # ClusterIP Service
            port:
              number: 80
```

#### 3. 配置 DNS

```bash
# 添加 A 记录:
# app.example.com → 192.168.1.10 (Ingress Controller Node IP)
```

#### 4. 验证

```bash
# 从外部访问
curl http://app.example.com/

# 或使用 Host 头
curl -H "Host: app.example.com" http://192.168.1.10/
```

## OVS 流表关键路径

### DNAT 流表

```bash
# Gateway Node - Table 0: 外部流量入口
table=0, priority=100, ip, in_port="eth0", nw_dst=203.0.113.100,
       actions=goto_table(32)

# Table 32: DNAT (Public IP → Pod IP)
table=32, priority=100, ip, nw_dst=203.0.113.100,
       actions=set_field:10.16.0.5->nw_dst,
                set_field:8080->tcp_dst,
                goto_table(33)

# Table 33: 路由到 Pod
table=33, priority=50, ip, nw_dst=10.16.0.5,
       actions=output("veth_pod")
```

### SNAT 流表 (保证回包路径)

```bash
# Table 32: SNAT (Pod IP → Public IP)
table=32, priority=100, ip, nw_src=10.16.0.5,
       actions=set_field:203.0.113.100->nw_src,
                goto_table(33)
```

## 诊断命令

### 1. DNAT 规则检查

```bash
# 查看 DNAT 规则
kubectl-ko nbctl lr-nat-list ovn-cluster

# 查看特定 DNAT 规则
kubectl-ko nbctl lr-nat-get ovn-cluster dnat_203.0.113.100
```

### 2. Ingress Controller 检查

```bash
# 查看 Ingress 资源
kubectl get ingress

# 查看 Ingress 详情
kubectl describe ingress nginx-ingress

# 查看 Ingress Controller Pod
kubectl get pods -n ingress-nginx
```

### 3. 流表检查

```bash
# 查看 DNAT 流表 (Table 32)
ovs-ofctl dump-flows br-int table=32

# 查找 Public IP 相关流
ovs-ofctl dump-flows br-int | grep "203.0.113.100"
```

### 4. 连通性测试

```bash
# 从外部访问 Public IP
curl http://203.0.113.100:80

# 使用域名访问
curl http://app.example.com/

# 查看响应头
curl -I http://app.example.com/
```

### 5. 抓包验证

```bash
# 在 Gateway Node 抓包
tcpdump -i eth0 -nn host 203.0.113.100

# 应该看到 DNAT 前后的包:
# IP 203.0.113.100 > 192.168.1.10  (外部 → Gateway)
# IP 10.16.0.5 > 203.0.113.100   (Pod → 外部)
```

## 常见问题

| 症状 | 可能原因 | 诊断命令 | 解决方案 |
|------|---------|---------|---------|
| Public IP 不通 | DNAT 规则未配置 | `kubectl-ko nbctl lr-nat-list` | 添加 DNAT 规则 |
| 502 Bad Gateway | Backend Pod 未就绪 | `kubectl get pods` | 等待 Pod Ready |
| 域名无法解析 | DNS 未配置 | `nslookup app.example.com` | 添加 DNS 记录 |
| 回包路径错误 | SNAT 规则缺失 | `tcpdump -i eth0` | 添加 SNAT 规则 |
| Ingress Controller 无法访问 | Service 配置错误 | `kubectl get svc` | 检查 Service 类型 |

## 性能优化

### 使用多个 Public IP

```bash
# 添加多个 DNAT 规则,负载均衡到多个 Pod
kubectl-ko nbctl lr-nat-add ovn-cluster dnat 203.0.113.100 10.16.0.5
kubectl-ko nbctl lr-nat-add ovn-cluster dnat 203.0.113.101 10.16.0.6
kubectl-ko nbctl lr-nat-add ovn-cluster dnat 203.0.113.102 10.16.0.7
```

### 使用 LoadBalancer 类型的 Ingress Controller

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ingress-nginx
  namespace: ingress-nginx
spec:
  type: LoadBalancer          # 使用云厂商 LB
  externalTrafficPolicy: Local
  selector:
    app.kubernetes.io/name: ingress-nginx
  ports:
  - port: 80
    targetPort: 80
```

## 安全配置

### 限制访问源 IP

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"
spec:
  # ... 其他配置
```

### 使用 TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
spec:
  tls:
  - hosts:
    - app.example.com
    secretName: app-tls-cert
  rules:
  - host: app.example.com
    # ... 其他配置
```

## NAT Dnat vs Ingress Controller

| 特性 | NAT Dnat | Ingress Controller |
|------|----------|-------------------|
| **复杂度** | 低 (简单 DNAT) | 高 (需要 Controller) |
| **功能** | 基础端口转发 | 丰富 (路由/SSL/认证) |
| **性能** | 高 (OVS DNAT) | 中等 (7层代理) |
| **适用场景** | 简单服务 | Web 应用/微服务 |
| **推荐使用** | 内网服务 | 生产环境 |

## 相关文档

- **Egress NAT**: `egress.md`
- **Join 网络**: `join-network.md`
- **NodePort Service**: `../service-communication/nodeport.md`
