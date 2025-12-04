from setuptools import setup, find_packages

setup(
    name="komitto",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pyperclip",
    ],
    entry_points={
        "console_scripts": [
            "komitto=komitto.main:main",
        ],
    },
    author="mxcake",
    description="A CLI tool that generates semantic Japanese commit message prompts for LLMs from Git diff information.",
    python_requires=">=3.6",
)