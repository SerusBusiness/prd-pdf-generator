"""
PRD Processor module - Core orchestrator for PRD generation
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from prd_generator.core.logging_setup import setup_logging, get_logger
from prd_generator.core.config import Config
from prd_generator.core.content_generator import ContentGenerator
from prd_generator.core.asset_generator import AssetGenerator
from prd_generator.core.reference_search_manager import ReferenceSearchManager
from prd_generator.formatters.content_normalizer import ContentNormalizer
from prd_generator.utils.ollama_client import OllamaClient
from prd_generator.utils.pdf_generator import PDFGenerator

# Initialize logger
logger = get_logger(__name__)

class PRDProcessor:
    """
    Main orchestrator class for the PRD generation workflow.
    Coordinates all components of the PRD generation process.
    """

    def __init__(self, config: Config):
        """
        Initialize the PRD processor with configuration.
        
        Args:
            config: Configuration settings
        """
        self.config = config
        
        # Initialize Ollama client
        self.ollama_client = OllamaClient(config)
        
        # Initialize core components
        self.content_generator = ContentGenerator(config, self.ollama_client)
        self.content_normalizer = ContentNormalizer()
        self.asset_generator = AssetGenerator(config, self.content_generator)
        self.reference_search_manager = ReferenceSearchManager(config)
        self.pdf_generator = PDFGenerator(config)
        
        logger.info(f"PRD Processor initialized with Ollama model: {config.ollama_model}")
        
    def process_prd(self, prompt_text: str, output_path: str) -> str:
        """
        Process the complete PRD generation workflow from input prompt to final PDF.
        
        Args:
            prompt_text: The input text prompt for PRD generation
            output_path: Path where the output PDF should be saved
            
        Returns:
            str: Path to the generated PDF file
        """
        # Start timing the process
        start_time = datetime.now()
        logger.info(f"Starting PRD generation process at {start_time}")
        
        try:
            # Create temporary directory for asset generation
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"Using temporary directory for assets: {temp_dir}")
                
                # Step 1: Generate structured PRD content from prompt
                logger.info("Step 1: Generating PRD content from prompt")
                try:
                    prd_content = self.content_generator.generate_content(prompt_text)
                except Exception as e:
                    logger.error(f"Error in content generation: {e}", exc_info=True)
                    # Create minimal content to allow process to continue
                    prd_content = self._create_fallback_content(prompt_text, str(e))
                
                # Step 2: Normalize the content structure
                logger.info("Step 2: Normalizing content structure")
                try:
                    normalized_content = self.content_normalizer.normalize(prd_content)
                except Exception as e:
                    logger.error(f"Error in content normalization: {e}", exc_info=True)
                    # Use original content if normalization fails
                    normalized_content = prd_content
                
                # Step 3: Generate search terms for references
                logger.info("Step 3: Getting search terms for references")
                search_terms = None
                if self.config.enable_search:
                    try:
                        search_terms = self.content_generator.generate_search_terms(prd_content)
                    except Exception as e:
                        logger.error(f"Error generating search terms: {e}", exc_info=True)
                
                # Prepare assets and references collections
                assets = {"images": [], "diagrams": []}
                references = []
                
                # Step 4: Generate images and diagrams
                if self.config.generate_images or self.config.generate_diagrams:
                    logger.info("Step 4: Generating assets (images and diagrams)")
                    try:
                        assets = self.asset_generator.generate_assets(prd_content, temp_dir)
                    except Exception as e:
                        logger.error(f"Error generating assets: {e}", exc_info=True)
                
                # Step 5: Search for references
                if self.config.enable_search and search_terms:
                    logger.info("Step 5: Searching for references")
                    try:
                        references = self.reference_search_manager.search_references(prd_content, search_terms)
                    except Exception as e:
                        logger.error(f"Error searching references: {e}", exc_info=True)
                
                # Step 6: Generate the final PDF document
                logger.info("Step 6: Generating PDF document")
                try:
                    self.pdf_generator.generate_pdf(
                        normalized_content, 
                        output_path,
                        image_files=assets.get('images', []),
                        diagram_files=assets.get('diagrams', []),
                        references=references
                    )
                except Exception as e:
                    logger.error(f"Error generating PDF: {e}", exc_info=True)
                    # Try with minimal content as last resort
                    self._generate_error_pdf(prompt_text, output_path, str(e))
                
                # Calculate and log total processing time
                end_time = datetime.now()
                processing_time = end_time - start_time
                logger.info(f"PRD generation completed in {processing_time.total_seconds():.2f} seconds")
                
                return output_path
                
        except Exception as e:
            logger.error(f"Error during PRD generation: {e}", exc_info=True)
            # Create a minimal error document
            try:
                self._generate_error_pdf(prompt_text, output_path, str(e))
                return output_path
            except:
                raise RuntimeError(f"PRD generation failed completely: {e}")
    
    def _create_fallback_content(self, prompt_text: str, error_message: str) -> Dict[str, Any]:
        """Create minimal content structure when generation fails."""
        fallback_content = {
            "Executive Summary": f"Document generated from prompt with errors. Original prompt: {prompt_text[:100]}...",
            "Problem Statement": "The document generation encountered technical issues.",
            "Error Information": f"Error details: {error_message}",
        }
        
        # Add all required sections with placeholder content
        for section in self.config.prd_sections:
            if section not in fallback_content:
                fallback_content[section] = "Content generation failed for this section."
        
        return fallback_content
    
    def _generate_error_pdf(self, prompt_text: str, output_path: str, error_message: str):
        """Generate a minimal PDF when regular generation fails."""
        minimal_content = {
            "Document Generation Error": f"Failed to generate complete PRD document.\n\nError: {error_message}\n\nOriginal prompt: {prompt_text[:250]}..."
        }
        
        # Use direct reportlab creation to ensure this works
        try:
            self.pdf_generator.generate_pdf(minimal_content, output_path)
        except Exception as pdf_error:
            # Last resort: try to create a very basic PDF
            logger.error(f"Error creating error PDF: {pdf_error}", exc_info=True)
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(output_path)
            c.drawString(100, 750, "Document Generation Error")
            c.drawString(100, 730, f"Error: {error_message[:50]}...")
            c.drawString(100, 710, f"Original prompt: {prompt_text[:50]}...")
            c.save()