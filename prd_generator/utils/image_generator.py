"""
Image Generator for PRD Generator.
Handles the generation of images for PRD documents from text descriptions.
"""
import os
import re
import requests
import time
import concurrent.futures
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class ImageGenerator:
    """
    Handles image generation for PRD documents.
    Supports multiple image generation strategies with parallel processing.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the image generator.
        
        Args:
            max_workers: Maximum number of worker threads for parallel image generation
        """
        self.max_workers = max_workers
        self.pixabay_api_key = os.environ.get("PIXABAY_API_KEY", "")
        logger.info(f"Image generator initialized with {max_workers} max workers")
        
    def generate_image(self, description: str, output_path: str) -> bool:
        """
        Generate an image based on a text description.
        
        Args:
            description: Text description of the image to generate
            output_path: Path where to save the generated image
            
        Returns:
            bool: True if image generation was successful, False otherwise
        """
        # First try to fetch from Pixabay if API key is available
        if self.pixabay_api_key:
            success = self._generate_from_pixabay(description, output_path)
            if success:
                return True
                
        # Fall back to placeholder image
        return self._generate_placeholder(description, output_path)
    
    def generate_images_parallel(self, descriptions: List[str], output_dir: str, 
                                progress_callback=None) -> List[Dict[str, Any]]:
        """
        Generate multiple images in parallel based on text descriptions.
        
        Args:
            descriptions: List of image descriptions
            output_dir: Directory to save generated images
            progress_callback: Optional callback function to report progress
            
        Returns:
            List[Dict]: List of image metadata dictionaries
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []
        
        total = len(descriptions)
        completed = 0
        
        # Define the worker function for each image
        def generate_single_image(idx, desc):
            try:
                # Create a unique filename for this image
                from uuid import uuid4
                unique_id = str(uuid4())[:8]
                img_path = os.path.join(output_dir, f"image_{idx+1}_{unique_id}.png")
                
                # Generate the image
                success = self.generate_image(desc, img_path)
                
                if success:
                    try:
                        # Validate the image
                        from PIL import Image
                        with Image.open(img_path) as img:
                            width, height = img.size
                            
                            return {
                                'path': img_path,
                                'description': desc,
                                'width': width,
                                'height': height,
                                'index': idx
                            }
                    except Exception as e:
                        logger.error(f"Invalid image at {img_path}: {e}")
                        try:
                            if os.path.exists(img_path):
                                os.remove(img_path)
                        except:
                            pass
                
                return None
            except Exception as e:
                logger.error(f"Error in worker thread generating image {idx+1}: {e}")
                return None
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(generate_single_image, i, desc): i 
                for i, desc in enumerate(descriptions)
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    completed += 1
                    
                    # Report progress if callback provided
                    if progress_callback:
                        progress_callback(completed, total, f"Generated image {completed}/{total}")
                    
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Exception processing image result {idx+1}: {e}")
        
        # Sort results by original index
        results.sort(key=lambda x: x.get('index', 0))
        
        # Remove temporary index field
        for result in results:
            result.pop('index', None)
            
        return results
    
    def _generate_from_pixabay(self, description: str, output_path: str) -> bool:
        """
        Generate an image using Pixabay API.
        
        Args:
            description: Text description of the image to search for
            output_path: Path where to save the generated image
            
        Returns:
            bool: True if image generation was successful, False otherwise
        """
        try:
            # Extract keywords from description
            keywords = self._extract_keywords(description)
            search_query = '+'.join(keywords[:3])  # Use top 3 keywords
            
            # Call Pixabay API
            api_url = f"https://pixabay.com/api/"
            params = {
                "key": self.pixabay_api_key,
                "q": search_query,
                "image_type": "photo",
                "orientation": "horizontal",
                "per_page": 3,
                "safesearch": "true"
            }
            
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            hits = data.get('hits', [])
            
            if hits:
                # Get the first image URL
                image_url = hits[0].get('largeImageURL')
                if image_url:
                    # Download the image
                    img_response = requests.get(image_url)
                    img_response.raise_for_status()
                    
                    # Save the image
                    with open(output_path, 'wb') as f:
                        f.write(img_response.content)
                    
                    logger.info(f"Successfully generated image from Pixabay: {os.path.basename(output_path)}")
                    return True
            
            logger.warning(f"No suitable images found on Pixabay for: {description[:30]}...")
            return False
            
        except Exception as e:
            logger.error(f"Error generating image from Pixabay: {e}")
            return False
    
    def _generate_placeholder(self, description: str, output_path: str) -> bool:
        """
        Generate a placeholder image with the description text.
        
        Args:
            description: Text description of the image
            output_path: Path where to save the generated image
            
        Returns:
            bool: True if image generation was successful, False otherwise
        """
        try:
            # Use PIL to create a simple placeholder image
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a blank image
            width, height = 800, 600
            image = Image.new('RGB', (width, height), color=(240, 240, 240))
            
            # Add text
            draw = ImageDraw.Draw(image)
            
            # Try to use a nice font if available, otherwise use default
            try:
                font_size = 24
                font_path = None
                
                # Try common system fonts
                common_fonts = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                    '/System/Library/Fonts/Helvetica.ttc',  # macOS
                    'C:\\Windows\\Fonts\\arial.ttf',  # Windows
                    'arial'  # Default name
                ]
                
                for font_candidate in common_fonts:
                    try:
                        font = ImageFont.truetype(font_candidate, font_size)
                        font_path = font_candidate
                        break
                    except:
                        continue
                        
                # If no specific font worked, use default
                if not font_path:
                    font = ImageFont.load_default()
            except:
                # Fall back to default font
                font = ImageFont.load_default()
            
            # Draw a border
            draw.rectangle([0, 0, width - 1, height - 1], outline=(200, 200, 200), width=2)
            
            # Draw heading
            heading = "PRD Image Placeholder"
            draw.text((width // 2, 50), heading, fill=(50, 50, 50), font=font, anchor="mm")
            
            # Draw description with word wrapping
            y_position = 100
            words = description.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                # Check if adding the word would make the line too long
                text_width = draw.textlength(test_line, font=font)
                
                if text_width <= width - 80:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            # Add the last line
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw each line
            for line in lines[:10]:  # Limit to prevent overflow
                draw.text((width // 2, y_position), line, fill=(50, 50, 50), font=font, anchor="mm")
                y_position += 30
            
            # Add ellipsis if description was truncated
            if len(lines) > 10:
                draw.text((width // 2, y_position), "...", fill=(50, 50, 50), font=font, anchor="mm")
            
            # Save the image
            image.save(output_path)
            logger.info(f"Generated placeholder image: {os.path.basename(output_path)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating placeholder image: {e}")
            return False
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract relevant keywords from a description.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List[str]: List of keywords
        """
        # Simple keyword extraction
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'with', 'by', 'for', 
                     'of', 'to', 'and', 'or', 'that', 'this', 'is', 'are', 'was', 
                     'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 
                     'does', 'did', 'but', 'if', 'then', 'else', 'when', 'up', 
                     'down', 'out', 'about', 'into', 'over', 'under'}
        
        # Clean text and split into words
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = [word for word in text.split() if word not in stop_words and len(word) > 2]
        
        # Return unique words
        return list(dict.fromkeys(words))