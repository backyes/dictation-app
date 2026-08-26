"""Web entry point"""
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from platforms.web.app import WebPlatform
from platforms.base import PlatformConfig

def main():
    """Run Web platform"""
    config = PlatformConfig(debug=True, host='0.0.0.0', port=5002)
    p = WebPlatform(config)
    p.run()

if __name__ == "__main__":
    main()
