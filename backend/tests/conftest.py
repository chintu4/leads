import sys
import os

# Ensure the 'backend' package root is on sys.path so 'src' imports resolve when running tests
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
