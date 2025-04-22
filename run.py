#!/usr/bin/env python3
"""
Run script for quickly testing the PRD generator without installation
"""
import os
import sys
from pathlib import Path

# Add support for .env file
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file if it exists
    env_path = Path(".env")
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        load_dotenv(env_path)
except ImportError:
    # If python-dotenv is not installed, try to read the .env file manually
    if Path(".env").exists():
        print("Loading environment variables from .env file (python-dotenv not installed)")
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip().strip('"').strip("'")
        except Exception as e:
            print(f"Error loading .env file: {e}")

# Add the project directory to the path so we can import our package
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Now we can import our main module
from prd_generator.main import main

if __name__ == "__main__":
    # This passes all command line arguments to our main function
    main()