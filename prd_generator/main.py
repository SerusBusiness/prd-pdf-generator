#!/usr/bin/env python3
"""
PRD Generator - Main module
Generates Product Requirement Documents from text input using LLM (Ollama)
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from prd_generator.core.config import Config, load_env_file
from prd_generator.core.logging_setup import setup_logging, get_logger
from prd_generator.prd_processor import PRDProcessor
from prd_generator.utils.cache_manager import cache

# Initialize logging
setup_logging()
logger = get_logger(__name__)

def generate_prd_from_prompt(prompt_text, output_path, config=None):
    """
    Generate a PRD document from a text prompt.
    
    Args:
        prompt_text: Text prompt describing the product
        output_path: Output path for the generated PDF
        config: Configuration settings (optional)
        
    Returns:
        str: Path to the generated PDF
    """
    if config is None:
        config = Config()
    
    try:
        # Process the PRD generation
        processor = PRDProcessor(config)
        logger.info(f"Using Ollama model: {config.ollama_model}")
        
        return processor.process_prd(prompt_text, output_path)
    except Exception as e:
        logger.error(f"Error generating PRD: {e}", exc_info=True)
        raise


def main():
    """Main entry point for the PRD Generator application."""
    try:
        # Initialize the cache system and repair if needed
        try:
            cache_repair_count = cache.repair()
            if cache_repair_count > 0:
                logger.info(f"Cache repair completed. Removed {cache_repair_count} corrupted cache entries.")
        except Exception as cache_error:
            logger.warning(f"Cache initialization error: {cache_error}. Continuing without cache.")
            
        # Load environment variables from .env file
        load_env_file()
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description="Generate PRDs from text input using Ollama LLM.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        # Input options
        input_group = parser.add_argument_group("Input Options")
        input_group.add_argument(
            "-i", "--input",
            help="Input text file containing PRD prompt"
        )
        input_group.add_argument(
            "-p", "--prompt",
            help="Direct text prompt (alternative to input file)"
        )
        
        # Output options
        output_group = parser.add_argument_group("Output Options")
        output_group.add_argument(
            "-o", "--output",
            help="Output PDF file path (default: auto-generated with timestamp)"
        )
        
        # Cache options
        cache_group = parser.add_argument_group("Cache Options")
        cache_group.add_argument(
            "--clear-cache",
            action="store_true",
            help="Clear all cached content before running"
        )
        cache_group.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable caching for this run"
        )
        
        # Model options
        model_group = parser.add_argument_group("Model Options")
        model_group.add_argument(
            "-m", "--model",
            default=os.environ.get("OLLAMA_MODEL", "llama3"),
            help="Ollama model to use"
        )
        model_group.add_argument(
            "--temperature",
            type=float,
            help="Temperature for LLM (0.0-1.0)"
        )
        
        # Feature flags
        feature_group = parser.add_argument_group("Features")
        feature_group.add_argument(
            "--search",
            nargs="?", 
            const=True,
            metavar="CONTEXT",
            help="Enable reference document search with optional context file or direct text"
        )
        feature_group.add_argument(
            "--enhance-prompt",
            action="store_true",
            help="Enhance the input prompt with search results before generating content"
        )
        feature_group.add_argument(
            "--no-search",
            action="store_true",
            help="Disable reference document search"
        )
        feature_group.add_argument(
            "--no-images",
            action="store_true",
            help="Disable image generation"
        )
        feature_group.add_argument(
            "--no-diagrams",
            action="store_true",
            help="Disable diagram generation"
        )
        feature_group.add_argument(
            "--use-ai-generated",
            action="store_true",
            help="Use pre-generated AI content from ai_generated.txt"
        )
        
        # API keys
        api_group = parser.add_argument_group("API Keys")
        api_group.add_argument(
            "--pixabay-key",
            help="Pixabay API key for image generation (can also be set in .env file)"
        )
        
        # Parse the arguments
        args = parser.parse_args()
        
        # Handle cache options
        if args.clear_cache:
            try:
                cleared_count = cache.clear()
                logger.info(f"Cache cleared: {cleared_count} entries removed")
            except Exception as e:
                logger.warning(f"Failed to clear cache: {e}")
        
        # Disable caching if requested
        if args.no_cache:
            # Set an extremely short TTL to effectively disable the cache
            cache.ttl = 1
            logger.info("Caching disabled for this session")
        
        # Initialize configuration
        config = Config()
        
        # Update configuration from command line arguments
        config.ollama_model = args.model
        if args.temperature is not None:
            config.ollama_temperature = args.temperature
            
        # Handle conflicting search flags
        if args.search and args.no_search:
            logger.warning("Both --search and --no-search specified; using --search")
            config.enable_search = True
        elif args.search:
            config.enable_search = True
            # Handle search context if provided
            if isinstance(args.search, str):
                search_context_text = ""
                # Check if it's a file path
                search_context_path = Path(args.search).resolve()
                if search_context_path.exists() and search_context_path.is_file():
                    try:
                        with open(search_context_path, 'r', encoding='utf-8') as f:
                            search_context_text = f.read()
                        logger.info(f"Loaded search context from file: {search_context_path}")
                    except Exception as e:
                        logger.error(f"Error reading search context file: {e}")
                        logger.info("Using search context as direct text")
                        search_context_text = args.search
                else:
                    # Use as direct text
                    search_context_text = args.search
                    logger.info("Using provided text as search context")
                
                if search_context_text:
                    config.search_context = search_context_text
                    logger.info(f"Search context set ({len(search_context_text)} characters)")
        elif args.no_search:
            config.enable_search = False
            
        # Set prompt enhancement option
        if args.enhance_prompt:
            if not config.enable_search:
                logger.warning("Prompt enhancement requires search to be enabled; enabling search")
                config.enable_search = True
            config.enhance_prompt = True
            logger.info("Prompt enhancement enabled")
            
        config.generate_images = not args.no_images
        config.generate_diagrams = not args.no_diagrams
        config.skip_ai_generated = not args.use_ai_generated
        
        # Set Pixabay API key if provided via command line
        if args.pixabay_key:
            config.pixabay_api_key = args.pixabay_key
            os.environ["PIXABAY_API_KEY"] = args.pixabay_key
            
        # Get input prompt either from file or direct prompt
        prompt_text = ""
        if args.input:
            try:
                input_path = Path(args.input).resolve()
                logger.info(f"Reading prompt from file: {input_path}")
                with open(input_path, 'r', encoding='utf-8') as f:
                    prompt_text = f.read()
            except FileNotFoundError:
                logger.error(f"Error: Input file '{args.input}' not found")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error reading input file: {e}")
                sys.exit(1)
        elif args.prompt:
            prompt_text = args.prompt
            logger.info(f"Using direct prompt: {prompt_text[:50]}...")
        else:
            # If no input provided, try to use the default_input.txt
            default_input_path = config.data_dir / 'default_input.txt'
            if (default_input_path.exists()):
                try:
                    with open(default_input_path, 'r', encoding='utf-8') as f:
                        prompt_text = f.read()
                    logger.info(f"Using default input from {default_input_path}")
                except Exception as e:
                    logger.error(f"Error reading default input file: {e}")
                    sys.exit(1)
            else:
                logger.error("Error: No input provided. Use --input or --prompt")
                parser.print_help()
                sys.exit(1)
        
        # Set output file path
        if args.output:
            output_path = Path(args.output).resolve()
        else:
            # If no output path provided, use a default with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            config.output_dir.mkdir(exist_ok=True)
            output_path = config.output_dir / f'prd_document_{timestamp}.pdf'
        
        # Ensure the output directory exists
        output_path.parent.mkdir(exist_ok=True)
        
        # Process the PRD generation
        logger.info(f"Generating PRD from prompt...")
        output_file = generate_prd_from_prompt(prompt_text, str(output_path), config)
        logger.info(f"PRD generated successfully: {output_file}")
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()