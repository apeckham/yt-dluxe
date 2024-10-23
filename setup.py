from setuptools import setup, find_packages

setup(
    name="yt-dluxe",
    version="0.1",
    packages=find_packages(),  # This should find your package directory
    include_package_data=True,  # This ensures non-Python files are included
    install_requires=[
        "flask",
        "yt-dlp",
    ],
    entry_points={
        "console_scripts": [
            "yt-dluxe=yt_dluxe.app:main",  # Adjust to point to your main function
        ],
    },
)