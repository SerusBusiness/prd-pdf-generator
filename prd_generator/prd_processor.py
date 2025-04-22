"""
PRD Processor module - Core functionality for PRD generation
"""
import json
import os
from pathlib import Path
import tempfile

from prd_generator.config import Config
from prd_generator.utils.ollama_client import OllamaClient
from prd_generator.utils.pdf_generator import PDFGenerator
from prd_generator.utils.reference_search import ReferenceSearch
from prd_generator.utils.diagram_generator import DiagramGenerator
from prd_generator.utils.image_generator import ImageGenerator


class PRDProcessor:
    """Main processor class for handling the PRD generation workflow."""

    def __init__(self, config: Config):
        """Initialize the PRD processor with configuration."""
        self.config = config
        self.ollama_client = OllamaClient(config)
        self.pdf_generator = PDFGenerator(config)
        
        # Initialize optional components based on config
        self.reference_search = ReferenceSearch() if config.enable_search else None
        self.diagram_generator = DiagramGenerator(config) if config.generate_diagrams else None
        
        # Initialize ImageGenerator with API key if images are enabled
        self.image_generator = None
        if config.generate_images:
            self.image_generator = ImageGenerator()
            # Pass the Pixabay API key if available
            if hasattr(config, 'pixabay_api_key') and config.pixabay_api_key:
                os.environ["PIXABAY_API_KEY"] = config.pixabay_api_key
        
        # Path to the pre-generated AI content
        self.ai_generated_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'ai_generated.txt')
    
    def process_prd(self, prompt_text: str, output_path: str):
        """
        Process the PRD generation workflow from input prompt to final PDF.
        
        Args:
            prompt_text: The input text prompt for PRD generation
            output_path: Path where the output PDF should be saved
        """
        # Create temporary directory for asset generation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: Generate structured PRD content from prompt
            prd_content = self._generate_prd_content(prompt_text)
            
            # Step 2: Generate images and diagrams if enabled
            image_files = []
            diagram_files = []
            
            if self.config.generate_images:
                image_files = self._generate_images(prd_content, temp_dir)
            
            if self.config.generate_diagrams:
                diagram_files = self._generate_diagrams(prd_content, temp_dir)
            
            # Step 3: Search for references if enabled
            references = []
            if self.config.enable_search:
                references = self._search_references(prd_content)
            
            # Step 4: Generate the final PDF document
            self.pdf_generator.generate_pdf(
                prd_content, 
                output_path,
                image_files=image_files,
                diagram_files=diagram_files,
                references=references
            )
    
    def _generate_prd_content(self, prompt_text: str) -> dict:
        """
        Generate structured PRD content using the LLM.
        
        Args:
            prompt_text: The input text prompt for PRD generation
            
        Returns:
            dict: Structured PRD content organized by sections
        """
        # First check if we have a pre-generated AI content file
        if os.path.exists(self.ai_generated_path):
            try:
                print(f"Using pre-generated AI content from {self.ai_generated_path}")
                with open(self.ai_generated_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error reading pre-generated content: {e}")
                print("Falling back to Ollama API")
        
        # If no pre-generated content or error reading it, fall back to original method
        # Construct the prompt for the LLM with proper instructions
        system_prompt = """
        You are a specialized Product Requirements Document (PRD) generator. 
        Your task is to take a brief product idea or concept and expand it into a comprehensive PRD.
        
        Generate a detailed PRD with the following sections:
        - Executive Summary: Brief overview of the product
        - Problem Statement: Clear description of the problem being solved
        - Target Users: Who will use this product
        - Product Goals: What the product aims to achieve
        - Requirements & Features: Detailed functionality requirements
        - User Stories: Key user journeys and scenarios
        - Technical Requirements: Technical specifications and constraints
        - Architecture: High-level system design and architecture
        - Implementation Plan: Timeline and development approach
        - Success Metrics: How to measure product success
        - Risks & Mitigation: Potential issues and how to address them
        - References: Relevant external information sources
        
        For each section, provide detailed, specific content based on the input.
        Include specific feature descriptions, implementation details, and technical specifications where appropriate.
        
        Respond with a JSON structure where keys are section names and values are the content.
        For diagrams, include a key called "diagrams" that contains an array of objects with "title", "type" (sequence/flowchart/class/etc), 
        and "mermaid_code" for each diagram to be generated.
        
        For images, include a key called "image_suggestions" that has descriptions for images that would enhance understanding.
        
        For references, add relevant topics to search for in a "search_terms" array.
        """
        
        # Prepare the actual LLM prompt
        prompt = f"{system_prompt}\n\nHere is the product idea to expand into a PRD:\n\n{prompt_text}"
        
        # Get response from Ollama
        response = self.ollama_client.generate(prompt)
        
        # Parse JSON response
        try:
            # Try to extract JSON from the response
            content_start = response.find('{')
            content_end = response.rfind('}') + 1
            
            if content_start >= 0 and content_end > content_start:
                json_content = response[content_start:content_end]
                prd_content = json.loads(json_content)
            else:
                # If no JSON found, use a structured approach to parse the response
                prd_content = self._parse_unstructured_response(response)
                
            return prd_content
            
        except json.JSONDecodeError:
            # Fallback for when the LLM doesn't return valid JSON
            return self._parse_unstructured_response(response)
    
    def _parse_unstructured_response(self, response: str) -> dict:
        """Parse an unstructured response into a structured PRD content dictionary."""
        prd_content = {}
        current_section = None
        content_lines = []
        
        # Simple parsing based on section headers
        for line in response.split('\n'):
            line = line.strip()
            
            # Check if this is a section header (matches one of our expected sections)
            is_section_header = False
            for section in self.config.prd_sections:
                if line.lower().startswith(section.lower()) or line.lower() == section.lower():
                    if current_section:
                        prd_content[current_section] = '\n'.join(content_lines).strip()
                    current_section = section
                    content_lines = []
                    is_section_header = True
                    break
            
            if not is_section_header and current_section:
                content_lines.append(line)
        
        # Don't forget the last section
        if current_section and content_lines:
            prd_content[current_section] = '\n'.join(content_lines).strip()
            
        # Add empty placeholders for required sections
        for section in self.config.prd_sections:
            if section not in prd_content:
                prd_content[section] = ""
        
        return prd_content
    
    def _generate_images(self, prd_content: dict, temp_dir: str) -> list:
        """Generate images based on the PRD content."""
        image_files = []
        
        # Check if image_suggestions are provided
        if "image_suggestions" in prd_content and isinstance(prd_content["image_suggestions"], list):
            for i, suggestion in enumerate(prd_content["image_suggestions"]):
                if isinstance(suggestion, str):
                    img_path = os.path.join(temp_dir, f"image_{i+1}.png")
                    if self.image_generator.generate_image(suggestion, img_path):
                        # Validate the image before adding it to our file list
                        try:
                            from PIL import Image
                            # Try to open the image to verify it's valid
                            with Image.open(img_path) as img:
                                # Force load to verify
                                img.load()
                                # If we succeed, add to our list
                                image_files.append({
                                    'path': img_path,
                                    'description': suggestion,
                                    'section': self._determine_section_for_image(suggestion, prd_content)
                                })
                        except Exception as e:
                            print(f"Skipping invalid image {img_path}: {e}")
        
        return image_files
    
    def _determine_section_for_image(self, image_description: str, prd_content: dict) -> str:
        """Determine which section an image belongs to based on its description."""
        # Simple algorithm - match keywords in description to sections
        for section, content in prd_content.items():
            if section in self.config.prd_sections:
                # Check if there are significant keyword matches
                keywords = self._extract_keywords(content)
                description_words = set(image_description.lower().split())
                
                # Calculate overlap
                overlap = len(description_words.intersection(keywords))
                if overlap > 2:  # If more than 2 significant keywords match
                    return section
        
        # Default to Architecture section if no match
        return "Architecture"
    
    def _extract_keywords(self, text: str) -> set:
        """Extract significant keywords from text."""
        # Simple implementation - split and filter common words
        common_words = {'the', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
        return set(word.lower() for word in text.split() if word.lower() not in common_words and len(word) > 3)
    
    def _generate_diagrams(self, prd_content: dict, temp_dir: str) -> list:
        """Generate diagrams based on the PRD content."""
        diagram_files = []
        
        # Check if diagrams are provided
        if "diagrams" in prd_content and isinstance(prd_content["diagrams"], list):
            for i, diagram in enumerate(prd_content["diagrams"]):
                if isinstance(diagram, dict) and "mermaid_code" in diagram:
                    diagram_path = os.path.join(temp_dir, f"diagram_{i+1}.png")
                    
                    title = diagram.get("title", f"Diagram {i+1}")
                    diagram_type = diagram.get("type", "flowchart")
                    mermaid_code = diagram["mermaid_code"]
                    
                    if self.diagram_generator.generate_diagram(mermaid_code, diagram_path):
                        diagram_files.append({
                            'path': diagram_path,
                            'title': title,
                            'type': diagram_type,
                            'section': diagram.get("section", "Architecture")
                        })
        else:
            # If no diagrams specified, generate at least one architecture diagram
            if "Architecture" in prd_content:
                arch_description = prd_content["Architecture"]
                # Ask LLM to create a Mermaid diagram based on architecture description
                prompt = f"Create a mermaid diagram for the following architecture description. Respond with only the mermaid code:\n\n{arch_description}"
                
                mermaid_code = self.ollama_client.generate(prompt)
                # Extract just the mermaid code from response
                if "```mermaid" in mermaid_code:
                    start = mermaid_code.find("```mermaid") + 10
                    end = mermaid_code.find("```", start)
                    if end > start:
                        mermaid_code = mermaid_code[start:end].strip()
                
                diagram_path = os.path.join(temp_dir, "architecture_diagram.png")
                if self.diagram_generator.generate_diagram(mermaid_code, diagram_path):
                    diagram_files.append({
                        'path': diagram_path,
                        'title': "System Architecture",
                        'type': "flowchart",
                        'section': "Architecture"
                    })
        
        return diagram_files
    
    def _search_references(self, prd_content: dict) -> list:
        """Search for relevant references based on PRD content."""
        references = []
        
        # Get search terms if available
        search_terms = []
        if "search_terms" in prd_content and isinstance(prd_content["search_terms"], list):
            search_terms.extend(prd_content["search_terms"])
        else:
            # Extract key terms from content
            if "Executive Summary" in prd_content:
                # Get key terms from executive summary
                summary = prd_content["Executive Summary"]
                # Simple extraction of key phrases
                key_terms = [term.strip() for term in summary.split('.') if len(term.strip()) > 10]
                search_terms.extend(key_terms[:3])  # Take up to 3 key phrases
            
            if "Technical Requirements" in prd_content:
                # Add technical terms
                tech_req = prd_content["Technical Requirements"]
                tech_terms = [term.strip() for term in tech_req.split('\n') if len(term.strip()) > 10]
                search_terms.extend(tech_terms[:3])
        
        # Perform the search
        for term in search_terms:
            results = self.reference_search.search(term, max_results=2)
            references.extend(results)
        
        return references