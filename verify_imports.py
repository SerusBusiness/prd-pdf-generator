#!/usr/bin/env python3
"""
Verify imports - A simple utility to test that all key imports in the PRD generator work correctly.
This helps identify import errors and module dependencies that might be causing issues.
"""
import sys
import os
from pathlib import Path

def print_success(message):
    """Print a success message in green"""
    print(f"\033[92m✓ {message}\033[0m")

def print_error(message):
    """Print an error message in red"""
    print(f"\033[91m✗ {message}\033[0m")

def print_info(message):
    """Print an info message in blue"""
    print(f"\033[94m• {message}\033[0m")

def test_imports():
    """Test importing all key modules and components"""
    print_info("Testing core imports...")
    
    try:
        from typing import TypeVar
        print_success("TypeVar import works correctly")
    except ImportError as e:
        print_error(f"TypeVar import error: {e}")
        
    try:
        from prd_generator.core.config import Config
        print_success("Config import works correctly")
        
        # Test Config initialization
        config = Config()
        print_success(f"Config initialized with model: {config.ollama_model}")
    except ImportError as e:
        print_error(f"Config import error: {e}")
    except Exception as e:
        print_error(f"Config initialization error: {e}")
        
    try:
        from prd_generator.utils.cache_manager import cached
        print_success("Cache manager cached decorator import works correctly")
    except ImportError as e:
        print_error(f"Cache manager import error: {e}")
        
    try:
        from prd_generator.utils.ollama_client import OllamaClient
        print_success("OllamaClient import works correctly")
    except ImportError as e:
        print_error(f"OllamaClient import error: {e}")
    
    try:
        from prd_generator.utils.pdf_generator import PDFGenerator
        print_success("PDFGenerator import works correctly")
    except ImportError as e:
        print_error(f"PDFGenerator import error: {e}")
        
    try:
        from prd_generator.core.content_generator import ContentGenerator
        print_success("ContentGenerator import works correctly")
    except ImportError as e:
        print_error(f"ContentGenerator import error: {e}")
        
    try:
        from prd_generator.formatters.content_normalizer import ContentNormalizer
        print_success("ContentNormalizer import works correctly")
    except ImportError as e:
        print_error(f"ContentNormalizer import error: {e}")
        
    try:
        from prd_generator.utils.diagram_generator import DiagramGenerator
        print_success("DiagramGenerator import works correctly")
    except ImportError as e:
        print_error(f"DiagramGenerator import error: {e}")
        
    try:
        from prd_generator.utils.image_generator import ImageGenerator
        print_success("ImageGenerator import works correctly")
    except ImportError as e:
        print_error(f"ImageGenerator import error: {e}")
        
    try:
        from prd_generator.prd_processor import PRDProcessor
        print_success("PRDProcessor import works correctly")
    except ImportError as e:
        print_error(f"PRDProcessor import error: {e}")
        
if __name__ == "__main__":
    print_info("Starting import verification...")
    test_imports()
    print_info("Import verification completed.")