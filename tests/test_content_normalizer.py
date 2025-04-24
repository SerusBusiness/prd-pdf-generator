"""
Unit tests for ContentNormalizer
"""
import unittest
from prd_generator.formatters.content_normalizer import ContentNormalizer

class TestContentNormalizer(unittest.TestCase):
    """Test cases for the ContentNormalizer class"""
    
    def setUp(self):
        """Set up test environment before each test"""
        self.normalizer = ContentNormalizer()
        
    def test_normalize_empty_content(self):
        """Test normalization of empty content"""
        # Execute
        result = self.normalizer.normalize({})
        
        # Assert
        self.assertEqual(result, {})
        
    def test_normalize_string_content(self):
        """Test normalization of string content"""
        # Setup
        content = {
            "Executive Summary": "This is a test summary",
            "Problem Statement": "This is a test problem"
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertEqual(result["Executive Summary"], "This is a test summary")
        self.assertEqual(result["Problem Statement"], "This is a test problem")
        
    def test_normalize_nested_dict_content(self):
        """Test normalization of nested dictionary content"""
        # Setup
        content = {
            "Executive Summary": {"content": "This is a test summary"},
            "Technical Requirements": {"technologies": ["Tech1", "Tech2"], "standards": ["Standard1"]}
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertEqual(result["Executive Summary"], "This is a test summary")
        self.assertIn("Tech1", result["Technical Requirements"])
        self.assertIn("Tech2", result["Technical Requirements"])
        
    def test_normalize_list_content(self):
        """Test normalization of list content"""
        # Setup
        content = {
            "Requirements & Features": [
                {"feature": "Feature 1", "description": "Description 1"},
                {"feature": "Feature 2", "description": "Description 2"}
            ]
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertIsInstance(result["Requirements & Features"], str)
        self.assertIn("Feature 1", result["Requirements & Features"])
        self.assertIn("Feature 2", result["Requirements & Features"])
        
    def test_normalize_user_stories(self):
        """Test normalization of user stories content"""
        # Setup
        content = {
            "User Stories": [
                {"user_type": "Admin", "action": "manage users", "benefit": "maintain system security"},
                {"user_type": "Customer", "action": "search products", "benefit": "find what they need quickly"}
            ]
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertIsInstance(result["User Stories"], str)
        self.assertIn("Admin", result["User Stories"])
        self.assertIn("Customer", result["User Stories"])
        self.assertIn("manage users", result["User Stories"])
        
    def test_normalize_success_metrics(self):
        """Test normalization of success metrics content"""
        # Setup
        content = {
            "Success Metrics": {
                "key_performance_indicators": [
                    {"metric": "User Growth", "baseline": "1000 users", "target": "10000 users"},
                    {"metric": "Conversion Rate", "baseline": "2%", "target": "5%"}
                ]
            }
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertIsInstance(result["Success Metrics"], str)
        self.assertIn("User Growth", result["Success Metrics"])
        self.assertIn("Conversion Rate", result["Success Metrics"])
        self.assertIn("10000 users", result["Success Metrics"])
        
    def test_preserve_special_keys(self):
        """Test that special keys are preserved during normalization"""
        # Setup
        content = {
            "Executive Summary": "Test summary",
            "image_suggestions": ["Image 1", "Image 2"],
            "diagrams": [{"title": "Diagram 1", "mermaid_code": "graph TD;"}]
        }
        
        # Execute
        result = self.normalizer.normalize(content)
        
        # Assert
        self.assertEqual(result["Executive Summary"], "Test summary")
        self.assertEqual(result["image_suggestions"], ["Image 1", "Image 2"])
        self.assertEqual(result["diagrams"][0]["title"], "Diagram 1")
        
if __name__ == '__main__':
    unittest.main()