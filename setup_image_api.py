#!/usr/bin/env python
"""
Setup script to configure the Pixabay API for the PRD Generator.
This helps users set up real image generation in the PRD documents.
"""
import os
import sys
import json
import webbrowser
from pathlib import Path

def main():
    """Run the Pixabay API setup process."""
    print("PRD Generator - Image API Setup")
    print("===============================")
    print("This script will help you set up real image generation for your PRDs.")
    print("\nTo use the Pixabay API, you need a free API key.")
    print("1. You can get one by signing up at https://pixabay.com/api/docs/")
    print("2. After signing up, go to your account dashboard to get your API key")
    
    # Check if key already exists
    env_file = Path(".env")
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    
    if env_file.exists():
        # Read existing .env file
        with open(env_file, "r") as f:
            lines = f.readlines()
        
        # Check if PIXABAY_API_KEY is already defined
        for line in lines:
            if line.startswith("PIXABAY_API_KEY="):
                pixabay_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    
    if pixabay_key:
        print(f"\nA Pixabay API key is already configured: {pixabay_key[:5]}...{pixabay_key[-3:]}")
        change = input("Do you want to change it? (y/n): ").lower()
        if change != 'y':
            print("\nKeeping existing API key. Setup complete!")
            return
    
    # Open the Pixabay sign up page in browser
    open_browser = input("\nDo you want to open the Pixabay API sign-up page in your browser? (y/n): ").lower()
    if open_browser == 'y':
        webbrowser.open("https://pixabay.com/api/docs/")
    
    # Get API key from user
    api_key = input("\nEnter your Pixabay API key (or press Enter to skip): ").strip()
    if not api_key:
        print("\nSkipping API key setup. You can add it later by:")
        print("1. Setting the PIXABAY_API_KEY environment variable")
        print("2. Running this setup script again")
        print("3. Editing the .env file directly")
        return
    
    # Save to .env file
    if env_file.exists():
        # Update existing file
        with open(env_file, "r") as f:
            lines = f.readlines()
        
        key_found = False
        with open(env_file, "w") as f:
            for line in lines:
                if line.startswith("PIXABAY_API_KEY="):
                    f.write(f'PIXABAY_API_KEY="{api_key}"\n')
                    key_found = True
                else:
                    f.write(line)
            
            if not key_found:
                f.write(f'\nPIXABAY_API_KEY="{api_key}"\n')
    else:
        # Create new file
        with open(env_file, "w") as f:
            f.write(f'PIXABAY_API_KEY="{api_key}"\n')
    
    # Also set it in the current environment
    os.environ["PIXABAY_API_KEY"] = api_key
    
    print("\nAPI key saved successfully!")
    print("The PRD Generator will now use real images from Pixabay in your documents.")
    
    # Ask if they want to test it
    test_now = input("\nDo you want to test image generation now? (y/n): ").lower()
    if test_now == 'y':
        try:
            from prd_generator.utils.image_generator import ImageGenerator
            
            print("\nTesting image generation...")
            generator = ImageGenerator()
            test_image = "test_image.png"
            desc = "A beautiful mountain landscape with a lake"
            
            if generator.generate_image(desc, test_image):
                print(f"Test successful! Image saved to {test_image}")
                print("You can delete this test image if you want.")
            else:
                print("Test failed. Please check your API key and try again.")
        except Exception as e:
            print(f"Error testing image generation: {e}")
    
    print("\nSetup complete!")

if __name__ == "__main__":
    main()