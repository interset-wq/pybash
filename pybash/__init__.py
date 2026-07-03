"""PyBash - A cross-platform bash shell implemented in pure Python.

Provides a bash-compatible shell experience on Windows, macOS, and Linux
without depending on external shell binaries. All core commands are
implemented in Python for maximum portability.

Usage:
    import pybash
    pybash.main()

    # Or from command line:
    python -m pybash
"""

from pybash.shell import main

__version__ = "0.1.0"
__all__ = ["main"]
