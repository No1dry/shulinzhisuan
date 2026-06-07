@echo off
chcp 65001 >nul
REM 数邻智算-网格员端 后端启动脚本 (Windows)

cd /d "%~dp0"

echo =========================================
echo   数邻智算-网格员端 后端服务启动
echo =========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 python，请先安装 Python 3.9+
    pause
    exit /b 1
)

REM Create virtual environment if not exists
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

REM Activate virtual environment
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM Install dependencies
echo 安装依赖...
pip install -q -r requirements.txt

REM Start server
echo 启动 FastAPI 服务...
echo 服务地址: http://localhost:8000
echo API文档:  http://localhost:8000/docs
echo =========================================

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
