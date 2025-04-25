"""
Enhanced configuration module for PRD Generator with improved environment variable handling.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Type, Union, Callable

from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


@dataclass
class Config:
    """Enhanced configuration settings for the PRD Generator."""
    # Ollama settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_temperature: float = 0.3
    ollama_api_endpoint: Optional[str] = None
    
    # API keys
    pixabay_api_key: str = ""
    
    # Feature flags
    enable_search: bool = True
    generate_images: bool = True
    generate_diagrams: bool = True
    skip_ai_generated: bool = True
    
    # Search settings
    search_context: Optional[str] = None
    enhance_prompt: bool = False
    max_references_for_enhancement: int = 5
    max_snippet_length: int = 300
    cache_enhanced_prompts: bool = True
    
    # Reasoning model settings
    handle_thinking: bool = True
    keep_thinking: bool = False
    extract_insights: bool = False
    
    # PDF settings
    page_width: float = 595.27  # A4 width in points
    page_height: float = 841.89  # A4 height in points
    margin: float = 50.0
    
    # PRD sections to include
    prd_sections: List[str] = field(default_factory=list)
    
    # Mermaid diagram service settings
    mermaid_service_url: str = "http://localhost:3000/convert/image"
    
    # File paths
    base_dir: Path = field(default_factory=lambda: Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    data_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    debug_dir: Path = field(init=False)
    
    def __post_init__(self):
        """Initialize configuration after object creation."""
        # Set default PRD sections if none provided
        if not self.prd_sections:
            self.prd_sections = [
                "Executive Summary",
                "Problem Statement",
                "Target Users",
                "Product Goals",
                "Requirements & Features",
                "User Stories",
                "Technical Requirements",
                "Architecture",
                "Implementation Plan",
                "Success Metrics",
                "Risks & Mitigation",
                "References"
            ]
            
        # Set directory paths
        self.data_dir = self.base_dir / "data"
        self.output_dir = self.base_dir / "output"
        self.debug_dir = self.data_dir / "debug"
        
        # Create necessary directories
        self.output_dir.mkdir(exist_ok=True)
        self.debug_dir.mkdir(exist_ok=True)
        
        # Load from environment variables
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration values from environment variables."""
        # Define mapping of environment variables to config attributes with types
        env_mappings = {
            # Ollama settings
            "OLLAMA_HOST": ("ollama_host", str),
            "OLLAMA_MODEL": ("ollama_model", str),
            "OLLAMA_TEMPERATURE": ("ollama_temperature", float),
            "OLLAMA_API_ENDPOINT": ("ollama_api_endpoint", str),
            
            # API keys
            "PIXABAY_API_KEY": ("pixabay_api_key", str),
            
            # Mermaid service
            "MERMAID_SERVICE_URL": ("mermaid_service_url", str),
        }
        
        # Boolean settings with their attribute names
        bool_mappings = {
            "ENABLE_SEARCH": "enable_search",
            "GENERATE_IMAGES": "generate_images",
            "GENERATE_DIAGRAMS": "generate_diagrams",
            "SKIP_AI_GENERATED": "skip_ai_generated",
            "HANDLE_THINKING": "handle_thinking",
            "KEEP_THINKING": "keep_thinking",
            "EXTRACT_INSIGHTS": "extract_insights",
        }
        
        # Process regular settings
        for env_var, (attr_name, attr_type) in env_mappings.items():
            if env_var in os.environ:
                try:
                    value = attr_type(os.environ[env_var])
                    setattr(self, attr_name, value)
                    logger.debug(f"Set {attr_name} = {value} from {env_var}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid {env_var} value: {os.environ[env_var]}. Error: {e}")
        
        # Process boolean settings
        for env_var, attr_name in bool_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var].lower() in ('true', '1', 'yes', 'y')
                setattr(self, attr_name, value)
                logger.debug(f"Set {attr_name} = {value} from {env_var}")
    
    def update_from_args(self, args):
        """
        Update configuration based on command line arguments.
        
        Args:
            args: Parsed command line arguments from argparse
        """
        # Map argparse attributes to config attributes if they exist and are not None
        if hasattr(args, 'model') and args.model is not None:
            self.ollama_model = args.model
        
        if hasattr(args, 'search'):
            self.enable_search = args.search
            
        if hasattr(args, 'no_images'):
            self.generate_images = not args.no_images
            
        if hasattr(args, 'no_diagrams'):
            self.generate_diagrams = not args.no_diagrams
            
        if hasattr(args, 'use_ai_generated'):
            self.skip_ai_generated = not args.use_ai_generated
            
        if hasattr(args, 'pixabay_key') and args.pixabay_key:
            self.pixabay_api_key = args.pixabay_key
            os.environ["PIXABAY_API_KEY"] = args.pixabay_key
        
        # Log the updated configuration
        logger.debug(f"Updated configuration from command line arguments: {vars(args)}")


def load_env_file(dotenv_path=None):
    """
    Load environment variables from .env file.
    
    Args:
        dotenv_path: Path to the .env file (optional)
        
    Returns:
        bool: True if .env file was loaded successfully, False otherwise
    """
    if not dotenv_path:
        # Try to locate .env file in the project root directory
        base_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        dotenv_path = base_dir / ".env"
    
    try:
        # Try to use python-dotenv if installed
        try:
            from dotenv import load_dotenv
            logger.info(f"Loading environment variables from {dotenv_path}")
            return load_dotenv(dotenv_path=dotenv_path)
        except ImportError:
            # Fallback to manual loading
            logger.info(f"python-dotenv not installed, using manual .env parsing")
            if not os.path.isfile(dotenv_path):
                logger.warning(f".env file not found at {dotenv_path}")
                return False
                
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")
                    except ValueError:
                        logger.warning(f"Invalid line in .env file: {line}")
            return True
            
    except Exception as e:
        logger.warning(f"Error loading .env file: {e}")
        return False