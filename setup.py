from setuptools import setup, find_packages

setup(
    name="yt-dluxe",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask>=3.0.0",
        "yt-dlp>=2023.0.0",
    ],
    entry_points={
        "console_scripts": [
            "yt-dluxe=yt_dluxe.app:main",
        ],
    },
)