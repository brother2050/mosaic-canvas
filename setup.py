#!/usr/bin/env python
"""Setup script for Mosaic Canvas."""

from setuptools import setup, find_packages

setup(
    name="mosaic-canvas",
    version="0.1.0",
    description="A standalone visual node-canvas UI for the Mosaic AI pipeline framework",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="brother2050",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "mosaic_canvas": [],
    },
    install_requires=[
        "fastapi>=0.100",
        "uvicorn[standard]>=0.20",
        "pydantic>=2.0",
        "websockets>=11.0",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "mosaic-canvas=mosaic_canvas.cli:main",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
