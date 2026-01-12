---
# IP 管理工作流
triggers:
  - ip
  - 地址
  - 耗尽
  - 分配
  - no ip
  - ipam
  - subnet

# 分类：通用基础文档
category: general

# 优先级：40（专题工作流）
priority: 40
---

# IP资源管理诊断工作流

## 概述

IP地址管理是Kube-OVN的核心功能之一。IP耗尽、分配失败、IP冲突等问题会导致Pod无法启动或网络异常。本工作流提供系统化的诊断步骤。

**常见症状**：
- Pod一直处于ContainerCreating状态
- Pod事件显示"Failed to allocate IP"
- 子网可用IP为0
- 删除Pod后IP未释放
- 跨节点Pod获得相同IP

## 诊断步骤

### 第一步：检查子网IP使用情况

#### 查看所有子网状态

```bash
# 列出所有子网
kubectl get subnet -A

# 详细查看特定子网
kubectl describe subnet <subnet-name>
```

#### 关键指标说明

**正常状态示例**：
```yaml
spec:
  cidrBlock: 10.16.0.0/16
  gateway: 10.16.0.1
  private: false
  excludeIps:
  - 10.16.0.0..10.16.0.10

status:
  availableIPs: 65524     # ✅ 充足
  usingIPs: 126           # 已分配
  totalIPs: 65650         # 总数
```

**异常状态示例**：
```yaml
# 情况1：IP耗尽
status:
  availableIPs: 0         # ❌ 已耗尽
  usingIPs: 65650
  totalIPs: 65650

# 情况2：即将耗尽
status:
  availableIPs: 3         # ⚠️  即将耗尽
  usingIPs: 65647
  totalIPs: 65650
```

#### 预期结果
- ✅ **正常**：`availableIPs > 10`
- ⚠️  **警告**：`5 < availableIPs <= 10`
- ❌ **异常**：`availableIPs <= 5`

### 第二步：分析IP分配策略

#### 检查IP分配模式

```bash
# 查看配置
kubectl get configmap -n kube-system ovn-config \
  -o jsonpath='{.data.crd}' | jq '.default_logical_gateway'
```

#### 分配模式说明

**Static模式（default_logical_gateway: true）**：
- Pod IP从所在节点子网分配
- 每个节点有独立的子网CIDR
- Pod跨节点重启后IP会变化
- 适合：节点固定、Pod不跨节点的场景

**Dynamic模式（default_logical_gateway: false）**：
- Pod IP从集群统一子网池分配
- Pod在整个集群范围内获得固定IP
- Pod跨节点重启后IP保持不变
- 适合：需要固定IP的场景

#### 检查子网CIDR配置

```bash
# 查看所有子网的CIDR
kubectl get subnet -o custom-columns=NAME:.metadata.name,CIDR:.spec.cidrBlock,AVAILABLE:.status.availableIPs

# 检查是否有CIDR冲突
kubectl get subnet -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.cidrBlock}{"\n"}{end}' \
  | sort -k2
```

#### 预期结果
- ✅ **正常**：不同子网的CIDR不重叠
- ❌ **异常**：CIDR有重叠（如多个节点使用相同CIDR）

### 第三步：诊断IP耗尽问题

#### 场景1：可用IP为0

**原因**：子网IP已全部分配

**解决方案**：

##### 方案1：扩容子网CIDR
```bash
# 编辑子网配置
kubectl edit subnet <subnet-name>

# 修改 CIDR（示例：从 /24 扩容到 /22）
# 修改前
spec:
  cidrBlock: 10.16.0.0/24

# 修改后
spec:
  cidrBlock: 10.16.0.0/22
```

**注意事项**：
- ⚠️  扩容CIDR不会影响已分配的IP
- ⚠️  缩小CIDR可能导致IP冲突
- ⚠️  需要确保新CIDR不与其他网络冲突

##### 方案2：清理僵尸IP
```bash
# 查找已删除Pod但仍占用的IP
kubectl get subnet <subnet-name> -o json \
  | jq '.status.usingIPs' \
  | jq 'to_entries[] | select(.value == null)'

# 强制释放IP
kubectl delete ip <ip-name> -n <namespace>

# 或批量清理
kubectl get ip -n <namespace> -o json \
  | jq '.items[] | select(.spec.podName == null) | .metadata.name' \
  | xargs -I {} kubectl delete ip {} -n <namespace>
```

