"""
Kube-OVN 智能诊断工具安装配置
"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="kube-ovn-checker",
    version="1.0.0",
    author="Kube-OVN Community",
    description="基于 LLM 的 Kube-OVN 网络问题智能诊断工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kube-ovn/kube-ovn-langgraph-checker",
    packages=find_packages(exclude=["tests*", "docs*", "build*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "langgraph>=0.2.0",
        "langchain>=0.3.0",
        "langchain-openai>=0.2.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "filelock>=3.12.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kube-ovn-checker=kube_ovn_checker.cli.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "kube_ovn_checker": [
            "knowledge/*.md",
            "knowledge/crds/*.md",
            "knowledge/issues/*.md",
        ],
    },
)
