"""
Reference Search Manager for PRD Generator.
Handles searching for references related to PRD content.
"""
import os
from typing import Dict, Any, List, Optional

from prd_generator.core.logging_setup import get_logger
from prd_generator.utils.reference_search import ReferenceSearch

# Initialize logger
logger = get_logger(__name__)

class ReferenceSearchManager:
    """
    Manages the search for references related to PRD content.
    This class encapsulates all logic for finding and processing references.
    """
    
    def __init__(self, config):
        """
        Initialize the reference search manager with configuration.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.reference_search = ReferenceSearch() if config.enable_search else None
    
    def search_references(self, prd_content: Dict[str, Any], search_terms: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search for references related to the PRD content.
        
        Args:
            prd_content: The structured PRD content
            search_terms: Optional list of specific search terms to use
            
        Returns:
            List[Dict]: List of reference metadata dictionaries
        """
        if not self.config.enable_search or not self.reference_search:
            logger.info("Reference search is disabled")
            return []
        
        # Get search terms if not provided
        if not search_terms:
            search_terms = self._get_search_terms(prd_content)
            
        if not search_terms:
            logger.warning("No search terms available for reference search")
            return []
            
        logger.info(f"Searching for references using {len(search_terms)} search terms")
        
        # Perform the search
        references = []
        for i, term in enumerate(search_terms, 1):
            logger.info(f"Searching for term {i}/{len(search_terms)}: {term}")
            try:
                results = self.reference_search.search(term, max_results=2)
                if results:
                    references.extend(results)
                    logger.info(f"Found {len(results)} references for term: {term}")
                else:
                    logger.info(f"No references found for term: {term}")
            except Exception as e:
                logger.error(f"Error searching for term '{term}': {e}")
        
        # Remove duplicates by URL if present
        unique_references = []
        seen_urls = set()
        
        for ref in references:
            url = ref.get('url', '')
            if url and url in seen_urls:
                continue
                
            if url:
                seen_urls.add(url)
            unique_references.append(ref)
        
        logger.info(f"Found {len(unique_references)} unique references")
        return unique_references
    
    def _get_search_terms(self, prd_content: Dict[str, Any]) -> List[str]:
        """
        Extract search terms from PRD content.
        
        Args:
            prd_content: The structured PRD content
            
        Returns:
            List[str]: List of search terms
        """
        # Get search terms if available in the content
        if "search_terms" in prd_content and isinstance(prd_content["search_terms"], list):
            return prd_content["search_terms"]
            
        # Extract default search terms
        search_terms = []
        
        # Extract from Executive Summary
        if "Executive Summary" in prd_content:
            summary = prd_content["Executive Summary"]
            # Handle different content types
            if isinstance(summary, dict) and 'content' in summary:
                summary = summary['content']
            elif not isinstance(summary, str):
                summary = str(summary)
            
            # Simple extraction of key phrases
            key_terms = [term.strip() for term in summary.split('.') if len(term.strip()) > 10]
            search_terms.extend(key_terms[:3])  # Take up to 3 key phrases
        
        # Extract from Technical Requirements
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
            
        # Return unique terms
        return list(set(search_terms))