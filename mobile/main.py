"""Mobile entry point - Flet main() for Android APK build"""
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import flet as ft
from platforms.android.app import DictationApp
from common.storage.sqlite_storage import get_storage

def main():
    """Run Flet app for Android"""
    def page_main(page: ft.Page):
        storage = get_storage()
        app = DictationApp(storage, page)
        app.init_ui(page)
    
    ft.app(target=page_main)

if __name__ == "__main__":
    main()
