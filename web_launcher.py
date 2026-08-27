"""
Web App macOS 启动器
启动 Flask 服务并自动打开浏览器
打包命令: pyinstaller --windowed --name DictationWeb web_launcher.py
"""
import sys
import os
import time
import threading
import webbrowser

# 确保项目根目录在路径中
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
else:
    # 开发模式路径
    project_root = os.path.dirname(os.path.abspath(__file__))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from platforms.web.app import app


def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)  # 等待 Flask 启动
    webbrowser.open('http://localhost:5002')


def main():
    """启动 Flask 并打开浏览器"""
    # 在后台线程打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # 启动 Flask（阻塞）
    app.run(debug=False, host='0.0.0.0', port=5002)


if __name__ == '__main__':
    main()
