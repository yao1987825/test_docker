#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docker 镜像加速器测试和配置脚本
根据 https://gist.githubusercontent.com/y0ngb1n/7e8f16af3242c7815e7ca2f0833d3ea6/raw/57d744ea66b5cec7e43cc56af8437ef622b8bd6d/docker-registry-mirrors.md
"""

import json
import sys
import os
import urllib.request
import urllib.error
from typing import List, Set

# 颜色输出
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

# 镜像加速器列表（从文档中提取的可用加速器）
MIRRORS = [
    "https://dockerproxy.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://docker.nju.edu.cn",
    "https://docker.m.daocloud.io",
    "https://mirror.baidubce.com",
    "https://mirror.iscas.ac.cn",
]

DAEMON_JSON = "/etc/docker/daemon.json"


def test_mirror(mirror: str, timeout: int = 5) -> bool:
    """测试镜像加速器是否可用"""
    test_urls = [
        f"{mirror}/v2/",
        f"{mirror}",
    ]
    
    for test_url in test_urls:
        try:
            req = urllib.request.Request(test_url)
            req.add_header('User-Agent', 'Docker-Mirror-Test/1.0')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                # 200, 401, 404 都表示服务可用
                if status_code in [200, 301, 302, 401, 404]:
                    return True, status_code
        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            continue
    
    return False, None


def test_all_mirrors() -> List[str]:
    """测试所有镜像加速器，返回可用的列表"""
    print(f"{Colors.YELLOW}开始测试 Docker 镜像加速器...{Colors.NC}\n")
    
    valid_mirrors = []
    
    for mirror in MIRRORS:
        print(f"测试 {mirror} ... ", end="", flush=True)
        is_valid, status_code = test_mirror(mirror)
        
        if is_valid:
            print(f"{Colors.GREEN}✓ 可用 (HTTP {status_code}){Colors.NC}")
            valid_mirrors.append(mirror)
        else:
            print(f"{Colors.RED}✗ 不可用{Colors.NC}")
    
    print(f"\n{Colors.YELLOW}测试完成！找到 {len(valid_mirrors)} 个可用的镜像加速器{Colors.NC}\n")
    
    return valid_mirrors


def update_docker_config(valid_mirrors: List[str]) -> None:
    """更新 Docker 配置文件"""
    if not valid_mirrors:
        print(f"{Colors.RED}错误: 没有找到可用的镜像加速器{Colors.NC}")
        sys.exit(1)
    
    # 检查是否以 root 权限运行
    if os.geteuid() != 0:
        print(f"\n{Colors.YELLOW}警告: 需要 root 权限来修改 Docker 配置{Colors.NC}")
        print(f"请使用 sudo 运行此脚本: sudo {sys.argv[0]}")
        sys.exit(1)
    
    # 备份现有配置
    if os.path.exists(DAEMON_JSON):
        backup_path = f"{DAEMON_JSON}.bak"
        print(f"\n{Colors.YELLOW}备份现有配置到 {backup_path}{Colors.NC}")
        with open(DAEMON_JSON, 'r', encoding='utf-8') as f:
            with open(backup_path, 'w', encoding='utf-8') as backup:
                backup.write(f.read())
    
    # 读取现有配置或创建新配置
    if os.path.exists(DAEMON_JSON):
        print(f"\n{Colors.YELLOW}合并现有配置...{Colors.NC}")
        try:
            with open(DAEMON_JSON, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, Exception):
            config = {}
    else:
        print(f"\n{Colors.YELLOW}创建新配置文件...{Colors.NC}")
        os.makedirs(os.path.dirname(DAEMON_JSON), exist_ok=True)
        config = {}
    
    # 获取现有镜像列表
    existing_mirrors = config.get("registry-mirrors", [])
    if not isinstance(existing_mirrors, list):
        existing_mirrors = []
    
    # 合并并去重
    all_mirrors = list(existing_mirrors)
    new_count = 0
    for mirror in valid_mirrors:
        if mirror not in all_mirrors:
            all_mirrors.append(mirror)
            new_count += 1
    
    # 更新配置
    config["registry-mirrors"] = all_mirrors
    
    # 写入文件
    with open(DAEMON_JSON, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print(f"{Colors.GREEN}配置已更新！{Colors.NC}")
    if new_count > 0:
        print(f"已添加 {new_count} 个新的镜像加速器")
    
    print(f"\n{Colors.YELLOW}当前配置内容:{Colors.NC}")
    with open(DAEMON_JSON, 'r', encoding='utf-8') as f:
        print(f.read())
    
    # 重启 Docker 服务
    print(f"\n{Colors.YELLOW}重启 Docker 服务...{Colors.NC}")
    os.system("systemctl daemon-reload")
    os.system("systemctl restart docker")
    
    print(f"\n{Colors.GREEN}完成！Docker 镜像加速器已配置。{Colors.NC}")
    print(f"\n{Colors.YELLOW}验证配置:{Colors.NC}")
    print("运行 'docker info | grep -A 10 Registry' 查看配置是否生效")


def main():
    """主函数"""
    print(f"{Colors.BLUE}Docker 镜像加速器测试和配置工具{Colors.NC}\n")
    
    # 测试所有镜像加速器
    valid_mirrors = test_all_mirrors()
    
    if not valid_mirrors:
        print(f"{Colors.RED}没有找到可用的镜像加速器，退出。{Colors.NC}")
        sys.exit(1)
    
    # 显示有效的镜像加速器
    print(f"{Colors.GREEN}可用的镜像加速器:{Colors.NC}")
    for mirror in valid_mirrors:
        print(f"  - {mirror}")
    
    # 询问是否继续
    print(f"\n{Colors.YELLOW}是否要将这些镜像加速器添加到 Docker 配置中？(y/n): {Colors.NC}", end="")
    try:
        response = input().strip().lower()
        if response not in ['y', 'yes', '是']:
            print(f"{Colors.YELLOW}已取消操作。{Colors.NC}")
            sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Colors.YELLOW}已取消操作。{Colors.NC}")
        sys.exit(0)
    
    # 更新配置
    update_docker_config(valid_mirrors)


if __name__ == "__main__":
    main()