##### 方案3：创建新子网
```bash
# 创建新的子网资源
cat <<EOF | kubectl apply -f -
apiVersion: kubeovn.io/v1
kind: Subnet
metadata:
  name: subnet-new
spec:
  cidrBlock: 10.17.0.0/16
  gateway: 10.17.0.1
  private: false
EOF

# 将新Pod调度到新子网
kubectl create namespace app-new
kubectl annotate namespace app-new ovn.kubernetes.io/subnet=subnet-new
```

#### 场景2：可用IP < 5

**原因**：即将耗尽

**解决方案**：

##### 监控和告警
```yaml
# Prometheus 告警规则
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: kube-ovn-ip-exhaustion
spec:
  groups:
  - name: kube-ovn
    rules:
    - alert: KubeOVNIPExhaustionWarning
      expr: kube_ovn_subnet_available_ips < 10
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Subnet {{ $labels.subnet_name }} running out of IPs"
        description: "Only {{ $value }} IPs available"

    - alert: KubeOVNIPExhaustionCritical
      expr: kube_ovn_subnet_available_ips < 5
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Subnet {{ $labels.subnet_name }} critically low on IPs"
        description: "Only {{ $value }} IPs available, immediate action required"
```

##### 提前扩容
```bash
# 在可用IP降到20以下时就开始扩容
AVAILABLE=$(kubectl get subnet <subnet-name> -o jsonpath='{.status.availableIPs}')

if [ "$AVAILABLE" -lt 20 ]; then
  echo "⚠️  IP即将耗尽，建议扩容"

  # 计算建议的新CIDR
  # 例如：从 /24 扩容到 /23（2倍），/22（4倍）
  echo "建议扩容到 /22 或更大的网段"
fi
```

### 第四步：检查IPAM控制器状态

#### 查看控制器日志

```bash
# 查看最近的IPAM相关日志
kubectl logs -n kube-system deploy/ovn-controller \
  | grep -i ipam | tail -50

# 查看所有错误日志
kubectl logs -n kube-system deploy/ovn-controller \
  | grep -i error | tail -50

# 实时监控
kubectl logs -n kube-system deploy/ovn-controller -f \
  | grep -E "(ipam|IP)"
```

#### 检查IP分配延迟

```bash
# 统计IP分配耗时（从Pod创建到IP分配）
# 获取Pod创建时间
CREATION_TIME=$(kubectl get pod <pod> -o jsonpath='{.metadata.creationTimestamp}')

# 获取IP分配时间（从IP资源的创建时间）
IP_TIME=$(kubectl get ip <ip-name> -o jsonpath='{.metadata.creationTimestamp}')

# 计算延迟（需要date命令）
# 示例
if command -v gdate &> /dev/null; then
  DELAY=$(gdate -d "$IP_TIME" -d "$CREATION_TIME" +%s)
else
  DELAY=$(date -d "$IP_TIME" -d "$CREATION_TIME" +%s)
fi

echo "IP分配延迟: ${DELAY}s"
```

#### 预期结果
- ✅ **正常**：IP分配延迟 < 2秒
- ⚠️  **警告**：IP分配延迟 2-10秒
- ❌ **异常**：IP分配延迟 > 10秒或失败

#### 常见错误处理

##### 错误1：`allocate ip timeout`

```bash
# 检查OVN数据库连接
ovn-appctl -t ovn_northd status/show

# 重启控制器
kubectl rollout restart deployment ovn-controller -n kube-system
```

##### 错误2：`conflicting IP`

```bash
# 检查重复IP
kubectl get ip -A -o jsonpath='{range .items[?(@.spec.ipAddress=="<IP>")]}{.metadata.name}{"\n"}{end}'

# 释放冲突的IP
kubectl delete ip <ip-name> -n <namespace>
```

### 第五步：诊断IP分配失败问题

#### 场景：Pod一直处于ContainerCreating状态

**检查Pod事件**：
```bash
kubectl get pod <pod>
kubectl describe pod <pod> | grep -A 10 Events
```

#### 常见事件及原因

##### 事件1：`Failed to allocate IP` / `no IP available`

**原因**：子网IP耗尽

**验证**：
```bash
kubectl get subnet
```

**解决**：参考"场景1：可用IP为0"的解决方案

##### 事件2：`Failed to create IP object`

