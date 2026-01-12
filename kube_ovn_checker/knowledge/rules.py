"""
网络连通性检测规则 - Pod 流量场景

设计理念：
- 简化知识库为实用规则引擎
- 专注网络连通性检测（4个核心场景）
- AI 通过 ovn-trace + tcpdump 验证流量路径
"""

# =============================================================================
# 场景 0: 通用问候/帮助（非诊断）
# =============================================================================

GENERAL = """
## 通用查询处理

当用户发送问候语、帮助请求或其他非诊断问题时：

**适用场景**：
- 问候语：你好、hello、hi、您好、嗨
- 帮助请求：帮助、help、怎么用、如何使用、说明、文档
- 其他非网络诊断问题

**响应策略**：
1. 友好地回应用户
2. 介绍自己的能力和功能
3. 引导用户提供具体的网络问题
4. 列举可以诊断的问题类型示例

**不要**：
- 不要调用任何诊断工具
- 不要进行 T0 健康检查
- 不要尝试收集 Kubernetes 数据

**示例响应**：
你好！👋 我是 Kube-OVN 网络诊断专家。

我可以帮您诊断以下类型的网络问题：
• Pod 之间无法通信
• Service 访问异常
• 外部网络访问问题
• 网络策略不生效
• IP 地址冲突
• 节点网络问题

请告诉我您遇到的具体问题，我会帮您进行诊断。
"""

# =============================================================================
# 场景 1: Pod → Pod（同节点）
# =============================================================================

POD_TO_POD_SAME_NODE = """
## Pod 到 Pod 同节点连通性检测

### 使用场景
- 两个 Pod 在同一节点上无法通信
- 提示信息包含 "同节点"、"same node"

### 诊断步骤

**第1步：验证 Pod 状态**
```bash
kubectl get pods -o wide
# 确认两个 Pod 都在 Running 状态
# 确认两个 Pod 在同一节点
```

**第2步：执行 ovn-trace**
```bash
kubectl ko trace {source_namespace}/{source_pod} {target_ip} icmp
```

**第3步：分析 trace 输出**

正常标志：
- `ls_in_port_sec_l2` → 通过（MAC 地址验证）
- `ls_in_port_sec_ip` → 通过（IP 地址验证）
- `ls_in_acl` → 通过（访问控制列表）
- `ls_in_l2_lkup` → 找到目标 MAC
- `output("...")` → 输出到目标端口

常见问题：
1. `ls_in_port_sec_l2: drop` → MAC 地址验证失败
   - 原因：MAC 地址不匹配或未学习
   - 解决：检查 Pod 网络接口配置

2. `ls_in_port_sec_ip: drop` → IP 地址验证失败
   - 原因：IP 地址不匹配或 IP 欺骗防护触发
   - 解决：检查 Pod IP 配置

3. `ls_in_acl: drop` → NetworkPolicy 或安全组规则阻止
   - 原因：Kubernetes NetworkPolicy 阻止流量
   - 解决：检查 NetworkPolicy 配置

4. `ls_in_l2_lkup: no match` → 目标 MAC 未在逻辑交换机中学习
   - 原因：目标 Pod 可能未正常运行
   - 解决：检查目标 Pod 状态

**第4步：tcpdump 验证（可选）**
```bash
kubectl ko tcpdump {source_namespace}/{source_pod} -nn icmp -c 3
kubectl ko tcpdump {target_namespace}/{target_pod} -nn icmp -c 3
```

### 预期结论
- ✅ "流量路径正常，应该能够通信"
- ❌ "流量被 XXX 阻止：[具体原因]"
"""

# =============================================================================
# 场景 2: Pod → Pod（跨节点）
# =============================================================================

