"""Compatibility entry point; training is coordinated by the primary CLI."""
import sys
from afiw.cli import primary_main

if __name__ == '__main__':
    primary_main(['train-labels', *sys.argv[1:]])
