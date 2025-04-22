from setuptools import setup, find_packages

setup(
    name="prd_generator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "reportlab",
        "pypdf",
        "pillow",
        "beautifulsoup4",
        "lxml",
        "markdown",
        "cairosvg",
        "python-dotenv",
        "duckduckgo-search"
    ],
    entry_points={
        'console_scripts': [
            'prd-gen=prd_generator.main:main',
        ],
    },
)