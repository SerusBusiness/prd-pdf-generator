#!/usr/bin/env python3
"""
PRD Generator - Main module
Generates Product Requirement Documents from text input using LLM (Ollama)
"""
import argparse
import os
import sys
from pathlib import Path

# Add support for .env file
def load_env_file():
    """Load environment variables from .env file if it exists."""
    try:
        # First try to use python-dotenv if installed
        try:
            from dotenv import load_dotenv
            env_path = Path(os.path.dirname(os.path.dirname(__file__))) / ".env"
            if env_path.exists():
                print(f"Loading environment variables from {env_path}")
                load_dotenv(env_path)
                return True
        except ImportError:
            pass

        # Fallback to manual loading if dotenv is not available
        env_path = Path(os.path.dirname(os.path.dirname(__file__))) / ".env"
        if env_path.exists():
            print("Loading environment variables from .env file")
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")
                    except ValueError:
                        pass
            return True
    except Exception as e:
        print(f"Warning: Error loading .env file: {e}")
    return False

from prd_generator.prd_processor import PRDProcessor
from prd_generator.config import Config


def generate_prd_from_prompt(prompt_text, output_path, config=None):
    """Generate a PRD document from a text prompt."""
    if config is None:
        config = Config()
    
    # Process the PRD generation
    processor = PRDProcessor(config)
    print(f"Using Ollama model: {config.ollama_model}")
    
    processor.process_prd(prompt_text, output_path)


def main():
    """Main entry point for the PRD Generator application."""
    # Load environment variables from .env file
    load_env_file()
    
    parser = argparse.ArgumentParser(description="Generate PRDs from text input using Ollama.")
    parser.add_argument(
        "-i", "--input",
        help="Input text file containing PRD prompt"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output PDF file path"
    )
    parser.add_argument(
        "-m", "--model",
        default="llama3",
        help="Ollama model to use (default: llama3)"
    )
    parser.add_argument(
        "-p", "--prompt",
        help="Direct text prompt (alternative to input file)"
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Enable reference document search"
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Disable image generation"
    )
    parser.add_argument(
        "--no-diagrams",
        action="store_true",
        help="Disable diagram generation"
    )
    parser.add_argument(
        "--pixabay-key",
        help="Pixabay API key for image generation (can also be set in .env file)"
    )
    
    args = parser.parse_args()
    
    config = Config()
    config.ollama_model = args.model
    config.enable_search = args.search
    config.generate_images = not args.no_images
    config.generate_diagrams = not args.no_diagrams
    
    # Set Pixabay API key if provided via command line
    if args.pixabay_key:
        config.pixabay_api_key = args.pixabay_key
        os.environ["PIXABAY_API_KEY"] = args.pixabay_key
    # If not set in command line, try to get it from environment (via .env file)
    elif os.environ.get("PIXABAY_API_KEY"):
        config.pixabay_api_key = os.environ.get("PIXABAY_API_KEY")
    
    # Get input prompt either from file or direct prompt
    prompt_text = ""
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
        except FileNotFoundError:
            print(f"Error: Input file '{args.input}' not found")
            sys.exit(1)
    elif args.prompt:
        prompt_text = args.prompt
    else:
        # If no input provided, try to use the default_input.txt
        default_input_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'default_input.txt')
        if os.path.exists(default_input_path):
            with open(default_input_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
        else:
            print("Error: No input provided. Use --input or --prompt")
            parser.print_help()
            sys.exit(1)
    
    # Set output file path
    if args.output:
        output_path = args.output
    else:
        # If no output path provided, use a default
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'prd_document.pdf')
    
    # Process the PRD generation
    print(f"Generating PRD from prompt...")
    generate_prd_from_prompt(prompt_text, output_path, config)
    print(f"PRD generated successfully: {output_path}")


if __name__ == "__main__":
    main()