# Docker 镜像加速器测试和配置工具

根据 [Docker Hub 镜像加速器文档](https://gist.githubusercontent.com/y0ngb1n/7e8f16af3242c7815e7ca2f0833d3ea6/raw/57d744ea66b5cec7e43cc56af8437ef622b8bd6d/docker-registry-mirrors.md) 创建的自动化测试和配置工具。

## 功能

- 自动测试多个 Docker 镜像加速器是否可用
- 将有效的镜像加速器添加到 Docker 配置中
- 自动备份现有配置
- 自动重启 Docker 服务

## 使用方法

### 方法 1: 使用 Bash 脚本（推荐）

```bash
sudo ./test_docker_mirrors.sh
```

### 方法 2: 使用 Python 脚本

```bash
sudo python3 test_docker_mirrors.py
```

或者：

```bash
sudo ./test_docker_mirrors.py
```

## 测试的镜像加速器

脚本会测试以下镜像加速器：

- https://dockerproxy.com
- https://docker.mirrors.ustc.edu.cn
- https://docker.nju.edu.cn
- https://docker.m.daocloud.io
- https://mirror.baidubce.com
- https://mirror.iscas.ac.cn

## 工作原理

1. **测试阶段**: 脚本会逐个测试每个镜像加速器的可用性
   - 通过 HTTP 请求检查镜像加速器的 API 端点
   - 如果返回 200、301、302、401 或 404 状态码，则认为可用

2. **配置阶段**: 
   - 备份现有的 `/etc/docker/daemon.json` 配置文件
   - 读取现有配置（如果存在）
   - 将有效的镜像加速器添加到配置中（去重）
   - 保存配置并重启 Docker 服务

## 验证配置

运行脚本后，可以使用以下命令验证配置：

```bash
docker info | grep -A 10 Registry
```

或者查看配置文件：

```bash
cat /etc/docker/daemon.json
```

## 注意事项

1. **需要 root 权限**: 修改 Docker 配置需要管理员权限，请使用 `sudo` 运行
2. **自动备份**: 脚本会自动备份现有配置文件到 `/etc/docker/daemon.json.bak`
3. **服务重启**: 脚本会自动重启 Docker 服务以应用新配置
4. **网络要求**: 测试需要网络连接，请确保可以访问互联网

## 故障排除

如果遇到问题：

1. 检查网络连接
2. 确认 Docker 服务正在运行: `systemctl status docker`
3. 查看备份文件: `cat /etc/docker/daemon.json.bak`
4. 手动恢复配置: `sudo cp /etc/docker/daemon.json.bak /etc/docker/daemon.json`

## 参考链接

- [Docker Hub 镜像加速器文档](https://gist.githubusercontent.com/y0ngb1n/7e8f16af3242c7815e7ca2f0833d3ea6/raw/57d744ea66b5cec7e43cc56af8437ef622b8bd6d/docker-registry-mirrors.md)
- [Docker 官方文档 - 配置镜像加速器](https://docs.docker.com/registry/recipes/mirror/)


# test_docker
