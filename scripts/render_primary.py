"""Compatibility entry point; map generation is coordinated by the primary CLI."""
import sys
from afiw.cli import primary_main

if __name__ == '__main__':
    primary_main(['render', *sys.argv[1:]])
