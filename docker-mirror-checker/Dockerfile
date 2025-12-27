FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY app.py .
COPY templates/ templates/

# 暴露端口
EXPOSE 5000

# 运行应用（使用 uvicorn 启动 FastAPI）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
