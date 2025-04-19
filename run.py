import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from server.server import app

if __name__ == '__main__':
    print("Starting Flask server...")
    print(f"Project root: {project_root}")
    app.run(debug=True, port=8000)