---
triggers:
  - 网络
  - ping
  - 连通
  - 连接
  - 不通
  - timeout
  - 无法访问
  - 通信
category: pod_to_pod
priority: 100
---

# Pod间网络连通性诊断工作流

## 概述

Pod间网络连通性问题是Kube-OVN中最常见的诊断场景之一。本工作流提供系统化的诊断步骤，帮助快速定位网络不通的根本原因。

**常见症状**：
- Pod间无法ping通
- 应用连接超时
- 跨节点通信失败
- Service无法访问Pod

## 诊断步骤

### 第一步：理解问题

#### 明确症状
1. **源Pod和目标**：
   ```bash
   # 源 Pod 信息
   kubectl get pod <source-pod> -o wide

   # 目标 Pod 或 Service
   kubectl get pod <target-pod> -o wide
   kubectl get svc <target-service>
   ```

2. **问题类型**：
   - Pod间通信？（Pod ↔ Pod）
   - Service访问？（Pod ↔ Service）
   - 外部访问？（Pod ↔ External）
   - 跨节点通信？（不同节点的Pod）

3. **错误表现**：
   - `ping: connect: Network is unreachable`
   - `Connection timed out`
   - `No route to host`
   - `Connection refused`

#### 确认环境
```bash
# Kube-OVN 版本
kubectl get configmap -n kube-system ovn-config -o jsonpath='{.data.VERSION}'

# 节点分布
kubectl get pod <source-pod> -o jsonpath='{.spec.nodeName}'
kubectl get pod <target-pod> -o jsonpath='{.spec.nodeName}'

# 子网信息
kubectl get subnet
kubectl describe subnet <subnet-name>
```

### 第二步：逻辑路径验证（ovn-trace）

#### 执行 ovn-trace

**场景1：同节点Pod间通信**
```bash
# 获取Pod信息
SOURCE_POD="pod-a"
TARGET_POD="pod-b"
TARGET_IP="<target-pod-ip>"

# 执行 ovn-trace
ovn-trace --detach \
  --lb-db 'unix:/var/run/openvswitch/ovnnb_db.sock' \
  --db 'unix:/var/run/openvswitch/ovnsb_db.sock' \
  <logical-switch> \
  "inport==\"$SOURCE_POD\" && eth.dst==$TARGET_IP"
```

**场景2：跨节点Pod间通信**
```bash
# 获取逻辑路由器
LOGICAL_ROUTER=$(ovn-nbctl lr-list | grep <node-name> | awk '{print $1}')

# 执行 ovn-trace（跨节点）
ovn-trace --detach \
  --lb-db 'unix:/var/run/openvswitch/ovnnb_db.sock' \
  --db 'unix:/var/run/openvswitch/ovnsb_db.sock' \
  $LOGICAL_ROUTER \
  "inport==\"$SOURCE_POD\" && eth.dst==$TARGET_IP"
```

#### 关键输出检查

**正常输出示例**：
```
# 输出流表处理过程
ingress(dp="tnl-port1", inport="pod-a")
  ...
output("pod-b");  # ✅ 最终出口到目标Pod
```

**异常输出示例**：
```
# 情况1：输出到未知端口
output("xxx");  # ❌ xxx 不是目标Pod

# 情况2：包含错误
error: "No logical router found"  # ❌ 逻辑路由器问题

# 情况3：输出到 drop
output("drop");  # ❌ 被安全规则丢弃
```

#### 预期结果
- ✅ **正常**：`output: "<target-pod>"` 或 `output: "<target-port>"`
- ❌ **异常**：`output: "xxx"`（非目标）或包含 `error:`

### 第三步：实际流量验证（tcpdump）

#### 在源Pod的宿主机抓包

```bash
# 确定源Pod的宿主机
SOURCE_NODE=$(kubectl get pod <source-pod> -o jsonpath='{.spec.nodeName}')

# 获取Pod的veth设备（在宿主机上执行）
kubectl exec <source-pod> -- ip addr show  # 查看Pod内的接口
# 然后在宿主机上找到对应的veth
kubectl exec <source-pod> -- cat /sys/class/net/eth0/iflink  # 获取ifindex
# 在宿主机上
ip link | grep <ifindex>  # 找到veth设备，如 veth1234

# 抓包（在源Pod的宿主机上）
tcpdump -i veth1234 -nn host <target-ip> -c 5
```

#### 在目标Pod的宿主机抓包

```bash
# 类似步骤，在目标Pod的宿主机上
tcpdump -i <target-veth> -nn host <source-ip> -c 5
```

#### 关键检查

**正常情况**：
```
# 发送方
10:24:35.123 IP 10.16.0.5 > 10.16.0.6: ICMP echo request

# 接收方
10:24:35.124 IP 10.16.0.5 > 10.16.0.6: ICMP echo request
10:24:35.125 IP 10.16.0.6 > 10.16.0.5: ICMP echo reply
```

