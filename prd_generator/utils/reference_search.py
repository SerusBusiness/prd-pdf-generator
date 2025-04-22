"""
Reference Search module for finding relevant external resources
"""
import os
import json
from typing import List, Dict
import requests

try:
    from duckduckgo_search import DDGS
    ddg_available = True
except ImportError:
    ddg_available = False


class ReferenceSearch:
    """Search engine for finding relevant external references."""
    
    def __init__(self):
        """Initialize the reference search engine."""
        self.search_engine = self._get_search_engine()
        
        # Google PSE configuration
        self.google_pse_cx = os.environ.get('GOOGLE_PSE_CX', '')  # Custom Search Engine ID
        self.google_pse_key = os.environ.get('GOOGLE_PSE_API_KEY', '')  # API Key
    
    def _get_search_engine(self):
        """Determine which search engine to use based on available libraries."""
        # Check for Google PSE configuration first
        if os.environ.get('GOOGLE_PSE_CX') and os.environ.get('GOOGLE_PSE_API_KEY'):
            print("Using Google Programmable Search Engine")
            return self._search_google_pse
        elif ddg_available:
            print("Using DuckDuckGo search")
            return self._search_duckduckgo
        else:
            print("Using fallback search method")
            return self._search_fallback
    
    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search for references related to the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of dictionaries with reference data {'title', 'url', 'snippet'}
        """
        return self.search_engine(query, max_results)
    
    def _search_google_pse(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Google Programmable Search Engine."""
        results = []
        
        try:
            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            
            # Parameters for the search request
            params = {
                'q': query,
                'cx': self.google_pse_cx,
                'key': self.google_pse_key,
                'num': min(max_results, 10)  # Google limits to 10 results per page
            }
            
            # Make the request
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Parse the response
            data = response.json()
            
            # Extract the search results
            if 'items' in data:
                for item in data['items']:
                    results.append({
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'snippet': item.get('snippet', '')
                    })
                    
        except Exception as e:
            print(f"Error using Google PSE: {e}")
            # Fall back to another search method
            if ddg_available:
                print("Falling back to DuckDuckGo search")
                return self._search_duckduckgo(query, max_results)
            else:
                print("Falling back to placeholder search")
                return self._search_fallback(query, max_results)
        
        return results
    
    def _search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using DuckDuckGo."""
        results = []
        
        try:
            with DDGS() as ddgs:
                search_results = ddgs.text(query, max_results=max_results)
                
                for result in search_results:
                    results.append({
                        'title': result.get('title', ''),
                        'url': result.get('href', ''),
                        'snippet': result.get('body', '')
                    })
                    
        except Exception as e:
            print(f"Error searching DuckDuckGo: {e}")
            # Fall back to the fallback method
            return self._search_fallback(query, max_results)
        
        return results
    
    def _search_fallback(self, query: str, max_results: int = 5) -> List[Dict]:
        """Fallback search method using a simple API."""
        results = []
        
        # This is a simple fallback using placeholder results
        print("Using placeholder search results")
        
        # Create some basic placeholder results
        base_terms = query.split()[:3]
        base_query = '+'.join(base_terms)
        
        results = [
            {
                'title': f"Documentation for {base_terms[0] if base_terms else 'project'} concepts",
                'url': f"https://en.wikipedia.org/wiki/{base_query}",
                'snippet': f"Learn more about {query} and related concepts."
            },
            {
                'title': f"Best practices for {base_query}",
                'url': f"https://www.example.com/best-practices/{base_query}",
                'snippet': f"Explore best practices and industry standards related to {query}."
            }
        ]
        
        return results[:max_results]