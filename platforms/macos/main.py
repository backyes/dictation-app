"""
Mobile entry point for Android APK build.
This main.py is used by Buildozer when source.dir = .. (project root).
"""
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import flet as ft
from ui.flet_app import run_app

def main():
    """Run Flet app for Android"""
    ft.app(target=run_app)

if __name__ == "__main__":
    main()