POD_TO_POD_CROSS_NODE = """
## Pod 到 Pod 跨节点连通性检测

### 使用场景
- 两个 Pod 在不同节点上无法通信
- 提示信息包含 "跨节点"、"cross node"、"不同节点"

### 诊断步骤

**第1步：验证节点信息**
```bash
kubectl get pods -o wide
# 确认两个 Pod 在不同节点
```

**第2步：执行 ovn-trace**
```bash
kubectl ko trace {source_namespace}/{source_pod} {target_ip} icmp
```

**第3步：检查隧道状态**
```bash
# 检查源节点的隧道接口
kubectl ko vsctl {source_node} show | grep genev_sys_6081

# 检查目标节点的隧道接口
kubectl ko vsctl {target_node} show | grep genev_sys_6081
```

**第4步：分析 trace 输出**

跨节点特征：
- trace 显示通过 `lr_in_ip_routing` → 路由查找
- trace 显示通过 `lr_out_gw_lkup` → 网关查找
- 最终通过隧道接口输出

常见问题：
1. trace 失败 → 路由配置错误
2. 隧道接口 DOWN → OVS 服务异常或防火墙阻止 UDP 6081
3. trace 正常但实际不通 → 物理网络问题

**第5步：tcpdump 验证**
```bash
# 在源节点的 ovn0 接口抓包
ssh {source_node} "tcpdump -i ovn0 -nn host {target_ip}"

# 在目标节点的 ovn0 接口抓包
ssh {target_node} "tcpdump -i ovn0 -nn host {target_ip}"
```

**第6步：检查防火墙（如果需要）**
```bash
# 检查 UDP 6081 端口（Geneve 隧道）
ssh {source_node} "iptables -L -v -n | grep 6081"
ssh {target_node} "iptables -L -v -n | grep 6081"
```

### 预期结论
- ✅ "流量路径正常，隧道状态 UP"
- ❌ "隧道接口 DOWN：检查 OVS 和防火墙"
- ❌ "物理网络不通：检查节点间网络"
"""

# =============================================================================
# 场景 3: Pod → Service
# =============================================================================

POD_TO_SERVICE = """
## Pod 到 Service 连通性检测

### 使用场景
- Pod 无法访问 Service（ClusterIP/NodePort/LoadBalancer）
- 提示信息包含 "service"、"svc"

### 诊断步骤

**第1步：检查 Service 配置**
```bash
kubectl get svc {service_name} -o wide
# 记录 ClusterIP 和端口

kubectl get endpoints {service_name}
# 确认后端 Pod IP 列表
```

**第2步：执行 ovn-trace**
```bash
kubectl ko trace {source_namespace}/{source_pod} {cluster_ip} tcp {port}
```

**第3步：检查 OVN Load Balancer**
```bash
kubectl ko nbctl lb-list | grep {cluster_ip}
# 确认 Load Balancer 存在且后端 IP 正确
```

**第4步：分析 trace 输出**

Service 流量特征：
- trace 显示 `lb` → Load Balancer 规则匹配
- trace 显示后端 Pod IP 被选择
- 最终转发到后端 Pod

常见问题：
1. Endpoints 为空 → Service selector 不匹配 Pod labels
2. Load Balancer 不存在 → kube-ovn-controller 未同步
3. trace 显示 drop → NetworkPolicy 阻止 Service 访问
4. trace 到后端 Pod 但后端无响应 → 后端 Pod 问题

**第5步：tcpdump 验证**
```bash
# 在源 Pod 抓包
kubectl ko tcpdump {source_namespace}/{source_pod} -nn tcp host {cluster_ip} and port {port}

# 在后端 Pod 抓包（检查流量是否到达）
kubectl ko tcpdump {backend_namespace}/{backend_pod} -nn tcp port {port}
```

**第6步：检查健康检查（如果需要）**
```bash
kubectl ko nbctl list Load_Balancer | grep -A 10 {cluster_ip}
kubectl ko sbctl list Service_Monitor | grep {service_name}
```

### 预期结论
- ✅ "Load Balancer 正常，流量转发到后端"
- ❌ "后端 Pod 异常：[具体原因]"
- ❌ "Service 配置错误：[具体原因]"
"""

# =============================================================================
# 场景 4: Pod → 外部网络
# =============================================================================

