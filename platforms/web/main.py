"""Web entry point"""
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from platforms.web.app import app

def main():
    """Run Web platform"""
    app.run(debug=True, host='0.0.0.0', port=5002)

if __name__ == "__main__":
    main()
