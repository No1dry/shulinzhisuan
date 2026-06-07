#!/bin/bash
# 数邻智算-网格员端 后端启动脚本 (Linux/Mac)

cd "$(dirname "$0")"

echo "========================================="
echo "  数邻智算-网格员端 后端服务启动"
echo "========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.9+"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "激活虚拟环境..."
source venv/bin/activate

# Install dependencies
echo "安装依赖..."
pip install -q -r requirements.txt

# Start server
echo "启动 FastAPI 服务..."
echo "服务地址: http://localhost:8000"
echo "API文档:  http://localhost:8000/docs"
echo "========================================="

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
