#!/usr/bin/env python
"""Compatibility setup.py for Python environments that don't fully support pyproject.toml."""

from setuptools import setup

if __name__ == "__main__":
    # All configuration is in pyproject.toml
    setup()