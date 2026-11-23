from setuptools import setup, find_packages

setup(
    name="bittle-cli",
    version="1.0.0",
    description="Command-line interface and terminal controller for Petoi Bittle and Bittle X robots",
    author="Prajval Arora",
    url="https://github.com/RoboX2020/bittle-cli",
    py_modules=["bittle_cli", "bittle_mix", "mock_bittle"],
    package_data={"": ["combos.json"]},
    include_package_data=True,
    install_requires=[
        "pyserial>=3.5",
        "bleak>=0.21.0",
        "websockets>=11.0",
    ],
    entry_points={
        "console_scripts": [
            "bittle=bittle_cli:main_cli",
            "bittle-mock=mock_bittle:main",
        ],
    },
    python_requires=">=3.8",
)
