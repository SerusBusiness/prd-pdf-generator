"""
Image Generator module for creating images for PRD documents
"""
import os
import requests
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap
import random
import json


class ImageGenerator:
    """Generator for creating images based on text descriptions."""
    
    def __init__(self):
        """Initialize the image generator."""
        # Set up API keys from environment if present
        self.api_key = os.environ.get("IMAGE_API_KEY", "")
        # Pixabay API key - get a free one from https://pixabay.com/api/docs/
        self.pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
        # Hugging Face token
        self.hf_token = os.environ.get("HUGGINGFACE_TOKEN", "")
    
    def generate_image(self, description: str, output_path: str) -> bool:
        """
        Generate an image based on a text description.
        
        Uses AI-based image generation with the given description as the prompt.
        Falls back to alternative methods if AI generation fails.
        
        Args:
            description: Text description of the image to generate
            output_path: Path to save the generated image
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Try different methods to generate images, starting with Hugging Face
        methods = [
            self._generate_using_huggingface,  # First attempt with Hugging Face
            self._generate_using_dall_e_compatible_api,
            self._generate_using_pixabay_api,  
            self._use_placeholder_image,
            self._create_text_placeholder_image  # Final fallback
        ]
        
        for method in methods:
            try:
                success = method(description, output_path)
                if success:
                    print(f"Successfully generated image using {method.__name__}")
                    return True
            except Exception as e:
                print(f"Error generating image with method {method.__name__}: {e}")
        
        return False
    
    def _generate_using_huggingface(self, description: str, output_path: str) -> bool:
        """Generate an image using Hugging Face's FLUX.1-dev model."""
        if not self.hf_token:
            print("No Hugging Face token found. Skipping Hugging Face image generation.")
            return False
        
        try:
            print(f"Generating image with Hugging Face using prompt: {description}")
            
            # Import the InferenceClient for Hugging Face
            try:
                from huggingface_hub import InferenceClient
            except ImportError:
                print("huggingface_hub package not installed. Please install it with: pip install huggingface_hub")
                return False
                
            # Create the client
            client = InferenceClient(
                provider="fal-ai",
                api_key=self.hf_token,
            )
            
            # Clean up the prompt if necessary
            if description.lower().startswith("generate an image of"):
                description = description[len("generate an image of"):].strip()
            elif description.lower().startswith("generate an image"):
                description = description[len("generate an image"):].strip()
            elif description.lower().startswith("generate"):
                description = description[len("generate"):].strip()
                
            # Generate the image using FLUX.1-dev model
            image = client.text_to_image(
                description,
                model="black-forest-labs/FLUX.1-dev",
            )
            
            # Save the image
            image.save(output_path)
            
            # Verify the image exists and is valid
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Successfully generated image with Hugging Face for: {description}")
                return True
                
            return False
            
        except Exception as e:
            print(f"Error using Hugging Face for image generation: {e}")
            return False
    
    def _generate_using_dall_e_compatible_api(self, description: str, output_path: str) -> bool:
        """Generate an image using a DALL-E compatible API if API key is available."""
        if not self.api_key:
            return False
        
        try:
            # This is a placeholder for an actual API integration
            # In a production environment, this would use something like OpenAI's DALL-E API
            # or a similar image generation service
            
            # Example of how OpenAI DALL-E implementation might look:
            # import openai
            # openai.api_key = self.api_key
            # response = openai.Image.create(
            #     prompt=description,
            #     size="512x512"
            # )
            # image_url = response['data'][0]['url']
            # response = requests.get(image_url)
            # with open(output_path, 'wb') as f:
            #     f.write(response.content)
            
            # For now, this method won't succeed since we don't have actual integration
            return False
        except Exception:
            return False
    
    def _generate_using_pixabay_api(self, description: str, output_path: str) -> bool:
        """Generate an image by searching Pixabay based on the description."""
        if not self.pixabay_key:
            print("No Pixabay API key found. Setting a temporary demo key.")
            # For testing, we'll use a temporary demo key
            self.pixabay_key = "demo_key_for_testing"
        
        try:
            # Extract key search terms from description
            search_terms = ' '.join(description.split()[:3])
            
            # Create API request URL
            api_url = "https://pixabay.com/api/"
            params = {
                'key': self.pixabay_key,
                'q': search_terms,
                'image_type': 'photo',
                'orientation': 'horizontal',
                'safesearch': 'true',
                'per_page': 5  # Get just a few results
            }
            
            # Make API request
            response = requests.get(api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have images
                if data.get('totalHits', 0) > 0 and 'hits' in data and len(data['hits']) > 0:
                    # Get first image URL
                    image_url = data['hits'][0].get('webformatURL')
                    
                    if image_url:
                        # Download the image
                        img_response = requests.get(image_url, timeout=10)
                        
                        if img_response.status_code == 200:
                            # Process the image to ensure it's valid
                            try:
                                import io
                                img = Image.open(io.BytesIO(img_response.content))
                                
                                # Resize if needed to ensure consistent dimensions
                                width, height = 800, 600
                                img = img.resize((width, height), Image.LANCZOS)
                                
                                # Convert to RGB if necessary (in case of RGBA or other formats)
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                
                                # Add a small attribution at the bottom
                                draw = ImageDraw.Draw(img)
                                try:
                                    font = ImageFont.truetype("arial.ttf", 12)
                                except:
                                    font = ImageFont.load_default()
                                
                                # Add semi-transparent background for text
                                draw.rectangle([5, height-20, 150, height-5], fill=(0, 0, 0, 128))
                                
                                # Add attribution text
                                attribution = "Source: Pixabay"
                                draw.text((10, height-18), attribution, fill=(255, 255, 255), font=font)
                                
                                # Save the image
                                img.save(output_path, format='PNG')
                                
                                print(f"Successfully downloaded image from Pixabay for '{search_terms}'")
                                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
                            except Exception as img_err:
                                print(f"Error processing Pixabay image: {img_err}")
                                return False
            
            # If we reach here, the API request failed or returned no usable images
            print(f"No usable images found on Pixabay for '{search_terms}'")
            return False
        except Exception as e:
            print(f"Error searching Pixabay: {e}")
            return False
    
    def _use_placeholder_image(self, description: str, output_path: str) -> bool:
        """Use a placeholder image from the web based on the description."""
        try:
            # Use Unsplash source for placeholder images
            # Create a simple URL-friendly version of the description
            keywords = '+'.join(description.split()[:3])
            
            # Get a random image related to the keywords
            url = f"https://source.unsplash.com/800x600/?{keywords}"
            response = requests.get(url, timeout=30)
            
            # First validate the image by opening it with PIL
            try:
                import io
                img = Image.open(io.BytesIO(response.content))
                # Convert to RGB if necessary (in case of RGBA or other formats)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Save the image with explicit format
                img.save(output_path, format='PNG')
            except Exception as img_err:
                print(f"Could not verify downloaded image: {img_err}")
                # If we can't validate the image, fall back to text placeholder
                return False
                
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Error getting placeholder image: {e}")
            return False
            
    def _create_text_placeholder_image(self, description: str, output_path: str) -> bool:
        """Create a simple placeholder image with the description text."""
        try:
            # Create a blank image with a colored background
            width, height = 800, 600
            colors = [
                (240, 240, 250),  # Light blue-gray
                (245, 240, 225),  # Light beige
                (230, 245, 230),  # Light green
                (250, 235, 235),  # Light pink
                (235, 235, 250)   # Light purple
            ]
            background_color = random.choice(colors)
            text_color = (60, 60, 60)  # Dark gray
            border_color = (180, 180, 180)  # Medium gray
            
            # Create image and drawing context
            img = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(img)
            
            # Draw border
            border_width = 5
            draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=border_width)
            
            # Try to load a font, fall back to default if not available
            try:
                font_path = None
                # Check for common font locations
                font_locations = [
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Helvetica.ttc"
                ]
                for path in font_locations:
                    if os.path.exists(path):
                        font_path = path
                        break
                
                if (font_path):
                    title_font = ImageFont.truetype(font_path, 30)
                    desc_font = ImageFont.truetype(font_path, 20)
                else:
                    title_font = ImageFont.load_default()
                    desc_font = ImageFont.load_default()
            except Exception:
                title_font = ImageFont.load_default()
                desc_font = ImageFont.load_default()
            
            # Draw title
            title = "Image Placeholder"
            draw.text((width//2, 50), title, fill=text_color, font=title_font, anchor="mm")
            
            # Draw description with text wrapping
            wrapped_text = textwrap.fill(description, width=40)
            y_position = height // 2 - 20 * (wrapped_text.count('\n') // 2)
            
            # Draw each line of wrapped text
            for line in wrapped_text.split('\n'):
                draw.text((width//2, y_position), line, fill=text_color, font=desc_font, anchor="mm")
                y_position += 30
            
            # Save the image - ensure we use a format that ReportLab supports well
            # Save as PNG with explicit format
            img.save(output_path, format='PNG')
            
            # Validate the image was saved correctly
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # Double check we can read it with PIL
                with Image.open(output_path) as check_img:
                    # Force loading the image to verify it's valid
                    check_img.load()
                return True
            return False
        except Exception as e:
            print(f"Error creating text placeholder image: {e}")
            return False