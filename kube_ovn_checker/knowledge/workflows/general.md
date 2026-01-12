---
# 通用诊断工作流
triggers:
  - 诊断
  - 排查
  - 问题
  - 故障
  - 检查

# 分类：通用基础文档
category: general

# 优先级：30（工作流文档）
priority: 30
---

# Kube-OVN 通用诊断工作流

## 诊断方法论

### 1. 理解问题

#### 明确症状
- 用户报告的具体问题是什么？
- 问题的表现形式是什么？（错误消息、异常行为、性能下降）
- 问题是持续的还是间歇性的？

#### 确认范围
- 影响范围：单个Pod、整个节点、集群级别
- 时间范围：何时开始出现？是否有变化？
- 环境信息：Kube-OVN版本、Kubernetes版本

#### 收集上下文
- 最近是否有配置变更？
- 是否有相关的操作（升级、扩容、配置修改）？
- 其他类似环境是否有相同问题？

### 2. 收集数据

#### T0健康检查（已自动完成）
- 控制器状态（ovn-controller、ovn-northd）
- 节点状态（网络配置、OVS桥接）
- 子网状态（IP分配、CIDR配置）

#### 主动数据收集
**相关资源状态**：
```bash
# Pod 状态
kubectl get pods -A
kubectl describe pod <pod-name>

# Service 和 NetworkPolicy
kubectl get svc -A
kubectl get networkpolicy -A

# OVN 资源
kubectl get subnet -A
kubectl get ip -A
```

**日志收集**：
```bash
# 控制器日志
kubectl logs -n kube-system deploy/ovn-controller --tail=100

# 节点日志
kubectl logs -n kube-system daemonset/ovs-ovn --tail=100

# Pod 事件
kubectl get events --sort-by='.lastTimestamp'
```

### 3. 分析推理

#### 形成假设
基于症状和证据，提出可能的原因：
- 网络配置问题？
- 资源耗尽（IP、端口、连接数）？
- 组件故障（控制器、OVS、数据库）？
- 外部因素（防火墙、SELinux、MTU）？

#### 验证假设
使用诊断工具收集证据：
```bash
# 网络连通性
kubectl exec <pod> -- ping <target-ip>

# OVN 逻辑路径
ovn-trace --detach ...

# 实际流量
tcpdump -i <interface> -nn host <target-ip>
```

#### 排除无关因素
- 检查其他Pod是否有相同问题（是否隔离）
- 检查其他节点是否有相同问题（是否节点特定）
- 测试基本功能是否正常（baseline）

### 4. 定位根因

#### 识别最可能的原因
综合所有证据，确定：
- 直接原因：直接导致问题的因素
- 根本原因：为什么会出现这个原因
- 触发条件：什么情况下会触发

#### 收集支持性证据
- 日志中的错误消息
- 配置与期望的差异
- 网络行为的异常模式

#### 验证根因
通过以下方式验证：
- 修复问题后症状消失
- 重现问题
- 对比正常和异常环境的差异

### 5. 提供解决方案

#### 可操作的修复步骤
提供清晰的步骤：
1. 临时缓解措施（快速恢复）
2. 根本修复（彻底解决）
3. 预防措施（避免再次发生）

#### 命令示例
每个步骤包含具体的命令：
```bash
# 示例
kubectl edit subnet <subnet-name>
# 修改 spec.cidrBlock
```

#### 验证方法
修复后如何确认问题已解决：
```bash
# 验证连通性
kubectl exec <pod> -- curl http://<target-ip>:<port>

# 检查状态
kubectl get pod <pod>
```

## 常用诊断命令

### OVN 相关
```bash
# 查看 OVN 数据库状态
ovn-nbctl show
ovn-sbctl show

# 查看逻辑交换机/路由器
ovn-nbctl ls-list
ovn-nbctl lr-list

# 查看端口
ovn-nbctl lsp-list <logical-switch>
```

### OVS 相关
```bash
# 查看 OVS 桥接状态
ovs-vsctl show

# 查看流表
ovs-ofctl dump-flows br-int

# 查看端口
ovs-vsctl list-ports br-int
```

### 网络诊断
```bash
# Ping 测试
kubectl exec <pod> -- ping -c 3 <target-ip>

# 端口连通性
kubectl exec <pod> -- nc -zv <target-ip> <port>

# DNS 解析
kubectl exec <pod> -- nslookup <hostname>
```

### 资源状态
```bash
# 查看 IP 分配
kubectl get subnet
kubectl describe subnet <subnet-name>

# 查看已分配的IP
kubectl get ip -A

# 查看网络策略
kubectl get networkpolicy -A
```

## 诊断检查清单

### 基础检查
- [ ] 控制器是否健康？
- [ ] 节点网络是否正常？
- [ ] 子网IP是否充足？
- [ ] 是否有相关错误日志？

### 网络连通性
- [ ] Pod 能否 ping 通其他 Pod？
- [ ] Pod 能否访问 Service？
- [ ] Pod 能否访问外部网络？
- [ ] 跨节点通信是否正常？

### 配置验证
- [ ] MTU 配置是否一致？
- [ ] NetworkPolicy 是否有冲突？
- [ ] CIDR 配置是否正确？
- [ ] IPAM 配置是否正确？

### 性能分析
- [ ] 是否有大量丢包？
- [ ] 延迟是否异常？
- [ ] 连接数是否超限？
- [ ] CPU/内存是否充足？

## 通用排查思路

### 问题：Pod 无法访问外部网络
**可能原因**：
1. NAT 配置问题
2. 防火墙规则
3. 路由配置错误

**排查步骤**：
```bash
# 1. 检查 NAT 规则
iptables -t nat -L -n -v | grep KUBE-OVN

# 2. 测试基础连通性
kubectl exec <pod> -- ping 8.8.8.8

# 3. 检查路由
ip route show
```

### 问题：Pod间网络不通
**可能原因**：
1. OVN 流表问题
2. NetworkPolicy 阻止
3. IP 地址冲突

**排查步骤**：
```bash
# 1. ovn-trace 验证逻辑路径
ovn-trace --detach ...

# 2. tcpdump 验证实际流量
tcpdump -i <interface> -nn host <target-ip>

# 3. 检查 NetworkPolicy
kubectl get networkpolicy
```

### 问题：Pod 无法启动
**可能原因**：
1. IP 地址耗尽
2. 网络插件未就绪
3. CNI 配置错误

**排查步骤**：
```bash
# 1. 检查子网 IP
kubectl get subnet

# 2. 查看 Pod 事件
kubectl describe pod <pod>

# 3. 检查 CNI
ls -la /etc/cni/net.d/
```

## 最佳实践

### 1. 系统化诊断
- 遵循上述诊断流程
- 不要跳跃，逐步验证
- 记录每一步的结果

### 2. 收集充分信息
- 日志：控制器、OVS、Pod
- 配置：网络配置、资源定义
- 状态：当前状态、历史变更

### 3. 验证假设
- 使用工具验证，不要猜测
- 收集支持性证据
- 考虑多个可能原因

### 4. 提供可操作的解决方案
- 步骤清晰、可执行
- 包含具体的命令
- 说明如何验证修复

### 5. 文档化
- 记录问题和解决方案
- 更新知识库
- 分享经验给团队
