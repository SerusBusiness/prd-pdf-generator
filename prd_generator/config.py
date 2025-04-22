"""
Configuration module for the PRD Generator.
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration settings for the PRD Generator."""
    # Ollama settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    
    # API keys
    pixabay_api_key: str = ""  # API key for Pixabay image search
    
    # Feature flags
    enable_search: bool = True
    generate_images: bool = True
    generate_diagrams: bool = True
    
    # PDF settings
    page_width: float = 595.27  # A4 width in points
    page_height: float = 841.89  # A4 height in points
    margin: float = 50.0
    
    # PRD sections to include (can be customized)
    prd_sections: list[str] = None
    
    # Mermaid diagram service settings
    mermaid_service_url: str = "http://localhost:3000/convert/image"
    
    def __post_init__(self):
        # Default PRD sections if none provided
        if self.prd_sections is None:
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
        
        # Load from environment variables if present
        if os.environ.get("OLLAMA_HOST"):
            self.ollama_host = os.environ["OLLAMA_HOST"]
        
        if os.environ.get("OLLAMA_MODEL"):
            self.ollama_model = os.environ["OLLAMA_MODEL"]
            
        # Load API keys from environment variables
        if os.environ.get("PIXABAY_API_KEY"):
            self.pixabay_api_key = os.environ["PIXABAY_API_KEY"]
        
        # Load Mermaid service URL from environment variables
        if os.environ.get("MERMAID_SERVICE_URL"):
            self.mermaid_service_url = os.environ["MERMAID_SERVICE_URL"]