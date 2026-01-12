"""
Kube-OVN 网络诊断框架流程图

展示整个诊断系统的工作流程
"""

from graphviz import Digraph

def create_diagnosis_flowchart():
    """创建诊断流程图"""

    dot = Digraph(comment='Kube-OVN 网络诊断框架', format='png')
    dot.attr(rankdir='TB', fontname='Arial')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
    dot.attr('edge', fontname='Arial', fontsize='10')

    # 样式定义
    style_user = {'fillcolor': '#E8F5E9', 'shape': 'ellipse'}  # 绿色
    style_system = {'fillcolor': '#E3F2FD', 'shape': 'box'}  # 蓝色
    style_agent = {'fillcolor': '#FFF3E0', 'shape': 'diamond'}  # 橙色
    style_tool = {'fillcolor': '#F3E5F5', 'shape': 'box'}  # 紫色
    style_decision = {'fillcolor': '#FFEBEE', 'shape': 'diamond'}  # 红色
    style_result = {'fillcolor': '#E0F2F1', 'shape': 'box'}  # 青色

    # ===== 1. 用户输入层 =====
    with dot.subgraph(name='cluster_input') as c:
        c.attr(label='用户输入层', style='rounded', color='#grey60')
        c.node('user_input', '用户查询\n例如: Pod A 访问 Pod B 不通', **style_user)
        c.node('t0_check', 'T0 快速健康检查\n(10秒)', **style_system)

    # ===== 2. 规则匹配层 =====
    with dot.subgraph(name='cluster_rules') as c:
        c.attr(label='规则匹配层', style='rounded', color='#grey60')
        c.node('rule_matching', '诊断规则匹配\n分析查询类型和目标', **style_system)
        c.node('rule_base', '规则库\n• Pod→Pod (同节点)\n• Pod→Pod (跨节点)\n• Pod→Service\n• Pod→External', **style_system)

    # ===== 3. Agent 决策层 =====
    with dot.subgraph(name='cluster_agent') as c:
        c.attr(label='Agent 决策层 (LangGraph ReAct)', style='rounded', color='#grey60')
        c.node('agent_brain', 'LLM Agent\n(GPT-4o)', **style_agent)
        c.node('knowledge', '注入诊断规则\n包含 ovn-trace/tcpdump 步骤', **style_system)
        c.node('plan', '制定诊断计划\n基于 T0 结果和规则', **style_agent)

    # ===== 4. 工具执行层 =====
    with dot.subgraph(name='cluster_tools') as c:
        c.attr(label='工具执行层', style='rounded', color='#grey60')
        c.node('tool_ovn_trace', 'ovn-trace\n逻辑路径分析', **style_tool)
        c.node('tool_tcpdump', 'tcpdump\n实际流量验证', **style_tool)
        c.node('tool_ovn_db', 'OVN DB 查询\n配置验证', **style_tool)
        c.node('tool_logs', '日志分析\nController/CNI', **style_tool)
        c.node('tool_resources', 'K8s 资源查询\nPod/Node/Service', **style_tool)

    # ===== 5. 决策循环 =====
    with dot.subgraph(name='cluster_decision') as c:
        c.attr(label='决策循环', style='rounded', color='#grey60')
        c.node('analyze', '分析结果\n更新假设', **style_agent)
        c.node('decision', '问题解决?', **style_decision)
        c.node('max_rounds', '达到最大轮次?', **style_decision)

    # ===== 6. 输出层 =====
    with dot.subgraph(name='cluster_output') as c:
        c.attr(label='输出层', style='rounded', color='#grey60')
        c.node('diagnosis', '诊断结论\n根因分析', **style_result)
        c.node('solution', '解决建议\n可操作步骤', **style_result)
        c.node('evidence', '证据链\n支撑结论的数据', **style_result)

    # ===== 连接关系 =====

    # 输入层 → 规则匹配
    dot.edge('user_input', 't0_check', label='提交查询')
    dot.edge('t0_check', 'rule_matching', label='T0 数据')

    # 规则匹配
    dot.edge('rule_matching', 'rule_base', label='查询规则库')
    dot.edge('rule_base', 'rule_matching', label='返回匹配规则', style='dashed')
    dot.edge('rule_matching', 'agent_brain', label='注入规则+T0数据')

    # Agent 初始化
    dot.edge('agent_brain', 'knowledge', label='加载诊断规则')
    dot.edge('knowledge', 'plan', label='制定初始计划')

    # 工具调用循环
    dot.edge('plan', 'tool_ovn_trace', label='优先使用\n逻辑分析')
    dot.edge('plan', 'tool_tcpdump', label='验证实际流量')
    dot.edge('plan', 'tool_ovn_db', label='检查配置')
    dot.edge('plan', 'tool_logs', label='分析日志')
    dot.edge('plan', 'tool_resources', label='查询资源')

    # 工具 → 分析
    dot.edge('tool_ovn_trace', 'analyze', label='返回结果')
    dot.edge('tool_tcpdump', 'analyze', label='返回结果')
    dot.edge('tool_ovn_db', 'analyze', label='返回结果')
    dot.edge('tool_logs', 'analyze', label='返回结果')
    dot.edge('tool_resources', 'analyze', label='返回结果')

    # 分析 → 决策
    dot.edge('analyze', 'decision', label='形成新假设')

    # 决策分支
    dot.edge('decision', 'diagnosis', label='是\n找到根因')
    dot.edge('decision', 'max_rounds', label='否\n继续诊断')
    dot.edge('max_rounds', 'plan', label='否\n< 10轮\n调用下一个工具')
    dot.edge('max_rounds', 'diagnosis', label='是\n达到轮次上限\n输出当前结论')

    # 输出
    dot.edge('diagnosis', 'solution', label='生成建议')
    dot.edge('diagnosis', 'evidence', label='整理证据')

    return dot


