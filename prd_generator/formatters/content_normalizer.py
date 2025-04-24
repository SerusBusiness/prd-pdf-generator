"""
Content Normalizer for PRD Generator.
Handles normalization and cleaning of content for PRD documents.
"""
import re
from typing import Dict, Any, Optional, List, Union

from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class ContentNormalizer:
    """
    Handles normalization and cleaning of content for PRD documents.
    Ensures consistent formatting and resolves common content issues.
    """
    
    def __init__(self, config=None):
        """
        Initialize the content normalizer.
        
        Args:
            config: Optional configuration settings
        """
        self.config = config
        logger.info("Content normalizer initialized")
        
    def normalize(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean content dictionary.
        
        Args:
            content: Raw content dictionary
            
        Returns:
            Dict: Normalized content dictionary
        """
        if not content:
            logger.warning("Empty content provided for normalization")
            return {}
        
        # Create a copy to avoid modifying the original
        normalized = content.copy()
        
        # Process each section
        for section, text in normalized.items():
            # Skip non-string values and sections starting with underscore
            if not isinstance(text, str) or section.startswith('_'):
                continue
                
            # Apply normalization steps
            normalized_text = self._normalize_text(text)
            normalized[section] = normalized_text
            
        # Make sure all required sections are present
        if self.config and hasattr(self.config, 'prd_sections'):
            for section in self.config.prd_sections:
                if section not in normalized:
                    logger.warning(f"Missing required section: {section}")
                    normalized[section] = ""
        
        # Process special fields
        if 'image_suggestions' in normalized:
            normalized['image_suggestions'] = self._normalize_list(normalized['image_suggestions'])
            
        if 'diagrams' in normalized:
            normalized['diagrams'] = self._normalize_diagrams(normalized['diagrams'])
            
        logger.debug("Content normalization complete")
        return normalized
        
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text content.
        
        Args:
            text: Raw text content
            
        Returns:
            str: Normalized text content
        """
        if not text:
            return ""
            
        # Convert to string if not already
        text = str(text)
        
        # Remove excess whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Fix common markdown issues
        text = self._fix_markdown_formatting(text)
        
        # Fix newlines (ensure consistent line breaks)
        text = text.replace('\r\n', '\n')
        
        # Remove thinking tags if configured
        if self.config and hasattr(self.config, 'handle_thinking') and self.config.handle_thinking:
            if not self.config.keep_thinking:
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        return text
        
    def _normalize_list(self, items: Union[List, str]) -> List[str]:
        """
        Normalize list content.
        
        Args:
            items: List of items or string to convert to list
            
        Returns:
            List[str]: Normalized list of items
        """
        result = []
        
        if isinstance(items, str):
            # Split string by newlines or bullet points
            lines = re.split(r'[\n•-]+', items)
            for line in lines:
                line = line.strip()
                if line:
                    result.append(line)
        elif isinstance(items, list):
            # Clean each item in the list
            for item in items:
                if item:
                    cleaned = str(item).strip()
                    if cleaned:
                        result.append(cleaned)
        else:
            logger.warning(f"Expected list or string, got {type(items)}")
        
        return result
        
    def _normalize_diagrams(self, diagrams: Union[List[Dict], Dict, str]) -> List[Dict]:
        """
        Normalize diagram definitions.
        
        Args:
            diagrams: Diagram definitions in various formats
            
        Returns:
            List[Dict]: Normalized list of diagram definitions
        """
        result = []
        
        try:
            if isinstance(diagrams, str):
                # Try to extract diagram from text block
                diagram = self._extract_diagram_from_text(diagrams)
                if diagram:
                    result.append(diagram)
            elif isinstance(diagrams, dict):
                # Single diagram as dictionary
                normalized = self._normalize_diagram(diagrams)
                if normalized:
                    result.append(normalized)
            elif isinstance(diagrams, list):
                # List of diagrams
                for diagram in diagrams:
                    if isinstance(diagram, dict):
                        normalized = self._normalize_diagram(diagram)
                        if normalized:
                            result.append(normalized)
                    elif isinstance(diagram, str):
                        extracted = self._extract_diagram_from_text(diagram)
                        if extracted:
                            result.append(extracted)
                    else:
                        logger.warning(f"Unexpected diagram type: {type(diagram)}")
            else:
                logger.warning(f"Unexpected diagrams type: {type(diagrams)}")
        except Exception as e:
            logger.error(f"Error normalizing diagrams: {e}")
            
        return result
        
    def _normalize_diagram(self, diagram: Dict) -> Optional[Dict]:
        """
        Normalize a single diagram definition.
        
        Args:
            diagram: Diagram definition dictionary
            
        Returns:
            Optional[Dict]: Normalized diagram definition or None if invalid
        """
        if not diagram:
            return None
            
        result = {}
        
        # Get title
        title = diagram.get('title', '')
        if not title:
            title = diagram.get('name', 'Untitled Diagram')
        result['title'] = title
        
        # Get Mermaid code
        mermaid_code = diagram.get('mermaid_code', '')
        if not mermaid_code:
            mermaid_code = diagram.get('code', '')
            
        if not mermaid_code:
            return None
            
        # Normalize mermaid code
        result['mermaid_code'] = self._normalize_mermaid_code(mermaid_code)
        
        return result
        
    def _extract_diagram_from_text(self, text: str) -> Optional[Dict]:
        """
        Extract diagram definition from text.
        
        Args:
            text: Text containing diagram definition
            
        Returns:
            Optional[Dict]: Extracted diagram definition or None if not found
        """
        # Try to extract title
        title_match = re.search(r'(.*?)(?:diagram|chart|graph|flow|sequence)', text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Untitled Diagram"
        
        # Try to extract Mermaid code
        code_match = re.search(r'```(?:mermaid)?\s*(graph|sequenceDiagram|classDiagram|flowchart|erDiagram|gantt|pie|stateDiagram).*?```', 
                              text, re.DOTALL | re.IGNORECASE)
                              
        if not code_match:
            # Try alternative format
            code_match = re.search(r'(graph|sequenceDiagram|classDiagram|flowchart|erDiagram|gantt|pie|stateDiagram).*?;', 
                                 text, re.DOTALL | re.IGNORECASE)
        
        if code_match:
            mermaid_code = code_match.group(0)
            
            # Clean up code
            mermaid_code = re.sub(r'```(?:mermaid)?\s*', '', mermaid_code)
            mermaid_code = re.sub(r'```\s*$', '', mermaid_code)
            
            return {
                'title': title,
                'mermaid_code': self._normalize_mermaid_code(mermaid_code)
            }
            
        return None
        
    def _normalize_mermaid_code(self, code: str) -> str:
        """
        Normalize Mermaid diagram code.
        
        Args:
            code: Mermaid code to normalize
            
        Returns:
            str: Normalized Mermaid code
        """
        # Remove any markdown code markers
        code = re.sub(r'```(?:mermaid)?\s*', '', code)
        code = re.sub(r'```\s*$', '', code)
        
        # Trim whitespace
        code = code.strip()
        
        return code
        
    def _fix_markdown_formatting(self, text: str) -> str:
        """
        Fix common markdown formatting issues.
        
        Args:
            text: Text to fix
            
        Returns:
            str: Fixed text
        """
        # Fix headers without space after #
        text = re.sub(r'(#{1,6})([^\s#])', r'\1 \2', text)
        
        # Add spacing around bold/italic markers for better rendering
        text = re.sub(r'([^\s*])\*\*([^\s*])', r'\1 **\2', text)
        text = re.sub(r'([^\s*])\*([^\s*])', r'\1 *\2', text)
        text = re.sub(r'([^\s_])__([^\s_])', r'\1 __\2', text)
        text = re.sub(r'([^\s_])_([^\s_])', r'\1 _\2', text)
        
        # Ensure proper list formatting
        text = re.sub(r'(?<!\n)\n([\*\-\+] )', r'\n\n\1', text)
        
        # Ensure proper quote formatting
        text = re.sub(r'(?<!\n)\n(> )', r'\n\n\1', text)
        
        return text