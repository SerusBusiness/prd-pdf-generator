"""
Content Generator for PRD Generator.
Handles interactions with LLMs to generate structured PRD content.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class ContentGenerator:
    """
    Handles the generation of PRD content from text prompts using LLMs.
    This class encapsulates all logic for interacting with LLMs and processing responses.
    """
    
    def __init__(self, config, ollama_client):
        """
        Initialize the content generator with configuration and Ollama client.
        
        Args:
            config: Configuration object
            ollama_client: Initialized Ollama client for LLM interactions
        """
        self.config = config
        self.ollama_client = ollama_client
        
    def generate_content(self, prompt_text: str) -> Dict[str, Any]:
        """
        Generate structured PRD content from a text prompt.
        
        Args:
            prompt_text: The text prompt describing the product
            
        Returns:
            Dict: Structured PRD content organized by sections
        """
        # First check if we should use pre-generated content
        prd_content = self._try_load_pregenerated()
        if prd_content:
            return prd_content
        
        # Otherwise generate fresh content using the LLM
        logger.info("Generating PRD content from prompt using Ollama")
        
        # Construct the prompt for the LLM
        full_prompt = self._construct_system_prompt(prompt_text)
        
        # Generate content using LLM
        raw_response = self._generate_from_llm(full_prompt)
        
        # Parse the response into structured content
        prd_content = self._parse_llm_response(raw_response)
        
        # Save debug information
        self._save_debug_files(prd_content, raw_response)
        
        return prd_content
    
    def _try_load_pregenerated(self) -> Optional[Dict[str, Any]]:
        """
        Try to load pre-generated AI content from file if enabled.
        
        Returns:
            Dict or None: Pre-generated content if available and enabled, None otherwise
        """
        if self.config.skip_ai_generated:
            return None
            
        ai_generated_path = self.config.data_dir / 'ai_generated.txt'
        
        if not ai_generated_path.exists():
            return None
            
        try:
            logger.info(f"Using pre-generated AI content from {ai_generated_path}")
            with open(ai_generated_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading pre-generated content: {e}")
            logger.info("Falling back to Ollama API")
            return None
    
    def _construct_system_prompt(self, user_prompt: str) -> str:
        """
        Construct a comprehensive system prompt for the LLM.
        
        Args:
            user_prompt: The user's product description prompt
            
        Returns:
            str: Full prompt for the LLM
        """
        system_prompt = """
        You are a specialized Product Requirements Document (PRD) generator with deep expertise in product management and technical documentation.
        Your task is to take a product idea or concept and transform it into a comprehensive, professional-grade PRD document.
        
        ### GOAL
        Create a detailed, specific, and actionable PRD that could be handed to a development team to implement.
        
        ### OUTPUT FORMAT
        Respond with a JSON structure where keys are section names and values contain the detailed content for that section.
        
        ### REQUIRED SECTIONS
        Generate the following sections (each with detailed, specific content):
        1. Executive Summary: Brief overview of product value proposition, target market, and unique selling points
        2. Problem Statement: Specific pain points being addressed with quantifiable impacts where possible
        3. Target Users: Primary and secondary personas with demographics, behaviors, needs, and goals
        4. Product Goals: Primary and secondary goals with specific success criteria (using SMART framework)
        5. Requirements & Features: Prioritized list with must-have vs nice-to-have features, acceptance criteria for each
        6. User Stories: Detailed user journeys with specific user flows in "As a... I want... So that..." format
        7. Technical Requirements: Specific technologies, standards, compatibility needs, and performance criteria
        8. Architecture: System design with components, interactions, data flows, and integration points
        9. Implementation Plan: Phased approach with milestones, dependencies, and resource requirements 
        10. Success Metrics: Key performance indicators with baseline values and target values
        11. Risks & Mitigation: Prioritized risks with probability/impact assessment and specific mitigation strategies
        12. References: Industry standards, competitive analysis, and relevant research
        
        ### ADDITIONAL CONTENT TO INCLUDE
        - "diagrams": Include an array of diagram objects with "title", "type", and "mermaid_code" fields for system architecture, user flows, etc.
        - "image_suggestions": Include 3-5 descriptive prompts for images that would enhance document understanding
        - "search_terms": Include 5-7 highly specific technical search terms for finding implementation references
        
        ### APPROACH
        1. First analyze the product domain and identify the specific industry, technologies, and business context
        2. For each section, provide concrete, specific details rather than generic statements
        3. Include quantitative metrics and specific criteria wherever possible
        4. Consider technical constraints, market realities, and implementation challenges
        5. Use industry-standard terminology relevant to the product domain
        6. Ensure logical consistency across all sections of the document
        
        ### EXAMPLES OF SPECIFICITY (DO INCLUDE THIS LEVEL OF DETAIL)
        - BAD (too generic): "The app should be fast and reliable"
        - GOOD (specific): "The app must load initial content within 2 seconds on 4G connections and maintain 99.9% uptime"
        
        - BAD (too generic): "Users will be able to search for products"
        - GOOD (specific): "Users will be able to search products by name, category, price range, and ratings, with autocomplete suggestions appearing after 3 characters"
        
        ### AVOID
        - Vague or generic statements without measurable criteria
        - Contradictions between different sections
        - Unrealistic or unachievable requirements
        - Focusing on solutions before clearly defining problems
        """
        
        # Prepare the actual LLM prompt
        full_prompt = f"{system_prompt}\n\nHere is the product idea to expand into a PRD:\n\n{user_prompt}"
        return full_prompt
    
    def _generate_from_llm(self, prompt: str) -> str:
        """
        Generate content from the LLM with appropriate error handling.
        
        Args:
            prompt: The full prompt to send to the LLM
            
        Returns:
            str: Raw response from the LLM
        """
        try:
            # Use the appropriate method based on configuration
            if self.config.extract_insights:
                # Use the method that separates reasoning from response
                result = self.ollama_client.generate_with_reasoning(prompt)
                response = result['response']
                reasoning = result.get('reasoning', '')
                
                # Optionally save reasoning to a separate file for analysis
                if reasoning:
                    reasoning_path = self.config.debug_dir / 'reasoning_process.txt'
                    try:
                        with open(reasoning_path, 'w', encoding='utf-8') as f:
                            f.write(reasoning)
                        logger.info(f"Saved model reasoning process to {reasoning_path}")
                    except IOError as e:
                        logger.warning(f"Could not save reasoning process: {e}")
                
                return response
            else:
                # Use standard generation
                return self.ollama_client.generate(prompt)
                
        except Exception as e:
            logger.error(f"Error generating content from LLM: {e}")
            raise RuntimeError(f"Failed to generate content using LLM: {e}")
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into structured PRD content.
        
        Args:
            response: Raw text response from the LLM
            
        Returns:
            Dict: Structured PRD content
        """
        # First try to extract JSON content
        try:
            # Find JSON content in the response
            content_start = response.find('{')
            content_end = response.rfind('}') + 1
            
            if content_start >= 0 and content_end > content_start:
                # Extract just the JSON portion
                json_content = response[content_start:content_end]
                return json.loads(json_content)
            else:
                # If no JSON found, try unstructured parsing
                logger.warning("No JSON structure found in LLM response, using unstructured parsing")
                return self._parse_unstructured_response(response)
                
        except json.JSONDecodeError as e:
            # Log the error with detailed information for debugging
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.info("Using unstructured parsing fallback")
            
            # Fallback to unstructured parsing
            return self._parse_unstructured_response(response)
    
    def _parse_unstructured_response(self, response: str) -> Dict[str, Any]:
        """
        Parse an unstructured text response into a structured PRD content dictionary.
        Used as a fallback when JSON parsing fails.
        
        Args:
            response: Raw text response from the LLM
            
        Returns:
            Dict: Structured PRD content
        """
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
    
    def _save_debug_files(self, prd_content: Dict[str, Any], raw_response: str = None):
        """
        Save debug files with current timestamp for analysis and debugging.
        
        Args:
            prd_content: The processed PRD content
            raw_response: The raw LLM response (optional)
        """
        # Create debug directory if it doesn't exist
        os.makedirs(self.config.debug_dir, exist_ok=True)
        
        # Current timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save the structured content as JSON
        json_path = self.config.debug_dir / f'prd_content_{timestamp}.json'
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(prd_content, f, indent=2)
            logger.info(f"Saved AI-generated content to {json_path}")
            
            # Count sections with content vs empty sections
            filled_sections = sum(1 for section in self.config.prd_sections if section in prd_content and prd_content[section])
            total_sections = len(self.config.prd_sections)
            logger.info(f"Sections with content: {filled_sections}/{total_sections}")
            
            # List which sections have content (at debug level)
            for section in self.config.prd_sections:
                has_content = section in prd_content and bool(prd_content[section])
                logger.debug(f"  - {section}: {'✓' if has_content else '✗'}")
                
        except IOError as e:
            logger.warning(f"Could not save AI-generated content: {e}")
        
        # Save the raw response if available
        if raw_response:
            raw_path = self.config.debug_dir / f'raw_response_{timestamp}.txt'
            try:
                with open(raw_path, 'w', encoding='utf-8') as f:
                    f.write(raw_response)
                logger.info(f"Saved raw AI response to {raw_path}")
            except IOError as e:
                logger.warning(f"Could not save raw response: {e}")
                
    def generate_architecture_diagram(self, architecture_description: str) -> str:
        """
        Generate Mermaid diagram code for architecture based on description.
        
        Args:
            architecture_description: Description of the architecture
            
        Returns:
            str: Mermaid code for the architecture diagram
        """
        # Create a prompt for the LLM to generate a diagram
        prompt = f"""
        Create a mermaid diagram for the following architecture description.
        
        <think>
        I need to analyze the architecture description and determine what type of diagram would be most appropriate.
        For a system architecture, a flowchart or component diagram is usually best.
        I should identify the main components, their relationships, and data flow.
        </think>
        
        Respond with only the mermaid code without additional explanation, comments, or code blocks:
        
        Architecture Description:
        {architecture_description}
        """
        
        try:
            mermaid_code = self.ollama_client.generate(prompt)
            
            # Extract just the mermaid code from response
            if "```mermaid" in mermaid_code:
                start = mermaid_code.find("```mermaid") + 10
                end = mermaid_code.find("```", start)
                if end > start:
                    mermaid_code = mermaid_code[start:end].strip()
            
            return mermaid_code
            
        except Exception as e:
            logger.error(f"Error generating architecture diagram: {e}")
            # Return a simple default diagram
            return "graph TD\nA[System] --> B[Components]"
    
    def generate_search_terms(self, prd_content: Dict[str, Any]) -> List[str]:
        """
        Generate optimal search terms for finding references based on PRD content.
        
        Args:
            prd_content: The structured PRD content
            
        Returns:
            List[str]: List of search terms
        """
        if "search_terms" in prd_content and isinstance(prd_content["search_terms"], list):
            return prd_content["search_terms"]
        
        # Create a prompt to extract better search terms
        prompt = f"""
        Analyze this PRD content and identify the most relevant and specific search terms for finding technical references.
        
        <think>
        I need to identify the key technical concepts, technologies mentioned, and specific domain terminology.
        General terms won't yield helpful results, so I should focus on specific technologies, standards, or methodologies.
        I should prioritize terms that would help find implementation guides, technical specifications, or industry best practices.
        </think>
        
        Output only a JSON array of strings containing 5-7 specific search terms, no explanation:
        
        {json.dumps(prd_content, indent=2)}
        """
        
        try:
            # Get search terms from the LLM
            if self.config.extract_insights:
                # Use the reasoning to get better search terms
                result = self.ollama_client.generate_with_reasoning(prompt)
                search_terms_response = result['response']
            else:
                # Standard generation
                search_terms_response = self.ollama_client.generate(prompt)
            
            # Try to parse JSON response for search terms
            search_terms = []
            start_idx = search_terms_response.find('[')
            end_idx = search_terms_response.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = search_terms_response[start_idx:end_idx]
                search_terms = json.loads(json_str)
            
            if search_terms and isinstance(search_terms, list):
                return search_terms
                
            # Fallback to default extraction
            return self._extract_default_search_terms(prd_content)
            
        except Exception as e:
            logger.warning(f"Error generating search terms: {e}")
            # Fallback to default extraction
            return self._extract_default_search_terms(prd_content)
    
    def _extract_default_search_terms(self, prd_content: Dict[str, Any]) -> List[str]:
        """Extract default search terms when advanced extraction fails."""
        search_terms = []
        
        # Get search terms if available
        if "search_terms" in prd_content and isinstance(prd_content["search_terms"], list):
            search_terms.extend(prd_content["search_terms"])
        else:
            # Extract key terms from content
            if "Executive Summary" in prd_content:
                # Get key terms from executive summary
                summary = prd_content["Executive Summary"]
                # Handle different content types
                if isinstance(summary, dict) and 'content' in summary:
                    summary = summary['content']
                elif not isinstance(summary, str):
                    summary = str(summary)
                
                # Simple extraction of key phrases
                key_terms = [term.strip() for term in summary.split('.') if len(term.strip()) > 10]
                search_terms.extend(key_terms[:3])  # Take up to 3 key phrases
            
            if "Technical Requirements" in prd_content:
                # Add technical terms
                tech_req = prd_content["Technical Requirements"]
                # Handle different content types
                if isinstance(tech_req, dict) and 'content' in tech_req:
                    tech_req = tech_req['content']
                elif not isinstance(tech_req, str):
                    if isinstance(tech_req, dict):
                        # Try to extract from technologies key if available
                        if 'technologies' in tech_req and isinstance(tech_req['technologies'], list):
                            search_terms.extend(tech_req['technologies'][:3])
                    tech_req = str(tech_req)
                
                tech_terms = [term.strip() for term in tech_req.split('\n') if len(term.strip()) > 10]
                search_terms.extend(tech_terms[:3])
        
        return search_terms