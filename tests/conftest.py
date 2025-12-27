"""
Pytest configuration and shared fixtures
"""
import sys
from pathlib import Path

# Add src directories to path for imports
src_shared = Path(__file__).parent.parent / "src" / "shared"
src_functions = Path(__file__).parent.parent / "src" / "functions-python"
src_webapp = Path(__file__).parent.parent / "src" / "webapp"

sys.path.insert(0, str(src_shared))
sys.path.insert(0, str(src_functions))
sys.path.insert(0, str(src_webapp))