**异常情况**：
```
# 情况1：只有request，没有reply
10:24:35.123 IP 10.16.0.5 > 10.16.0.6: ICMP echo request
# ❌ 无后续包

# 情况2：完全无包
# ❌ 发送方无输出，说明包未发出

# 情况3：有reply但被丢弃
10:24:35.125 IP 10.16.0.6 > 10.16.0.5: ICMP echo reply
# ❌ 但发送方未收到
```

#### 预期结果
- ✅ **正常**：发送方有request，接收方有request+reply
- ❌ **异常**：只有request无reply，或完全无包

### 第四步：流表验证

#### 检查OpenFlow流表

```bash
# 查看网桥流表
ovs-ofctl dump-flows br-int | grep <target-ip>

# 查看特定端口的流表
ovs-ofctl dump-flows br-int | grep in_port=<port-num>
```

#### 关键检查

**正常流表示例**：
```
# 匹配目标IP的流表
priority=50,ip,nw_dst=10.16.0.6 actions=output:5
#                          ^^^^^^^^^^
#                          目标IP
#                          ^^^^^^^^^^^
#                          输出端口（对应目标Pod）
```

**异常流表示例**：
```
# 情况1：没有匹配流表
# ❌ 完全没有输出

# 情况2：优先级太低，被其他规则覆盖
priority=1,ip,nw_dst=10.16.0.0/24 actions=drop
priority=50,ip,nw_dst=10.16.0.6 actions=output:5
#            ^^^^
#            ❌ 不会匹配到这条规则

# 情况3：动作错误
priority=50,ip,nw_dst=10.16.0.6 actions=drop
#                                  ^^^^^
#                                  ❌ 应该是 output:<port>
```

#### 重置流表（如果需要）
```bash
# ⚠️ 谨慎操作！仅在其他方法都失败时使用
# 重启 OVS 守护进程会重新生成流表
systemctl restart openvswitch-switch

# 或者重启 ovn-controller
kubectl rollout restart daemonset ovn-controller -n kube-system
```

### 第五步：检查其他可能因素

#### NetworkPolicy 检查
```bash
# 查看所有 NetworkPolicy
kubectl get networkpolicy -A

# 检查是否有策略阻止
kubectl describe networkpolicy <policy-name>
```

#### MTU 检查
```bash
# 检查Pod的MTU
kubectl exec <pod> -- ip link show eth0 | grep mtu

# 检查宿主机的MTU
ip link show ovs0 | grep mtu
ip link show <vxlan_sys> | grep mtu

# 统一MTU（如果不一致）
# 编辑配置
kubectl edit configmap -n kube-system ovn-config
# 设置 mtu: 1400
```

#### 防火墙规则
```bash
# 检查 iptables 规则
iptables -L -n -v | grep KUBE-OVN

# 检查是否有 DROP 规则
iptables -L -n -v | grep DROP
```

## 常见问题诊断

### 问题1：ovn-trace显示正常，但实际不通

**现象**：
- ovn-trace 输出 `output: "<target-pod>"`（正常）
- tcpdump 显示只有request，没有reply（异常）

**可能原因**：

#### 原因1：OVS流表未同步
```bash
# 检查 OVS 连接状态
ovs-vsctl show

# 检查 ovn-controller 状态
kubectl get pod -n kube-system | grep ovn-controller

# 重启 ovn-controller
kubectl rollout restart daemonset ovn-controller -n kube-system
```

#### 原因2：网卡或驱动问题
```bash
# 检查网卡状态
ip link show ovs0
ethtool -i ovs0

# 检查 OVS 内核模块
lsmod | grep openvswitch
modinfo openvswitch

# 重启 OVS
systemctl restart openvswitch-switch
```

#### 原因3：MTU问题导致包被丢弃
```bash
# 检查 MTU 是否一致
kubectl exec <source-pod> -- ip link show eth0 | grep mtu
kubectl exec <target-pod> -- ip link show eth0 | grep mtu
ip link show ovs0 | grep mtu

# 诊断：抓包看是否有 fragmentation
tcpdump -i <interface> -nn -v host <target-ip>
# 如果看到 "packet exceeded MTU" 则是MTU问题
```

### 问题2：ovn-trace失败，显示 output to unknown port

**现象**：
```
output: "xxx"  # xxx 不是目标Pod
# 或
error: "Cannot find logical switch port"
```

**可能原因**：

#### 原因1：目标Pod不在同一个子网
```bash
# 检查Pod的子网
kubectl get pod <target-pod> -o jsonpath='{.metadata.annotations.ovn\.kubernetes\.io/logical_switch}'

# 检查子网配置
kubectl get subnet
kubectl describe subnet <subnet-name>
```

