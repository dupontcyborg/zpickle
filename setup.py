#!/usr/bin/env python

import os
from setuptools import setup, find_packages

# Read the long description from README.md
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="zpickle",
    use_scm_version={
        "write_to": "zpickle/_version.py",
        "version_scheme": "guess-next-dev",
        "local_scheme": "no-local-version",
        "fallback_version": "0.0.0+unknown",
    },
    description="Transparent, drop-in compression for Python's pickle",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Nicolas Dupont",
    author_email="your.email@example.com",
    url="https://github.com/dupontcyborg/zpickle",
    project_urls={
        "Bug Tracker": "https://github.com/dupontcyborg/zpickle/issues",
        "Documentation": "https://github.com/dupontcyborg/zpickle#readme",
        "Source Code": "https://github.com/dupontcyborg/zpickle",
    },
    keywords=["pickle", "compression", "serialization", "zstd", "brotli", "zlib", "lzma"],
    license="MIT",
    packages=["zpickle"],
    setup_requires=[
        "setuptools_scm>=3.4",
    ],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Archiving :: Compression",
        "Topic :: Software Development :: Libraries",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "compress-utils",
    ],
    zip_safe=False,
)