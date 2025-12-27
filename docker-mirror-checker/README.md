# Docker 镜像加速器测试网站

一个用于测试 Docker 镜像加速器是否失效的 Web 应用，使用 Docker Compose 部署。

## 功能特性

- ✅ 自动测试多个镜像加速器的可用性
- ✅ 显示响应时间和 HTTP 状态码
- ✅ 实时显示测试进度
- ✅ 统计可用/不可用数量
- ✅ 导出测试结果和配置
- ✅ 美观的现代化 UI 界面
- ✅ 无需 SSL，本地部署
- ✅ **Redis 缓存优化**：使用 Redis 缓存测试结果，提高响应速度
- ✅ **MySQL 数据持久化**：存储历史检测记录和统计信息
- ✅ **历史记录查询**：支持查询镜像源的历史检测记录
- ✅ **统计分析**：提供镜像源的详细统计信息
- ✅ **自动配置 Docker**：每1小时自动更新 `/etc/docker/daemon.json`，无需手动操作

## 快速开始

### 1. 启动服务

```bash
docker-compose up -d
```

### 2. 访问网站

打开浏览器访问：`http://localhost:5000`

### 3. 停止服务

```bash
docker-compose down
```

## 使用方法

1. **测试所有镜像站**：点击"测试所有镜像站"按钮，系统会自动测试所有配置的镜像加速器
2. **查看结果**：测试完成后，会显示每个镜像站的状态、响应时间和详细信息
3. **导出结果**：点击"导出结果"按钮，可以下载包含测试结果和可用配置的文本文件

## 配置镜像站列表

要修改测试的镜像站列表，编辑 `app.py` 文件中的 `DEFAULT_MIRRORS` 列表：

```python
DEFAULT_MIRRORS = [
    "https://docker.1ms.run",
    "https://docker.1panel.live",
    # ... 添加更多镜像站
]
```

## 项目结构

```
docker-mirror-checker/
├── app.py                 # Flask 后端应用
├── templates/
│   └── index.html        # 前端界面
├── requirements.txt      # Python 依赖
├── Dockerfile           # Docker 镜像构建文件
├── docker-compose.yml   # Docker Compose 配置
└── README.md           # 说明文档
```

## API 接口

### 测试所有镜像站
```
POST /api/test/all
Content-Type: application/json

{
  "mirrors": ["https://docker.1ms.run", ...]
}
```

### 测试单个镜像站
```
POST /api/test
Content-Type: application/json

{
  "mirror": "https://docker.1ms.run"
}
```

### 健康检查
```
GET /api/health
```

### 获取历史记录
```
GET /api/history?mirror=<镜像源URL>&limit=100
```

### 获取统计信息
```
GET /api/statistics
```

## 技术栈

- **后端**: Flask (Python)
- **前端**: HTML + CSS + JavaScript
- **容器**: Docker + Docker Compose
- **缓存**: Redis (缓存测试结果，提高性能)
- **数据库**: MySQL (存储历史记录和统计信息)

## 自动配置 Docker

系统每1小时自动检测镜像源状态，并自动更新 `/etc/docker/daemon.json` 配置文件：

- **自动选择**：选择响应时间最快的 5 个可用镜像源
- **自动备份**：更新前自动备份现有配置到 `daemon.json.bak`
- **自动写入**：直接写入到 `/etc/docker/daemon.json`（通过 volume 挂载）
- **手动触发**：可通过 API `POST /api/config/update` 手动触发更新

### 配置 Docker 服务重启

配置更新后，需要重启 Docker 服务才能生效。由于容器内无法直接重启宿主机的 Docker 服务，请手动执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

或者使用提供的脚本：

```bash
./update-docker-config.sh
```

### 验证配置

配置更新后，验证是否生效：

```bash
docker info | grep -A 10 "Registry Mirrors"
```

## 注意事项

1. 默认端口为 5000，如需修改请编辑 `docker-compose.yml`
2. 测试超时时间为 5 秒
3. 测试结果会按可用性排序，可用的镜像站会显示在前面
4. 支持 HTTP 状态码 200, 301, 302, 401, 404 作为可用标识
5. **自动配置功能**：需要挂载 `/etc/docker` 目录，确保容器有写入权限
6. **Docker 服务重启**：配置更新后需要手动重启 Docker 服务才能生效

## 故障排除

如果遇到问题：

1. 检查 Docker 服务是否运行：`docker ps`
2. 查看容器日志：`docker-compose logs`
3. 检查端口是否被占用：`netstat -tuln | grep 5000`
4. 重新构建镜像：`docker-compose build --no-cache`

## 许可证

MIT License