def create_architecture_overview():
    """创建系统架构总览图"""

    dot = Digraph(comment='Kube-OVN 诊断系统架构', format='png')
    dot.attr(rankdir='LR', fontname='Arial')
    dot.attr('node', shape='component', fontname='Arial', fontsize='11')
    dot.attr('edge', fontname='Arial', fontsize='9')

    # 样式
    style_input = {'fillcolor': '#E8F5E9', 'style': 'filled'}
    style_core = {'fillcolor': '#E3F2FD', 'style': 'filled'}
    style_data = {'fillcolor': '#FFF3E0', 'style': 'filled'}
    style_output = {'fillcolor': '#E0F2F1', 'style': 'filled'}

    # 主要组件
    dot.node('cli', 'CLI 入口\nkube-ovn-checker', **style_input)
    dot.node('analyzer', 'LLM Agent 分析器\nLangGraph ReAct', **style_core)
    dot.node('rules', '规则引擎\n4种网络场景', **style_data)
    dot.node('tools', '工具集\n12个诊断工具', **style_core)
    dot.node('collector', '资源收集器\nK8s API', **style_data)
    dot.node('k8s', 'Kubernetes 集群\nPod/Node/Service', **style_data)
    dot.node('output', '诊断报告\n根因+建议+证据', **style_output)

    # 连接
    dot.edge('cli', 'analyzer', label='用户查询')
    dot.edge('analyzer', 'rules', label='匹配规则')
    dot.edge('rules', 'analyzer', label='注入知识', dir='both')
    dot.edge('analyzer', 'tools', label='调用工具')
    dot.edge('tools', 'collector', label='请求数据')
    dot.edge('collector', 'k8s', label='查询资源')
    dot.edge('tools', 'analyzer', label='返回结果', dir='both')
    dot.edge('analyzer', 'output', label='生成报告')

    # 添加说明
    with dot.subgraph(name='cluster_legend') as c:
        c.attr(label='关键特性', rank='sink', style='dashed')
        c.node('feature1', '✓ 渐进式诊断: T0 → T1 → T2')
        c.node('feature2', '✓ ReAct 模式: 观察→推理→行动')
        c.node('feature3', '✓ 规则驱动: 网络场景规则')
        c.node('feature4', '✓ 证据导向: 每个结论有数据支撑')

    return dot


def create_data_flow():
    """创建数据流图"""

    dot = Digraph(comment='诊断数据流', format='png')
    dot.attr(rankdir='TB', fontname='Arial')
    dot.attr('node', shape='note', fontname='Arial', fontsize='10')
    dot.attr('edge', fontname='Arial', fontsize='9')

    # 数据流节点
    dot.node('input', '用户输入\n"Pod A → Pod B 不通"', fillcolor='#E8F5E9')
    dot.node('t0', 'T0 数据\n• Pod 状态\n• Node 状态\n• Controller 状态', fillcolor='#E3F2FD')
    dot.node('rule', '诊断规则\n包含 ovn-trace/tcpdump 步骤', fillcolor='#FFF3E0')
    dot.node('context', 'Agent 上下文\n系统消息 + T0 + 规则', fillcolor='#F3E5F5')
    dot.node('tool_result', '工具结果\novn-trace 输出\ntcpdump 输出\nOVN DB 数据', fillcolor='#E3F2FD')
    dot.node('reasoning', 'LLM 推理\n分析结果 → 形成假设', fillcolor='#FFE0B2')
    dot.node('next_action', '下一步行动\n选择工具或结束', fillcolor='#FFE0B2')
    dot.node('output', '最终诊断\n根因分析\n解决建议\n证据链', fillcolor='#E0F2F1')

    # 连接
    dot.edge('input', 't0', label='触发健康检查')
    dot.edge('t0', 'rule', label='匹配场景')
    dot.edge('rule', 'context', label='注入规则')
    dot.edge('context', 'reasoning', label='初始化 Agent')
    dot.edge('reasoning', 'next_action', label='决策')
    dot.edge('next_action', 'tool_result', label='调用工具', dir='both')
    dot.edge('tool_result', 'reasoning', label='分析\n循环 (最多10轮)', style='dashed', constraint='false')
    dot.edge('reasoning', 'output', label='达到收敛条件')

    return dot


if __name__ == '__main__':
    # 生成三个流程图
    print("生成诊断流程图...")
    diag1 = create_diagnosis_flowchart()
    diag1.render('kube_ovn_checker_diagnosis_flowchart', cleanup=True, format='png')
    print("✓ 诊断流程图已保存: kube_ovn_checker_diagnosis_flowchart.png")

    print("\n生成系统架构图...")
    diag2 = create_architecture_overview()
    diag2.render('kube_ovn_checker_architecture', cleanup=True, format='png')
    print("✓ 系统架构图已保存: kube_ovn_checker_architecture.png")

    print("\n生成数据流图...")
    diag3 = create_data_flow()
    diag3.render('kube_ovn_checker_data_flow', cleanup=True, format='png')
    print("✓ 数据流图已保存: kube_ovn_checker_data_flow.png")

    print("\n✅ 所有流程图生成完成!")