**原因**：权限问题或API Server问题

**验证**：
```bash
# 检查RBAC权限
kubectl auth can-i create ip --as=system:serviceaccount:kube-system:ovn-controller

# 检查API Server
kubectl get apiservice
```

**解决**：
```bash
# 重启控制器
kubectl rollout restart deployment ovn-controller -n kube-system

# 或手动创建IP（临时）
cat <<EOF | kubectl apply -f -
apiVersion: kubeovn.io/v1
kind: IP
metadata:
  name: <pod-name>.<namespace>
  namespace: <namespace>
spec:
  ipAddress: <desired-ip>
  subnet: <subnet-name>
  podName: <pod-name>
EOF
```

##### 事件3：`IP already allocated`

**原因**：IP冲突或僵尸IP

**验证**：
```bash
kubectl get ip -A | grep <ip>
```

**解决**：
```bash
# 删除旧的IP对象
kubectl delete ip <old-ip-name> -n <namespace>

# 等待Pod重新获取IP
kubectl delete pod <pod> --grace-period=0 --force
```

## 常见问题诊断

### 问题1：删除Pod后IP未释放

**现象**：
- Pod已删除，但IP对象仍存在
- `kubectl get ip` 显示Pod名称为 `<none>`
- 新Pod无法获得IP

**原因**：垃圾回收延迟或失败

**诊断步骤**：

#### 步骤1：确认Pod已删除
```bash
kubectl get pod <pod-name>
# 应该显示 "NotFound"
```

#### 步骤2：检查IP对象状态
```bash
kubectl get ip <ip-name> -o yaml

# 查看podName字段
# 如果显示 null 或 <none>，说明是僵尸IP
```

#### 步骤3：手动清理
```bash
# 删除僵尸IP
kubectl delete ip <ip-name> -n <namespace>

# 批量清理
kubectl get ip -n <namespace> -o json \
  | jq '.items[] | select(.spec.podName == null) | .metadata.name' \
  | xargs -I {} kubectl delete ip {} -n <namespace>
```

#### 步骤4：调整垃圾回收间隔
```bash
# 编辑配置
kubectl edit configmap -n kube-system ovn-config

# 添加或修改
data:
  enable-lb: "true"
  gc-interval: "30"  # 垃圾回收间隔（秒），默认可能是60
```

### 问题2：跨节点Pod获得相同IP

**现象**：
- 两个不同节点的Pod有相同的IP
- Pod间网络异常
- IP冲突导致通信失败

**原因**：子网配置错误（不同节点使用了相同的CIDR）

**诊断步骤**：

#### 步骤1：确认IP冲突
```bash
# 查找重复IP
kubectl get ip -A -o jsonpath='{range .items[?(@.spec.ipAddress=="<IP>")]}{.metadata.name}{"\n"}{end}'

# 应该看到多个IP对象使用相同IP
```

#### 步骤2：检查子网配置
```bash
# 查看所有节点的子网配置
kubectl get subnet -o wide

# 检查是否有重复的CIDR
kubectl get subnet -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.cidrBlock}{"\n"}{end}' \
  | sort -k2 | uniq -D -f1
```

#### 步骤3：解决冲突
```bash
# 方案A：删除错误的子网
kubectl delete subnet <wrong-subnet>

# 方案B：修改子网CIDR
kubectl edit subnet <subnet-name>
# 修改 spec.cidrBlock 为不冲突的网段

# 方案C：重新分配IP
# 1. 删除冲突的Pod
kubectl delete pod <pod-1> <pod-2>

# 2. 删除冲突的IP
kubectl delete ip <ip-name-1> <ip-name-2>

# 3. 重新创建Pod
kubectl apply -f <pod-manifest.yaml>
```

### 问题3：Pod重启后IP变化

**现象**：
- Pod重启后获得不同的IP
- 应用配置或缓存失效
- 客户端连接丢失

**原因**：使用了Static IP分配模式（`default_logical_gateway: true`）

**解决方案**：

#### 方案1：切换到Dynamic模式
```bash
# 修改配置
kubectl edit configmap -n kube-system ovn-config

data:
  default-logical-gateway: "false"  # 改为false
```

**注意**：
- ⚠️  切换后需要重建所有Pod才能生效
- ⚠️  现有Pod仍会使用节点子网IP
- ⚠️  建议在维护窗口进行

