#!/bin/bash

# Docker 配置自动更新脚本
# 此脚本用于在容器外重启 Docker 服务

echo "🔄 重启 Docker 服务以应用新配置..."

# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 重启 Docker 服务
sudo systemctl restart docker

# 检查 Docker 服务状态
if systemctl is-active --quiet docker; then
    echo "✅ Docker 服务已成功重启"
    echo ""
    echo "📋 验证配置:"
    docker info | grep -A 10 "Registry Mirrors" || echo "未找到镜像源配置"
else
    echo "❌ Docker 服务重启失败"
    exit 1
fi

