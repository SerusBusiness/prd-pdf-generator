"""
Prompt Enhancer - Enhances input prompts with relevant information from search results
to provide more context to the LLM for improved PRD generation.
"""
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from prd_generator.core.logging_setup import get_logger
from prd_generator.utils.reference_search import ReferenceSearch

# Initialize logger
logger = get_logger(__name__)

class PromptEnhancer:
    """
    Enhances input prompts with external reference information
    to provide better context to the LLM for PRD generation.
    """
    
    def __init__(self, config):
        """
        Initialize the prompt enhancer with configuration.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.reference_search = ReferenceSearch() if config.enable_search else None
        self.max_references = config.max_references_for_enhancement
        self.max_snippet_length = config.max_snippet_length
        self.cache_dir = Path(config.data_dir) / "search_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
    def enhance_prompt(self, prompt_text: str) -> str:
        """
        Enhance the input prompt with relevant information from search results.
        
        Args:
            prompt_text: The original input prompt text
            
        Returns:
            str: Enhanced prompt text with additional context from search results
        """
        if not self.config.enhance_prompt or not self.reference_search:
            logger.info("Prompt enhancement is disabled")
            return prompt_text
            
        logger.info("Enhancing prompt with search results")
        
        # Extract key search terms from the prompt
        search_terms = self._extract_search_terms(prompt_text)
        
        if not search_terms:
            logger.warning("No suitable search terms found for prompt enhancement")
            return prompt_text
            
        logger.info(f"Extracted {len(search_terms)} search terms from prompt")
        
        # Get search results for the extracted terms
        references = self._get_search_results(search_terms)
        
        if not references:
            logger.warning("No relevant references found for prompt enhancement")
            return prompt_text
            
        # Generate enhanced prompt with references
        enhanced_prompt = self._build_enhanced_prompt(prompt_text, references)
        
        logger.info(f"Prompt enhanced: original {len(prompt_text)} characters, " + 
                   f"enhanced {len(enhanced_prompt)} characters")
        
        # Cache the enhanced prompt for debugging if enabled
        if self.config.cache_enhanced_prompts:
            self._cache_enhanced_prompt(prompt_text, enhanced_prompt)
            
        return enhanced_prompt
    
    def _extract_search_terms(self, prompt_text: str) -> List[str]:
        """
        Extract key search terms from the prompt text.
        
        Args:
            prompt_text: The input prompt text
            
        Returns:
            List[str]: List of extracted search terms
        """
        # Simple extraction strategy: split by sentences and extract key phrases
        terms = []
        
        # Split the prompt into sentences
        sentences = prompt_text.split('.')
        
        # Extract terms from sentences with sufficient length
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 15:
                # Get the first N words as a term (adjust based on your needs)
                words = sentence.split()
                if len(words) >= 3:
                    term = ' '.join(words[:5])  # Take first 5 words
                    terms.append(term)
                    
        # Limit the number of terms to avoid excessive searches
        max_terms = min(5, len(terms))
        return terms[:max_terms]
    
    def _get_search_results(self, search_terms: List[str]) -> List[Dict[str, Any]]:
        """
        Get search results for the given terms.
        
        Args:
            search_terms: List of search terms
            
        Returns:
            List[Dict]: List of reference dictionaries with search results
        """
        all_references = []
        
        for term in search_terms:
            try:
                results = self.reference_search.search(term, max_results=2)
                if results:
                    all_references.extend(results)
                    logger.info(f"Found {len(results)} references for term: {term[:30]}...")
                else:
                    logger.info(f"No references found for term: {term[:30]}...")
            except Exception as e:
                logger.error(f"Error searching for term '{term[:30]}...': {e}")
                
        # Remove duplicates by URL
        unique_references = []
        seen_urls = set()
        
        for ref in all_references:
            url = ref.get('url', '')
            if url and url in seen_urls:
                continue
                
            if url:
                seen_urls.add(url)
            unique_references.append(ref)
        
        # Limit the number of references used for enhancement
        return unique_references[:self.max_references]
    
    def _build_enhanced_prompt(self, original_prompt: str, references: List[Dict[str, Any]]) -> str:
        """
        Build an enhanced prompt by incorporating reference information.
        
        Args:
            original_prompt: The original input prompt
            references: List of reference dictionaries with search results
            
        Returns:
            str: Enhanced prompt with reference information
        """
        # Create a section of the prompt with references information
        reference_section = "\n\n--- ADDITIONAL CONTEXT FROM SEARCH RESULTS ---\n\n"
        
        for i, ref in enumerate(references, 1):
            title = ref.get('title', 'Untitled Reference')
            snippet = ref.get('snippet', '')
            url = ref.get('url', '')
            
            # Limit snippet length
            if len(snippet) > self.max_snippet_length:
                snippet = snippet[:self.max_snippet_length] + "..."
                
            # Add reference information
            reference_section += f"Reference {i}: {title}\n"
            reference_section += f"Source: {url}\n"
            reference_section += f"Content: {snippet}\n\n"
            
        reference_section += "--- END OF ADDITIONAL CONTEXT ---\n\n"
        reference_section += "Please use the above information to enhance your understanding of the topic, " \
                            "but maintain focus on the core requirements specified in the original prompt below:\n\n"
                            
        # Combine original prompt with reference section
        enhanced_prompt = reference_section + original_prompt
        
        return enhanced_prompt
    
    def _cache_enhanced_prompt(self, original_prompt: str, enhanced_prompt: str) -> None:
        """
        Cache the enhanced prompt for debugging purposes.
        
        Args:
            original_prompt: The original input prompt
            enhanced_prompt: The enhanced prompt with references
        """
        try:
            import hashlib
            import time
            
            # Create a unique filename based on timestamp and content hash
            timestamp = int(time.time())
            prompt_hash = hashlib.md5(original_prompt.encode('utf-8')).hexdigest()[:8]
            filename = f"enhanced_prompt_{timestamp}_{prompt_hash}.txt"
            
            # Write to cache file
            cache_file = self.cache_dir / filename
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write("--- ORIGINAL PROMPT ---\n\n")
                f.write(original_prompt)
                f.write("\n\n--- ENHANCED PROMPT ---\n\n")
                f.write(enhanced_prompt)
                
            logger.debug(f"Cached enhanced prompt to {cache_file}")
            
        except Exception as e:
            logger.error(f"Error caching enhanced prompt: {e}")