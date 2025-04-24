"""
Unit tests for ContentGenerator
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from prd_generator.core.config import Config
from prd_generator.core.content_generator import ContentGenerator

class TestContentGenerator(unittest.TestCase):
    """Test cases for the ContentGenerator class"""
    
    def setUp(self):
        """Set up test environment before each test"""
        self.config = Config()
        # Create a mock Ollama client
        self.mock_ollama_client = MagicMock()
        # Initialize the content generator with the mock client
        self.content_generator = ContentGenerator(self.config, self.mock_ollama_client)
        
        # Create a temporary directory for testing
        self.test_dir = Path(os.path.dirname(__file__)) / "test_data"
        self.test_dir.mkdir(exist_ok=True)
        self.config.debug_dir = self.test_dir
        self.config.data_dir = self.test_dir
        
    def tearDown(self):
        """Clean up after each test"""
        # Remove test files
        for file in self.test_dir.glob("*"):
            try:
                file.unlink()
            except Exception:
                pass
        
        # Remove test directory
        try:
            self.test_dir.rmdir()
        except Exception:
            pass
    
    @patch('prd_generator.core.content_generator.json.loads')
    def test_generate_content_json_parsing(self, mock_json_loads):
        """Test the content generation with JSON parsing"""
        # Setup mock returns
        mock_response = '{"Executive Summary": "Test summary"}'
        mock_json_loads.return_value = {"Executive Summary": "Test summary"}
        self.mock_ollama_client.generate.return_value = mock_response
        
        # Execute
        result = self.content_generator.generate_content("Test prompt")
        
        # Assert
        self.assertEqual(result["Executive Summary"], "Test summary")
        self.mock_ollama_client.generate.assert_called_once()
    
    def test_generate_content_with_pregenerated(self):
        """Test content generation using pre-generated content"""
        # Setup
        self.config.skip_ai_generated = False
        test_content = {"Executive Summary": "Pre-generated summary"}
        
        # Create pre-generated content file
        with open(self.test_dir / "ai_generated.txt", "w", encoding="utf-8") as f:
            json.dump(test_content, f)
        
        # Execute
        result = self.content_generator.generate_content("Ignored prompt")
        
        # Assert
        self.assertEqual(result["Executive Summary"], "Pre-generated summary")
        self.mock_ollama_client.generate.assert_not_called()
        
    def test_generate_content_unstructured_fallback(self):
        """Test content generation with unstructured response fallback"""
        # Setup mock to return an unstructured response
        unstructured_response = """
        Executive Summary
        This is a test summary
        
        Problem Statement
        This is a test problem
        """
        self.mock_ollama_client.generate.return_value = unstructured_response
        
        # Execute with patched json.loads to force an exception
        with patch('json.loads', side_effect=json.JSONDecodeError("Test error", "", 0)):
            result = self.content_generator.generate_content("Test prompt")
        
        # Assert
        self.assertIn("Executive Summary", result)
        self.assertIn("Problem Statement", result)
        
    def test_generate_search_terms(self):
        """Test the generation of search terms"""
        # Setup
        prd_content = {
            "search_terms": ["term1", "term2", "term3"]
        }
        
        # Execute
        result = self.content_generator.generate_search_terms(prd_content)
        
        # Assert
        self.assertEqual(result, ["term1", "term2", "term3"])
        
    def test_generate_search_terms_fallback(self):
        """Test fallback search terms generation when no search_terms in content"""
        # Setup
        prd_content = {
            "Executive Summary": "This is a test summary with some keywords",
            "Technical Requirements": "This includes test technologies"
        }
        
        # Mock the LLM to fail
        self.mock_ollama_client.generate.side_effect = Exception("Test exception")
        
        # Execute
        result = self.content_generator.generate_search_terms(prd_content)
        
        # Assert
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        
    def test_generate_architecture_diagram(self):
        """Test architecture diagram generation"""
        # Setup
        arch_description = "Test architecture with components"
        expected_mermaid = "graph TD\nA[System] --> B[Components]"
        self.mock_ollama_client.generate.return_value = f"```mermaid\n{expected_mermaid}\n```"
        
        # Execute
        result = self.content_generator.generate_architecture_diagram(arch_description)
        
        # Assert
        self.assertEqual(result, expected_mermaid)
        self.mock_ollama_client.generate.assert_called_once()
        
    def test_generate_architecture_diagram_error_handling(self):
        """Test architecture diagram generation with error handling"""
        # Setup
        arch_description = "Test architecture with components"
        self.mock_ollama_client.generate.side_effect = Exception("Test exception")
        
        # Execute
        result = self.content_generator.generate_architecture_diagram(arch_description)
        
        # Assert - should return a simple default diagram
        self.assertIn("graph TD", result)
        self.assertIn("System", result)
        
if __name__ == '__main__':
    unittest.main()