#### 方案2：使用StatefulSet
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: stable-app
spec:
  serviceName: stable-app
  replicas: 3
  template:
    # ... Pod模板
```

**优势**：
- StatefulSet提供稳定的网络标识
- Pod重启后主机名不变
- 适合需要固定身份的应用

#### 方案3：使用固定IP注解
```bash
# 为Pod指定固定IP
kubectl annotate pod <pod> ovn.kubernetes.io/ip_address=<fixed-ip>
```

**限制**：
- ⚠️  需要确保IP在子网范围内且未被使用
- ⚠️  需要手动管理IP分配
- ⚠️  不适合大规模场景

## 监控和告警

### 关键指标

```yaml
# Prometheus 指标示例
kube_ovn_subnet_available_ips{subnet="ovn-default"}
kube_ovn_subnet_using_ips{subnet="ovn-default"}
kube_ovn_ip_allocation_duration_seconds{quantile="0.99"}
kube_ovn_ip_allocation_errors_total
```

### Grafana 仪表板

```json
{
  "title": "Kube-OVN IP管理",
  "panels": [
    {
      "title": "可用IP数量",
      "targets": [
        {
          "expr": "kube_ovn_subnet_available_ips"
        }
      ]
    },
    {
      "title": "IP分配延迟",
      "targets": [
        {
          "expr": "histogram_quantile(0.99, kube_ovn_ip_allocation_duration_seconds_bucket)"
        }
      ]
    },
    {
      "title": "IP分配错误率",
      "targets": [
        {
          "expr": "rate(kube_ovn_ip_allocation_errors_total[5m])"
        }
      ]
    }
  ]
}
```

## 验证修复

### 完整验证流程

```bash
# 1. 验证子网状态
kubectl get subnet
# 确认 availableIPs > 10

# 2. 测试Pod创建
kubectl run test-pod --image=nginx --restart=Never
# 等待Pod启动

# 3. 检查Pod获得IP
kubectl get pod test-pod -o jsonpath='{.status.podIP}'

# 4. 验证IP分配时间
time kubectl run test-pod-2 --image=nginx --restart=Never
# 应该在2秒内完成

# 5. 测试Pod删除和IP释放
kubectl delete pod test-pod
sleep 5
kubectl get ip | grep test-pod
# 应该找不到test-pod的IP（或podName为null）

# 6. 清理
kubectl delete pod test-pod-2
```

## 快速诊断决策树

```
IP管理问题
    │
    ├─ availableIPs == 0？
    │   ├─ 是 → 扩容CIDR或清理僵尸IP
    │   └─ 否 ↓
    │
    ├─ availableIPs < 10？
    │   ├─ 是 → 设置监控告警，准备扩容
    │   └─ 否 ↓
    │
    ├─ Pod ContainerCreating？
    │   ├─ 检查Events → "no IP available"
    │   │               → "Failed to create IP object"
    │   │               → "IP already allocated"
    │   └─ 检查控制器日志
    │
    ├─ IP未释放？
    │   ├─ 手动清理僵尸IP
    │   └─ 调整垃圾回收间隔
    │
    └─ IP冲突？
        ├─ 检查子网CIDR配置
        └─ 确保节点使用不同CIDR
```

## 相关命令参考

### 批量操作

```bash
# 批量查看所有子网的IP使用情况
kubectl get subnet -o custom-columns=NAME:.metadata.name,AVAILABLE:.status.availableIPs,USING:.status.usingIPs,TOTAL:.status.totalIPs

# 批量清理僵尸IP
kubectl get ip -A -o json \
  | jq '.items[] | select(.spec.podName == null) | "\(.metadata.namespace)/\(.metadata.name)"' \
  | xargs -I {} kubectl delete ip {}

# 批量修改Pod的固定IP
kubectl get pods -n <namespace> -o json \
  | jq '.items[] | select(.spec.nodeName == "<node>") | .metadata.name' \
  | while read pod; do
      kubectl annotate pod $pod -n <namespace> ovn.kubernetes.io/ip_address=<fixed-ip>
    done
```

### 数据库查询

```bash
# 查询OVN数据库中的IP分配
ovn-nbctl list Logical_Switch_Port | grep -A5 "addresses"

# 查询特定IP的端口
ovn-nbctl --bare --columns=name find Logical_Switch_Port "addresses=~\"<IP>\""
```
