import sys
import os

# Allow importing from src directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from qa_snapshot_tool.main import main

if __name__ == "__main__":
    main()
