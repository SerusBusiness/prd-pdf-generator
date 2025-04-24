"""
Asset Generator for PRD Generator.
Handles the generation of assets like images and diagrams for PRD documents.
"""
import os
import re
import io
from typing import Dict, Any, Optional, List, Tuple, Callable
from pathlib import Path

from prd_generator.utils.image_generator import ImageGenerator
from prd_generator.utils.diagram_generator import DiagramGenerator
from prd_generator.utils.progress_reporter import ProgressReporter
from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class AssetGenerator:
    """
    Handles generation of assets like images and diagrams for PRD documents.
    Now supports parallel processing and progress reporting.
    """
    
    def __init__(self, config, content_generator):
        """
        Initialize the asset generator with configuration.
        
        Args:
            config: Configuration settings
            content_generator: ContentGenerator instance for generating architecture diagrams
        """
        self.config = config
        self.content_generator = content_generator
        
        # Initialize image and diagram generators with proper error handling
        try:
            self.image_generator = ImageGenerator(max_workers=4)  # Allow 4 parallel image generations
            logger.debug("ImageGenerator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ImageGenerator: {e}")
            self.image_generator = None
            
        try:
            self.diagram_generator = DiagramGenerator(config=config)  # Pass the config object correctly
            logger.debug("DiagramGenerator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DiagramGenerator: {e}")
            self.diagram_generator = None
        
        logger.info("Asset generator initialized")
    
    def generate_assets(self, prd_content: Dict[str, Any], output_dir: str, 
                       progress_callback: Optional[Callable] = None) -> Dict[str, List]:
        """
        Generate all assets needed for the PRD document.
        
        Args:
            prd_content: PRD content dictionary
            output_dir: Directory to save generated assets
            progress_callback: Optional callback function to report progress
            
        Returns:
            Dict: Dictionary containing lists of generated assets
        """
        # Create output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            # Return empty result if we can't create the output directory
            return {'images': [], 'diagrams': []}
        
        # Create a progress reporter
        total_steps = 100
        reporter = ProgressReporter(total_steps, "Generating Assets", progress_callback)
        
        # Initialize result containers
        result = {
            'images': [],
            'diagrams': []
        }
        
        # Report initial progress
        reporter.update(5, "Starting asset generation")
        
        # Generate images if enabled and image generator is available
        if self.config.generate_images and self.image_generator is not None:
            # Extract image suggestions from content
            image_suggestions = self._extract_image_suggestions(prd_content)
            
            if image_suggestions:
                logger.info(f"Generating {len(image_suggestions)} images")
                reporter.update(5, f"Preparing to generate {len(image_suggestions)} images")
                
                # Create images directory
                images_dir = os.path.join(output_dir, "images")
                try:
                    os.makedirs(images_dir, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create images directory {images_dir}: {e}")
                    reporter.update(40, "Failed to create images directory")
                else:
                    # Define a progress callback for image generation
                    def image_progress(completed, total, message):
                        # Map image generation progress to overall progress (40% of total)
                        progress = (completed / max(1, total)) * 40
                        reporter.update(int(progress), message)
                    
                    # Generate images in parallel with progress reporting
                    try:
                        images = self.image_generator.generate_images_parallel(
                            image_suggestions, 
                            images_dir,
                            progress_callback=image_progress
                        )
                        
                        # Process the generated images
                        for i, img_info in enumerate(images):
                            if img_info is None:
                                continue
                                
                            # Verify the image file exists
                            if not self._verify_file_exists(img_info.get('path', '')):
                                logger.warning(f"Generated image file does not exist: {img_info.get('path')}")
                                continue
                                
                            # Determine which section this image belongs to
                            try:
                                img_description = img_info['description']
                                section = self._determine_section_for_image(img_description, prd_content)
                                
                                # Add section to image info
                                img_info['section'] = section
                                result['images'].append(img_info)
                            except Exception as e:
                                logger.error(f"Error processing image {i}: {e}")
                                
                        reporter.update(40, f"Generated {len(result['images'])} images")
                    except Exception as e:
                        logger.error(f"Error generating images: {e}")
                        reporter.update(40, f"Error generating images: {str(e)}")
            else:
                reporter.update(40, "No images to generate")
        else:
            if not self.config.generate_images:
                reporter.update(40, "Image generation disabled")
            else:
                reporter.update(40, "Image generator not available")
            
        # Generate diagrams if enabled and diagram generator is available
        if self.config.generate_diagrams and self.diagram_generator is not None:
            # Extract diagram definitions from content
            try:
                diagrams = self._extract_diagrams(prd_content)
                
                # If no diagrams but we have an Architecture section, generate a diagram for it
                if not diagrams and 'Architecture' in prd_content:
                    arch_content = prd_content['Architecture']
                    if arch_content and isinstance(arch_content, str) and self.content_generator is not None:
                        logger.info("Generating architecture diagram")
                        reporter.update(5, "Generating architecture diagram")
                        
                        try:
                            # Generate mermaid diagram code
                            mermaid_code = self.content_generator.generate_architecture_diagram(arch_content)
                            
                            if mermaid_code:
                                diagrams = [{
                                    'title': "System Architecture",
                                    'mermaid_code': mermaid_code
                                }]
                        except Exception as e:
                            logger.error(f"Error generating architecture diagram: {e}")
                            reporter.update(5, f"Error generating architecture diagram: {str(e)}")
                
                if diagrams:
                    logger.info(f"Generating {len(diagrams)} diagrams")
                    reporter.update(5, f"Preparing to generate {len(diagrams)} diagrams")
                    
                    # Create diagrams directory
                    diagrams_dir = os.path.join(output_dir, "diagrams")
                    try:
                        os.makedirs(diagrams_dir, exist_ok=True)
                    except Exception as e:
                        logger.error(f"Failed to create diagrams directory {diagrams_dir}: {e}")
                        reporter.update(40, "Failed to create diagrams directory")
                    else:
                        # Track progress for diagrams (50% of remaining progress)
                        diagram_step_size = 40 / max(1, len(diagrams))
                        
                        for i, diagram in enumerate(diagrams):
                            title = diagram.get('title', f"Diagram {i+1}")
                            mermaid_code = diagram.get('mermaid_code', '')
                            
                            if not mermaid_code:
                                logger.warning(f"Empty mermaid code for diagram: {title}")
                                continue
                                
                            reporter.update(0, f"Generating diagram: {title}")
                            
                            try:
                                # Create filename for the diagram
                                sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', title).lower()
                                diagram_path = os.path.join(diagrams_dir, f"{sanitized_title}.png")
                                
                                # Generate the diagram
                                success = self.diagram_generator.generate_diagram(mermaid_code, diagram_path)
                                
                                if success and self._verify_file_exists(diagram_path):
                                    try:
                                        # Validate the diagram
                                        from PIL import Image
                                        with Image.open(diagram_path) as img:
                                            width, height = img.size
                                            
                                            # Determine the most appropriate section for this diagram
                                            section = self._determine_section_for_diagram(title, prd_content)
                                            
                                            # Add to result
                                            result['diagrams'].append({
                                                'path': diagram_path,
                                                'title': title,
                                                'width': width,
                                                'height': height,
                                                'section': section,
                                                'type': self._determine_diagram_type(mermaid_code)
                                            })
                                            
                                            reporter.update(diagram_step_size, f"Generated diagram: {title}")
                                    except Exception as e:
                                        logger.error(f"Invalid diagram at {diagram_path}: {e}")
                                        
                                        # Create a placeholder entry if we failed to open the image
                                        result['diagrams'].append({
                                            'path': diagram_path,
                                            'title': title,
                                            'width': 800,  # Default width
                                            'height': 600, # Default height
                                            'section': self._determine_section_for_diagram(title, prd_content),
                                            'type': self._determine_diagram_type(mermaid_code),
                                            'error': str(e)
                                        })
                                else:
                                    logger.warning(f"Failed to generate diagram: {title}")
                            except Exception as e:
                                logger.error(f"Error processing diagram {title}: {e}")
                else:
                    reporter.update(40, "No diagrams to generate")
            except Exception as e:
                logger.error(f"Error in diagram generation process: {e}")
                reporter.update(40, f"Error in diagram generation: {str(e)}")
        else:
            if not self.config.generate_diagrams:
                reporter.update(40, "Diagram generation disabled")
            else:
                reporter.update(40, "Diagram generator not available")
            
        # Complete progress
        reporter.complete("Asset generation completed")
        
        logger.info(f"Asset generation complete. Generated {len(result['images'])} images and {len(result['diagrams'])} diagrams")
        return result
    
    def _extract_image_suggestions(self, prd_content: Dict[str, Any]) -> List[str]:
        """
        Extract image suggestions from PRD content.
        
        Args:
            prd_content: PRD content dictionary
            
        Returns:
            List of image suggestion strings
        """
        image_suggestions = []
        
        # Direct image suggestions
        if 'image_suggestions' in prd_content and isinstance(prd_content['image_suggestions'], list):
            image_suggestions.extend(prd_content['image_suggestions'])
            
        # Legacy format support (sometimes nested under 'images' key)
        if 'images' in prd_content:
            if isinstance(prd_content['images'], list):
                image_suggestions.extend(prd_content['images'])
            elif isinstance(prd_content['images'], dict) and 'suggestions' in prd_content['images']:
                if isinstance(prd_content['images']['suggestions'], list):
                    image_suggestions.extend(prd_content['images']['suggestions'])
        
        return image_suggestions
    
    def _extract_diagrams(self, prd_content: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract diagram definitions from PRD content.
        
        Args:
            prd_content: PRD content dictionary
            
        Returns:
            List of diagram definition dictionaries
        """
        diagrams = []
        
        # Direct diagrams list
        if 'diagrams' in prd_content and isinstance(prd_content['diagrams'], list):
            diagrams.extend(prd_content['diagrams'])
            
        # Legacy format support
        if 'diagrams' in prd_content and isinstance(prd_content['diagrams'], dict):
            for title, code in prd_content['diagrams'].items():
                if isinstance(code, str):
                    diagrams.append({
                        'title': title,
                        'mermaid_code': code
                    })
                    
        return diagrams
    
    def _verify_file_exists(self, file_path: str) -> bool:
        """
        Verify if a file exists and has content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if file exists and has content
        """
        if not file_path:
            return False
            
        try:
            path = Path(file_path)
            return path.exists() and path.is_file() and path.stat().st_size > 0
        except Exception as e:
            logger.error(f"Error checking file existence {file_path}: {e}")
            return False
    
    def _determine_section_for_image(self, description: str, prd_content: Dict[str, Any]) -> str:
        """
        Determine which section an image belongs to based on its description.
        
        Args:
            description: Image description
            prd_content: PRD content dictionary
            
        Returns:
            str: Section name
        """
        if not description:
            return "Executive Summary"  # Default
            
        # Convert description to lowercase for matching
        desc_lower = description.lower()
        
        # Define section keywords mapping
        section_keywords = {
            'Executive Summary': ['overview', 'summary', 'introduction', 'executive'],
            'Problem Statement': ['problem', 'challenge', 'issue', 'pain point', 'pain-point'],
            'Target Users': ['user', 'customer', 'persona', 'market', 'audience', 'demographic'],
            'Requirements & Features': ['feature', 'requirement', 'capability', 'functionality', 'function'],
            'Architecture': ['architecture', 'system', 'component', 'diagram', 'design', 'structure'],
            'Technical Requirements': ['technical', 'technology', 'stack', 'platform', 'specification'],
            'User Stories': ['story', 'journey', 'task', 'scenario', 'use case', 'use-case'],
            'Implementation Plan': ['implementation', 'timeline', 'milestone', 'phase', 'roadmap', 'plan'],
            'Success Metrics': ['metric', 'kpi', 'success', 'measurement', 'analytics', 'goal']
        }
        
        # Try to match based on exact section name in description
        for section in prd_content.keys():
            if section.lower() in desc_lower:
                return section
        
        # Try to match based on keywords
        matched_sections = []
        for section, keywords in section_keywords.items():
            for keyword in keywords:
                if keyword in desc_lower and section in prd_content:
                    matched_sections.append(section)
                    break
        
        if matched_sections:
            # Return the first matched section
            return matched_sections[0]
            
        # Try to match with content
        for section, content in prd_content.items():
            # Skip non-string content or special keys
            if not isinstance(content, str) or section.startswith('_'):
                continue
                
            # Convert to lowercase for case-insensitive matching
            content_lower = content.lower()
            
            # Check if any significant word from the description appears in the content
            significant_words = [word for word in desc_lower.split() if len(word) > 4]
            for word in significant_words:
                if word in content_lower:
                    return section
        
        # Default to Executive Summary if it exists, otherwise first section
        if "Executive Summary" in prd_content:
            return "Executive Summary"
        elif len(prd_content) > 0:
            return list(prd_content.keys())[0]
        else:
            return "Executive Summary"  # Fallback
            
    def _determine_section_for_diagram(self, title: str, prd_content: Dict[str, Any]) -> str:
        """
        Determine which section a diagram belongs to based on its title.
        
        Args:
            title: Diagram title
            prd_content: PRD content dictionary
            
        Returns:
            str: Section name
        """
        title_lower = title.lower()
        
        # Mapping of common diagram titles to sections
        diagram_section_mapping = {
            'system architecture': 'Architecture',
            'architecture': 'Architecture',
            'component': 'Architecture',
            'class diagram': 'Architecture',
            'sequence': 'Architecture',
            'flow': 'Architecture',
            'process': 'Architecture',
            'user flow': 'User Stories',
            'user journey': 'User Stories',
            'timeline': 'Implementation Plan',
            'roadmap': 'Implementation Plan',
            'database': 'Technical Requirements',
            'entity relationship': 'Technical Requirements',
        }
        
        # Check for direct matches in the mapping
        for key, section in diagram_section_mapping.items():
            if key in title_lower and section in prd_content:
                return section
                
        # If Architecture section exists, prefer it for unknown diagrams
        if 'Architecture' in prd_content:
            return 'Architecture'
        elif 'Technical Requirements' in prd_content:
            return 'Technical Requirements'
        elif 'Executive Summary' in prd_content:
            return 'Executive Summary'
        elif len(prd_content) > 0:
            return list(prd_content.keys())[0]
        else:
            return "Architecture"  # Default fallback
            
    def _determine_diagram_type(self, mermaid_code: str) -> str:
        """
        Determine the type of diagram from mermaid code.
        
        Args:
            mermaid_code: Mermaid diagram code
            
        Returns:
            str: Diagram type
        """
        if not mermaid_code:
            return "flowchart"
            
        mermaid_code = mermaid_code.strip().lower()
        
        # Map starting keywords to diagram types
        diagram_types = {
            'sequencediagram': 'sequence',
            'classd': 'class',
            'erdiagram': 'er',
            'flowchart': 'flowchart',
            'graph': 'flowchart',
            'gantt': 'gantt',
            'pie': 'pie',
            'statediagram': 'state',
            'journey': 'journey'
        }
        
        for keyword, diagram_type in diagram_types.items():
            if mermaid_code.startswith(keyword):
                return diagram_type
                
        return "flowchart"  # Default