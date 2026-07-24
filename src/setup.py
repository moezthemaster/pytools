#!/usr/bin/env python3
"""Setup du package sessions"""

from setuptools import setup, find_packages

setup(
    name="sessions",
    version="1.0.0",
    description="Outils SSH multi-environnements",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "paramiko>=3.0.0",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.0",
    ],
    entry_points={
        "console_scripts": [
            "connect=sessions.connect:main",
            "exec=sessions.exec:main",
        ],
    },
    python_requires=">=3.6",
)