POD_TO_EXTERNAL = """
## Pod 到外部网络连通性检测

### 使用场景
- Pod 无法访问外部网络（如 8.8.8.8、api.example.com）
- 提示信息包含 "外部"、"external"、"internet"

### 诊断步骤

**第1步：执行 ovn-trace**
```bash
kubectl ko trace {source_namespace}/{source_pod} 8.8.8.8 icmp
```

**第2步：检查 NAT 配置**
```bash
# 查看 NAT 规则
kubectl ko nbctl show | grep -A 10 "NAT"

# 查看路由器路由表
kubectl ko nbctl lr-route-list ovn-cluster
```

**第3步：检查 Gateway Pods**
```bash
kubectl get pods -n kube-ovn -l app=ovn-gateway -o wide
# 确认 Gateway Pods 在每个节点都运行
```

**第4步：分析 trace 输出**

外部网络流量特征：
- trace 显示 `lr_in_ip_routing` → 路由查找
- trace 显示 `ct_snat` → SNAT 规则匹配
- trace 显示通过物理接口输出

常见问题：
1. trace 无 NAT 规则 → Subnet 的 NAT 配置未启用
2. Gateway Pod 异常 → kube-ovn-controller 问题
3. trace 正常但无法访问 → 节点默认网关问题
4. DNS 解析失败 → CoreDNS 问题

**第5步：tcpdump 验证**
```bash
# 在源 Pod 抓包
kubectl ko tcpdump {source_namespace}/{source_pod} -nn host 8.8.8.8

# 在节点的物理接口抓包（查看 SNAT 后的源地址）
ssh {node} "tcpdump -i {physical-interface} -nn host 8.8.8.8"
```

**第6步：检查节点路由**
```bash
ssh {node} "ip route show"
# 确认默认路由存在
```

**第7步：DNS 检查（如果是域名访问）**
```bash
kubectl ko tcpdump {source_namespace}/{source_pod} -nn udp port 53
# 检查 DNS 请求和响应
```

### 预期结论
- ✅ "NAT 规则正常，流量可以访问外部网络"
- ❌ "Gateway 异常：检查 kube-ovn-controller"
- ❌ "NAT 配置缺失：检查 Subnet 配置"
- ❌ "节点路由问题：检查默认网关"
"""

# =============================================================================
# 规则匹配和导出
# =============================================================================

def get_all_rules() -> dict:
    """返回所有诊断规则"""
    return {
        "general": GENERAL,
        "pod_to_pod": POD_TO_POD_SAME_NODE,
        "pod_to_pod_cross_node": POD_TO_POD_CROSS_NODE,
        "pod_to_service": POD_TO_SERVICE,
        "pod_to_external": POD_TO_EXTERNAL,
    }


# 全局分类器实例（懒加载）
_classifier = None

def match_rule(user_query: str) -> tuple:
    """使用 LLM 智能分类查询到诊断场景

    Args:
        user_query: 用户的自然语言查询

    Returns:
        tuple: (category: str, confidence: float)
            - category: 匹配的规则名称（5个场景之一）
            - confidence: 置信度（0-1，基于 Transformer softmax 概率）
    """
    global _classifier

    if _classifier is None:
        from kube_ovn_checker.classifier import IntelligentClassifier
        _classifier = IntelligentClassifier()

    try:
        result = _classifier.classify(user_query)
        return (result.category, result.confidence)
    except ValueError as e:
        # API Key 未配置
        import warnings
        warnings.warn(f"⚠️ LLM API Key 未配置，请设置 OPENAI_API_KEY 环境变量: {e}")
        return ("general", 0.0)  # 返回通用场景，引导用户
    except Exception as e:
        # 其他 LLM 调用失败
        import warnings
        warnings.warn(f"LLM 分类失败，返回通用场景: {e}")
        return ("general", 0.0)  # 更合理的默认：通用/帮助


def get_rule_by_name(rule_name: str) -> str:
    """根据规则名称获取规则内容

    Args:
        rule_name: 规则名称

    Returns:
        str: 规则内容，如果不存在则返回空字符串
    """
    rules = get_all_rules()
    return rules.get(rule_name, "")
