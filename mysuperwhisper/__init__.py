"""
MySuperWhisper - Global voice dictation tool using Granite Speech
"""
import os
import sys
from pathlib import Path

# Automatically detect and add NVIDIA library paths from venv to LD_LIBRARY_PATH.
# This helps local CUDA-enabled torch wheels find bundled NVIDIA libraries.
def _setup_cuda_paths():
    # Find the venv relative to this file
    # This assumes we are in project/mysuperwhisper/__init__.py
    # So project root is parent.
    project_root = Path(__file__).parent.parent
    
    # Try to find site-packages (path varies by python version)
    # We'll look for any directory matching the structure
    potential_lib_dirs = list(project_root.glob("venv/lib/python*/site-packages/nvidia/*/lib"))
    
    if potential_lib_dirs:
        unique_paths = list(set([str(p.absolute()) for p in potential_lib_dirs]))
        existing_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        
        # Prepend to LD_LIBRARY_PATH
        if existing_ld_path:
            os.environ["LD_LIBRARY_PATH"] = ":".join(unique_paths + [existing_ld_path])
        else:
            os.environ["LD_LIBRARY_PATH"] = ":".join(unique_paths)

_setup_cuda_paths()

__version__ = "1.6.1"
__author__ = "Olivier Mary"
