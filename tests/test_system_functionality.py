#!/usr/bin/env python3
"""
System Functionality Test for PRD Generator
Tests the entire workflow end-to-end and verifies all components are working correctly
"""
import os
import sys
import time
import unittest
import tempfile
from pathlib import Path
import logging
import json
import shutil

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prd_generator.core.config import Config
from prd_generator.utils.ollama_client import OllamaClient
from prd_generator.core.content_generator import ContentGenerator
from prd_generator.core.asset_generator import AssetGenerator
from prd_generator.formatters.content_normalizer import ContentNormalizer
from prd_generator.utils.diagram_generator import DiagramGenerator
from prd_generator.utils.image_generator import ImageGenerator
from prd_generator.utils.pdf_generator import PDFGenerator
from prd_generator.prd_processor import PRDProcessor

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SystemTest")


class PRDGeneratorSystemTest(unittest.TestCase):
    """Test case for validating the full PRD generation system."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Create a test config with safe defaults
        cls.config = Config()
        cls.config.ollama_model = os.environ.get("TEST_OLLAMA_MODEL", "llama3")
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)
        
        # Update config to use test directories
        cls.config.data_dir = cls.temp_path / "data"
        cls.config.output_dir = cls.temp_path / "output"
        cls.config.debug_dir = cls.temp_path / "debug"
        
        # Create directories
        cls.config.data_dir.mkdir(exist_ok=True)
        cls.config.output_dir.mkdir(exist_ok=True)
        cls.config.debug_dir.mkdir(exist_ok=True)
        
        # Copy test data if available
        project_root = Path(__file__).parent.parent
        if (project_root / "data" / "default_input.txt").exists():
            cls.config.data_dir.mkdir(exist_ok=True)
            shutil.copy(
                project_root / "data" / "default_input.txt",
                cls.config.data_dir / "default_input.txt"
            )
            
        if (project_root / "data" / "ai_generated.txt").exists():
            shutil.copy(
                project_root / "data" / "ai_generated.txt",
                cls.config.data_dir / "ai_generated.txt"
            )
            
        # Create a test prompt
        cls.test_prompt = """
        Create a PRD for a Smart Home Energy Management System that optimizes energy usage,
        integrates with IoT devices, and provides user-friendly dashboards. The system should
        support solar panel integration and battery storage management.
        """
        
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.temp_dir.cleanup()

    def setUp(self):
        """Set up before each test."""
        # Reset the environment for each test
        pass
        
    def test_01_ollama_client_connection(self):
        """Test that Ollama client can connect to the service."""
        try:
            client = OllamaClient(self.config)
            connected = client.verify_connection()
            
            if not connected:
                self.skipTest("Ollama service not available - skipping this test")
            
            self.assertTrue(connected, "Ollama client should connect successfully")
            
            # Try a simple generation to verify it works
            response = client.generate("Hello, how are you?", {"max_tokens": 20})
            self.assertIsInstance(response, str, "Response should be a string")
            self.assertGreater(len(response), 0, "Response should not be empty")
            
            logger.info("✅ Ollama client connection test passed")
        except Exception as e:
            logger.error(f"❌ Error testing Ollama client: {e}")
            raise
            
    def test_02_content_generation(self):
        """Test content generation from a prompt."""
        try:
            # Skip if no Ollama
            try:
                client = OllamaClient(self.config)
                if not client.verify_connection():
                    self.skipTest("Ollama service not available - skipping this test")
            except:
                self.skipTest("Ollama client initialization failed - skipping this test")
                
            # Use pre-generated content if available to speed up tests
            self.config.skip_ai_generated = False
            
            # Create content generator
            content_generator = ContentGenerator(self.config, client)
            
            # Generate content from prompt
            start_time = time.time()
            logger.info("Generating PRD content from prompt (this may take a while)...")
            prd_content = content_generator.generate_content(self.test_prompt)
            elapsed = time.time() - start_time
            logger.info(f"Content generation completed in {elapsed:.2f} seconds")
            
            # Verify the content
            self.assertIsInstance(prd_content, dict, "Content should be a dictionary")
            self.assertGreater(len(prd_content), 0, "Content should not be empty")
            
            # Verify at least some of the required sections are present
            required_sections = ["Executive Summary", "Problem Statement", "Target Users"]
            for section in required_sections:
                self.assertIn(section, prd_content, f"Content should include {section} section")
            
            # Save the content for subsequent tests
            self.prd_content = prd_content
            
            logger.info("✅ Content generation test passed")
        except Exception as e:
            logger.error(f"❌ Error testing content generation: {e}")
            raise

    def test_03_content_normalization(self):
        """Test content normalization."""
        try:
            # Skip if previous test was skipped
            if not hasattr(self, 'prd_content'):
                # Create minimal content for testing
                self.prd_content = {
                    "Executive Summary": "Test summary",
                    "Problem Statement": "Test problem",
                    "Target Users": "Test users"
                }
            
            # Create normalizer
            normalizer = ContentNormalizer()
            
            # Normalize content
            normalized = normalizer.normalize(self.prd_content)
            
            # Verify normalization
            self.assertIsInstance(normalized, dict, "Normalized content should be a dictionary")
            self.assertGreater(len(normalized), 0, "Normalized content should not be empty")
            
            # Save for subsequent tests
            self.normalized_content = normalized
            
            logger.info("✅ Content normalization test passed")
        except Exception as e:
            logger.error(f"❌ Error testing content normalization: {e}")
            raise
            
    def test_04_diagram_generation(self):
        """Test diagram generation."""
        try:
            # Create diagram generator
            diagram_generator = DiagramGenerator(self.config)
            
            # Create a simple test diagram
            mermaid_code = """
            flowchart TD
                A[Start] --> B{Decision}
                B -- Yes --> C[Process 1]
                B -- No --> D[Process 2]
                C --> E[End]
                D --> E
            """
            
            # Generate diagram
            output_path = str(self.temp_path / "test_diagram.png")
            result = diagram_generator.generate_diagram(mermaid_code, output_path)
            
            # Check if any diagram generation method succeeded
            if not result:
                logger.warning("⚠️ No diagram generation methods succeeded, but test continues")
            
            # Check if file exists
            self.assertTrue(os.path.exists(output_path), "Diagram file should exist")
            if os.path.exists(output_path):
                self.assertGreater(os.path.getsize(output_path), 0, "Diagram file should not be empty")
                
            logger.info("✅ Diagram generation test passed")
        except Exception as e:
            logger.error(f"❌ Error testing diagram generation: {e}")
            raise
            
    def test_05_image_generation(self):
        """Test image generation."""
        try:
            # Create image generator
            image_generator = ImageGenerator()
            
            # Generate a test image
            description = "A smart home control dashboard showing energy usage statistics"
            output_path = str(self.temp_path / "test_image.png")
            result = image_generator.generate_image(description, output_path)
            
            # Check result
            self.assertTrue(result, "Image generation should succeed")
            self.assertTrue(os.path.exists(output_path), "Image file should exist")
            self.assertGreater(os.path.getsize(output_path), 0, "Image file should not be empty")
            
            logger.info("✅ Image generation test passed")
        except Exception as e:
            logger.error(f"❌ Error testing image generation: {e}")
            raise
            
    def test_06_parallel_image_generation(self):
        """Test parallel image generation."""
        try:
            # Create image generator
            image_generator = ImageGenerator(max_workers=2)
            
            # Generate multiple images in parallel
            descriptions = [
                "A smart home living room with IoT devices",
                "A solar panel installation on a residential roof"
            ]
            
            # Call the parallel generation method
            results = image_generator.generate_images_parallel(
                descriptions, 
                str(self.temp_path / "images")
            )
            
            # Verify results
            self.assertIsInstance(results, list, "Results should be a list")
            self.assertGreaterEqual(len(results), 1, "At least one image should be generated")
            
            # Check if files exist
            for img_data in results:
                self.assertTrue(os.path.exists(img_data["path"]), f"Image file should exist: {img_data['path']}")
                self.assertGreater(os.path.getsize(img_data["path"]), 0, "Image file should not be empty")
            
            logger.info("✅ Parallel image generation test passed")
        except Exception as e:
            logger.error(f"❌ Error testing parallel image generation: {e}")
            raise
            
    def test_07_pdf_generation(self):
        """Test PDF generation."""
        try:
            # Create PDF generator
            pdf_generator = PDFGenerator(self.config)
            
            # Use normalized content from previous test or create minimal content
            content = getattr(self, 'normalized_content', {
                "Executive Summary": "Test summary for PDF generation",
                "Problem Statement": "Test problem statement for PDF verification",
                "Target Users": "Test users description"
            })
            
            # Generate PDF file
            output_path = str(self.temp_path / "test_output.pdf")
            
            # Add some test images and diagrams
            image_files = []
            if os.path.exists(str(self.temp_path / "test_image.png")):
                image_files.append({
                    "path": str(self.temp_path / "test_image.png"),
                    "description": "Test image",
                    "section": "Executive Summary"
                })
                
            diagram_files = []
            if os.path.exists(str(self.temp_path / "test_diagram.png")):
                diagram_files.append({
                    "path": str(self.temp_path / "test_diagram.png"),
                    "title": "Test diagram",
                    "type": "flowchart",
                    "section": "Problem Statement"
                })
                
            # Generate the PDF
            pdf_generator.generate_pdf(
                content,
                output_path,
                image_files=image_files,
                diagram_files=diagram_files
            )
            
            # Verify PDF was created
            self.assertTrue(os.path.exists(output_path), "PDF file should exist")
            self.assertGreater(os.path.getsize(output_path), 0, "PDF file should not be empty")
            
            logger.info("✅ PDF generation test passed")
        except Exception as e:
            logger.error(f"❌ Error testing PDF generation: {e}")
            raise
            
    def test_08_end_to_end_processing(self):
        """Test the complete end-to-end PRD generation process."""
        try:
            # Skip if no Ollama
            try:
                client = OllamaClient(self.config)
                if not client.verify_connection():
                    self.skipTest("Ollama service not available - skipping this test")
            except:
                self.skipTest("Ollama client initialization failed - skipping this test")
                
            # Use pre-generated content if available to speed up tests
            self.config.skip_ai_generated = False
            
            # Create PRD processor
            processor = PRDProcessor(self.config)
            
            # Process a simple PRD
            output_path = str(self.temp_path / "end_to_end_test.pdf")
            
            # Process the PRD
            logger.info("Running end-to-end PRD generation (this may take a while)...")
            start_time = time.time()
            result_path = processor.process_prd(self.test_prompt, output_path)
            elapsed = time.time() - start_time
            logger.info(f"End-to-end PRD generation completed in {elapsed:.2f} seconds")
            
            # Verify result
            self.assertEqual(result_path, output_path, "Result path should match output path")
            self.assertTrue(os.path.exists(output_path), "Output PDF should exist")
            self.assertGreater(os.path.getsize(output_path), 0, "Output PDF should not be empty")
            
            logger.info("✅ End-to-end PRD generation test passed")
        except Exception as e:
            logger.error(f"❌ Error in end-to-end PRD generation: {e}")
            raise
            
    def test_09_error_handling(self):
        """Test error handling in the PRD processor."""
        try:
            # Create a PRD processor with invalid configuration to test error handling
            bad_config = Config()
            bad_config.ollama_host = "http://nonexistent-host:11434"  # Invalid host
            bad_config.ollama_model = "nonexistent-model"  # Invalid model
            
            # Set up output directory
            bad_config.output_dir = self.temp_path / "output"
            bad_config.output_dir.mkdir(exist_ok=True)
            
            processor = PRDProcessor(bad_config)
            
            # Process a PRD with the bad configuration
            output_path = str(self.temp_path / "error_handling_test.pdf")
            
            # This should not raise an exception due to our error handling improvements
            result_path = processor.process_prd("Test prompt for error handling", output_path)
            
            # Verify that a fallback PDF was created
            self.assertTrue(os.path.exists(output_path), "Error fallback PDF should exist")
            
            logger.info("✅ Error handling test passed")
        except Exception as e:
            logger.error(f"❌ Error in error handling test: {e}")
            raise


if __name__ == '__main__':
    unittest.main()