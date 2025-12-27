#!/bin/bash

# Docker 镜像加速器测试和配置脚本
# 根据 https://gist.githubusercontent.com/y0ngb1n/7e8f16af3242c7815e7ca2f0833d3ea6/raw/57d744ea66b5cec7e43cc56af8437ef622b8bd6d/docker-registry-mirrors.md

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 镜像加速器列表（从文档中提取的可用加速器）
MIRRORS=(
    "https://dockerproxy.com"
    "https://docker.mirrors.ustc.edu.cn"
    "https://docker.nju.edu.cn"
    "https://docker.m.daocloud.io"
    "https://mirror.baidubce.com"
    "https://mirror.iscas.ac.cn"
)

echo -e "${YELLOW}开始测试 Docker 镜像加速器...${NC}\n"

# 测试函数：检查镜像加速器是否可用
test_mirror() {
    local mirror=$1
    
    echo -n "测试 ${mirror} ... "
    
    # 方法1: 检查 HTTP 响应（检查 API 端点）
    # 尝试访问 /v2/ 端点
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 --connect-timeout 5 "${mirror}/v2/" 2>/dev/null || echo "000")
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "401" ] || [ "$http_code" = "404" ]; then
        # 200/401/404 都表示服务可用（401 需要认证，404 是正常的）
        echo -e "${GREEN}✓ 可用 (HTTP $http_code)${NC}"
        return 0
    fi
    
    # 方法2: 尝试访问根路径
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 --connect-timeout 5 "${mirror}" 2>/dev/null || echo "000")
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "301" ] || [ "$http_code" = "302" ] || [ "$http_code" = "401" ] || [ "$http_code" = "404" ]; then
        echo -e "${GREEN}✓ 可用 (HTTP $http_code)${NC}"
        return 0
    fi
    
    echo -e "${RED}✗ 不可用 (HTTP $http_code)${NC}"
    return 1
}

# 收集有效的镜像加速器
VALID_MIRRORS=()

for mirror in "${MIRRORS[@]}"; do
    if test_mirror "$mirror"; then
        VALID_MIRRORS+=("$mirror")
    fi
done

echo -e "\n${YELLOW}测试完成！找到 ${#VALID_MIRRORS[@]} 个可用的镜像加速器${NC}\n"

if [ ${#VALID_MIRRORS[@]} -eq 0 ]; then
    echo -e "${RED}错误: 没有找到可用的镜像加速器${NC}"
    exit 1
fi

# 显示有效的镜像加速器
echo -e "${GREEN}可用的镜像加速器:${NC}"
for mirror in "${VALID_MIRRORS[@]}"; do
    echo "  - $mirror"
done

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then 
    echo -e "\n${YELLOW}警告: 需要 root 权限来修改 Docker 配置${NC}"
    echo "请使用 sudo 运行此脚本: sudo $0"
    exit 1
fi

# 备份现有配置
DAEMON_JSON="/etc/docker/daemon.json"
if [ -f "$DAEMON_JSON" ]; then
    echo -e "\n${YELLOW}备份现有配置到 ${DAEMON_JSON}.bak${NC}"
    cp "$DAEMON_JSON" "${DAEMON_JSON}.bak}"
fi

# 读取现有配置或创建新配置
if [ -f "$DAEMON_JSON" ]; then
    echo -e "\n${YELLOW}合并现有配置...${NC}"
    # 使用 Python 合并配置（Python 通常在所有 Linux 系统上都可用）
    python3 << 'PYTHON_SCRIPT'
import json
import sys

daemon_json = "/etc/docker/daemon.json"
valid_mirrors = sys.argv[1:]

# 读取现有配置
try:
    with open(daemon_json, 'r', encoding='utf-8') as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}

# 获取现有镜像列表
existing_mirrors = config.get("registry-mirrors", [])
if not isinstance(existing_mirrors, list):
    existing_mirrors = []

# 合并并去重
all_mirrors = list(existing_mirrors)
for mirror in valid_mirrors:
    if mirror not in all_mirrors:
        all_mirrors.append(mirror)

# 更新配置
config["registry-mirrors"] = all_mirrors

# 写入文件
with open(daemon_json, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print(f"已添加 {len(valid_mirrors)} 个新的镜像加速器")
PYTHON_SCRIPT
    "${VALID_MIRRORS[@]}"
else
    # 创建新配置
    echo -e "\n${YELLOW}创建新配置文件...${NC}"
    mkdir -p /etc/docker
    
    # 构建 JSON 配置
    python3 << 'PYTHON_SCRIPT'
import json
import sys

daemon_json = "/etc/docker/daemon.json"
valid_mirrors = sys.argv[1:]

config = {
    "registry-mirrors": valid_mirrors
}

with open(daemon_json, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print(f"已创建配置文件，包含 {len(valid_mirrors)} 个镜像加速器")
PYTHON_SCRIPT
    "${VALID_MIRRORS[@]}"
fi

echo -e "\n${GREEN}配置已更新！${NC}"
echo -e "\n${YELLOW}当前配置内容:${NC}"
cat "$DAEMON_JSON"

# 重启 Docker 服务
echo -e "\n${YELLOW}重启 Docker 服务...${NC}"
systemctl daemon-reload
systemctl restart docker

echo -e "\n${GREEN}完成！Docker 镜像加速器已配置。${NC}"
echo -e "\n${YELLOW}验证配置:${NC}"
echo "运行 'docker info | grep -A 10 Registry' 查看配置是否生效"

