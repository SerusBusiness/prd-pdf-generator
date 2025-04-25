"""
Tests for the Prompt Enhancer functionality
"""
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from prd_generator.core.config import Config
from prd_generator.core.enhancers.prompt_enhancer import PromptEnhancer
from prd_generator.utils.reference_search import ReferenceSearch

class TestPromptEnhancer(unittest.TestCase):
    """Test cases for the Prompt Enhancer functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.config.enhance_prompt = True
        self.config.max_references_for_enhancement = 3
        self.config.max_snippet_length = 200
        
        # Create a temporary directory for cached prompts
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config.data_dir = Path(self.temp_dir.name)
        
    def tearDown(self):
        """Clean up test fixtures"""
        self.temp_dir.cleanup()
    
    @patch('prd_generator.utils.reference_search.ReferenceSearch')
    def test_enhance_prompt_basic(self, mock_reference_search_class):
        """Test basic prompt enhancement functionality"""
        # Setup mock search results
        mock_search_instance = MagicMock()
        mock_reference_search_class.return_value = mock_search_instance
        
        mock_search_results = [
            {
                'title': 'Test Reference 1',
                'url': 'https://example.com/1',
                'snippet': 'This is a sample snippet for testing prompt enhancement'
            },
            {
                'title': 'Test Reference 2',
                'url': 'https://example.com/2',
                'snippet': 'Another sample snippet with useful information'
            }
        ]
        
        mock_search_instance.search.return_value = mock_search_results
        
        # Create enhancer and test enhance_prompt
        enhancer = PromptEnhancer(self.config)
        test_prompt = "Create a PRD for a mobile app that helps users track their fitness goals"
        
        enhanced_prompt = enhancer.enhance_prompt(test_prompt)
        
        # Assertions
        self.assertNotEqual(test_prompt, enhanced_prompt)
        self.assertIn("ADDITIONAL CONTEXT FROM SEARCH RESULTS", enhanced_prompt)
        self.assertIn("Test Reference 1", enhanced_prompt)
        self.assertIn("https://example.com/1", enhanced_prompt)
        self.assertIn("This is a sample snippet", enhanced_prompt)
        self.assertIn(test_prompt, enhanced_prompt)  # Original prompt should be preserved
        
        # Verify the search was called
        mock_search_instance.search.assert_called()
    
    def test_enhance_prompt_disabled(self):
        """Test that prompt enhancement is skipped when disabled"""
        self.config.enhance_prompt = False
        enhancer = PromptEnhancer(self.config)
        
        test_prompt = "Test prompt that should not be enhanced"
        enhanced_prompt = enhancer.enhance_prompt(test_prompt)
        
        # Should return the original prompt unchanged
        self.assertEqual(test_prompt, enhanced_prompt)
    
    @patch('prd_generator.utils.reference_search.ReferenceSearch')
    def test_extract_search_terms(self, mock_reference_search_class):
        """Test extraction of search terms from prompt"""
        enhancer = PromptEnhancer(self.config)
        
        # Test prompt with multiple sentences
        test_prompt = ("Create a mobile fitness tracking app. It should allow users to track their workouts. "
                      "The app needs to integrate with wearable devices. Social features should be included.")
        
        # Access the protected method for testing
        search_terms = enhancer._extract_search_terms(test_prompt)
        
        # Assertions
        self.assertIsInstance(search_terms, list)
        self.assertGreater(len(search_terms), 0)
        
        # First term should be from first sentence
        self.assertIn("Create a mobile fitness tracking", search_terms[0])

if __name__ == '__main__':
    unittest.main()