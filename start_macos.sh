#!/bin/bash
# 启动 Dictation Practice macOS 桌面应用
# 用法: ./start_macos.sh

cd "$(dirname "$0")"

# 设置 Python 路径
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 启动 Flet 桌面应用
echo "Starting Dictation Practice for macOS..."
echo ""

python3 -m platforms.macos.main
