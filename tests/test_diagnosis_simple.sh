#!/bin/bash
# 快速测试诊断流程

echo "测试问题: Pod ping 不通问题"
echo ""

./kube-ovn-checker "帮我看看什么pod kube-system kube-ovn-pinger-qrfqd ping不通 kube-system kube-ovn-pinger-rmqjg"
