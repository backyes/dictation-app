#!/bin/bash
# 启动 Dictation Web 应用
# 用法: ./start_web.sh

cd "$(dirname "$0")"

# 设置 Python 路径
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 使用与打包 App 相同的数据库路径
export DATABASE_PATH="$HOME/Library/Application Support/DictationWeb/dictation.db"

# 启动 Flask 应用
echo "Starting Dictation Web..."
echo "Database: $DATABASE_PATH"
echo ""

python3 -m platforms.web.main
