#!/bin/bash
# 启动 Dictation Web 应用
# 用法: ./start_web.sh

cd "$(dirname "$0")"

# 设置 Python 路径
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 使用项目本地 data/ 目录的数据库
export DATABASE_PATH="$(pwd)/data/dictation.db"

# 启动 Flask 应用
echo "Starting Dictation Web..."
echo "Database: $DATABASE_PATH"
echo ""

python3 -m platforms.web.main
