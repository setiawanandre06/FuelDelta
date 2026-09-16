"""Allow pytest to import the src layout without installing the package."""

import os
import sys


SOURCE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)  # type: str
sys.path.insert(0, SOURCE_ROOT)
