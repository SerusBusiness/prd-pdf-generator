"""
Ollama client for interacting with local LLM models
"""
import json
import requests
import time
import os
from prd_generator.config import Config


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, config: Config):
        """Initialize the Ollama client."""
        self.config = config
        self.api_base = config.ollama_host.rstrip('/')
        self.model = config.ollama_model
        # Define potential API endpoints to try
        self.api_endpoints = [
            "/api/generate",
            "/v1/chat/completions",
            "/api/v1/generate",
        ]
        # Print current configuration
        print(f"Ollama API base: {self.api_base}")
        print(f"Ollama model: {self.model}")
    
    def generate(self, prompt: str, max_retries: int = 3) -> str:
        """
        Generate a response from the Ollama model.
        
        Args:
            prompt: The prompt to send to the model
            max_retries: Maximum number of retries in case of failure
            
        Returns:
            str: Text response from the model
        """
        # Try all API endpoints until one works
        for endpoint in self.api_endpoints:
            url = f"{self.api_base}{endpoint}"
            print(f"Trying endpoint: {url}")
            
            # Adjust payload format based on endpoint
            if "chat/completions" in endpoint:
                # OpenAI-style API format
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
            else:
                # Standard Ollama format
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "temperature": 0.3,
                }
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, json=payload, timeout=120)
                    response.raise_for_status()
                    
                    # Parse response based on API format
                    if "chat/completions" in endpoint:
                        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    else:
                        return response.json().get("response", "")
                        
                except requests.exceptions.RequestException as e:
                    print(f"Error connecting to Ollama endpoint {endpoint} (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        # If we've exhausted retries for this endpoint, try the next one
                        break
                    time.sleep(2)  # Wait before retrying
        
        # If we reach here, none of the endpoints worked
        return f"Error: Could not connect to Ollama at {self.api_base} after trying multiple endpoints. Please ensure Ollama is running with the model {self.model} loaded."
    
    def check_model_availability(self) -> bool:
        """
        Check if the configured model is available in Ollama.
        
        Returns:
            bool: True if model is available, False otherwise
        """
        endpoints = ["/api/tags", "/v1/models"]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_base}{endpoint}"
                print(f"Checking models at: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                if endpoint == "/api/tags":
                    models = response.json().get("models", [])
                    available_models = [model.get("name") for model in models]
                else:  # /v1/models endpoint
                    data = response.json()
                    available_models = [model.get("id") for model in data.get("data", [])]
                
                print(f"Available models: {available_models}")
                return self.model in available_models
                
            except requests.exceptions.RequestException as e:
                print(f"Error checking model availability at {endpoint}: {e}")
        
        return False