#!/bin/bash
# 启动 Dictation Practice Web 应用
# 用法: ./start_web.sh

cd "$(dirname "$0")"

# 设置 Python 路径
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 启动 Flask 应用
echo "Starting Dictation Practice Web..."
echo "Open http://localhost:5002 in your browser"
echo ""

python3 -m platforms.web.main