#### 原因2：逻辑交换机配置错误
```bash
# 查看逻辑交换机
ovn-nbctl ls-list
ovn-nbctl lsp-list <logical-switch>

# 检查Pod端口是否存在
ovn-nbctl lsp-list <logical-switch> | grep <pod-name>

# 手动添加端口（如果缺失）
ovn-nbctl lsp-add <logical-switch> <pod-name>
ovn-nbctl lsp-set-addresses <pod-name> "<mac> <ip>"
```

#### 原因3：OVN数据库数据不一致
```bash
# 检查数据库连接
ovn-appctl -t ovn_northd status/show

# 重启 ovn-northd
kubectl rollout restart deployment ovn-northd -n kube-system

# 重新同步数据库
ovn-nbctl sync
ovn-sbctl sync
```

### 问题3：tcpdump显示只有request没有reply

**现象**：
- 发送方：有request包
- 接收方：有request包，但无reply包
- ovn-trace：可能正常或异常

**可能原因**：

#### 原因1：目标Pod未运行或无响应
```bash
# 检查Pod状态
kubectl get pod <target-pod>
kubectl describe pod <target-pod>

# 检查Pod日志
kubectl logs <target-pod> --tail=50

# 检查Pod内部网络
kubectl exec <target-pod> -- ip addr
kubectl exec <target-pod> -- ip route
```

#### 原因2：防火墙规则阻止
```bash
# 检查 iptables
iptables -L -n -v | grep <target-ip>

# 检查 NetworkPolicy
kubectl get networkpolicy -A
kubectl describe networkpolicy <policy-name>

# 暂时测试：删除 NetworkPolicy
kubectl delete networkpolicy <policy-name>
```

#### 原因3：IP地址冲突
```bash
# 检查是否有重复IP
kubectl get ip -A | grep <target-ip>

# 如果有冲突，释放并重新分配
kubectl delete ip <ip-name>
kubectl delete pod <pod>  # Pod会重新获取IP
```

#### 原因4：目标Pod的服务未监听
```bash
# 测试Pod内部服务
kubectl exec <source-pod> -- curl -v http://<target-ip>:<port>

# 在目标Pod中检查监听端口
kubectl exec <target-pod> -- netstat -tlnp
kubectl exec <target-pod> -- ss -tlnp
```

## 验证修复

### 完整验证流程

```bash
# 1. 重新测试连通性
kubectl exec <source-pod> -- ping -c 3 <target-ip>

# 2. 测试服务访问
kubectl exec <source-pod> -- curl http://<service-name>:<port>

# 3. 检查端到端延迟
kubectl exec <source-pod> -- ping -c 10 <target-ip> | tail -1

# 4. 验证持久性
# 多次测试，确保问题不是间歇性的
for i in {1..10}; do
  kubectl exec <source-pod> -- ping -c 1 <target-ip> > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "Test $i: PASS"
  else
    echo "Test $i: FAIL"
  fi
done
```

## 快速诊断决策树

```
Pod间网络不通
    │
    ├─ ovn-trace 失败？
    │   ├─ 是 → 检查OVN配置、数据库、子网
    │   └─ 否 ↓
    │
    ├─ tcpdump 只有request？
    │   ├─ 是 → 检查目标Pod状态、防火墙、IP冲突
    │   └─ 否 ↓
    │
    ├─ tcpdump 完全无包？
    │   ├─ 是 → 检查源Pod配置、OVS流表
    │   └─ 否 ↓
    │
    └─ ovn-trace正常，实际不通
        ├─ 检查OVS流表同步
        ├─ 检查网卡驱动
        └─ 检查MTU配置
```

## 相关命令参考

### ovn-trace 高级用法
```bash
# 带详细输出的 ovn-trace
ovn-trace --detach --verbose ...

# 只显示最终输出
ovn-trace --detach --minimal ...

# 保存输出到文件
ovn-trace --detach ... 2>&1 | tee ovn-trace-output.txt
```

### tcpdump 高级用法
```bash
# 抓取特定协议
tcpdump -i <interface> -nn icmp  # 只抓ICMP
tcpdump -i <interface> -nn tcp   # 只抓TCP

# 抓取并保存到文件
tcpdump -i <interface> -nn -w capture.pcap host <target-ip>

# 读取pcap文件
tcpdump -r capture.pcap -nn
```

### OVS 流表分析
```bash
# 统计流表数量
ovs-ofctl dump-flows br-int | wc -l

# 查找特定动作的流表
ovs-ofctl dump-flows br-int | grep "actions=drop"

# 按优先级排序
ovs-ofctl dump-flows br-int | sort -t',' -k2 -n
```
