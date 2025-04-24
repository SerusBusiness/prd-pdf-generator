"""
OllamaClient for PRD Generator.
Handles communication with Ollama API for LLM generation with caching support.
"""
import json
import time
import requests
from typing import Dict, Any, Optional, List, Union, Tuple
import socket

from prd_generator.utils.cache_manager import cached
from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class OllamaClient:
    """
    Client for interacting with Ollama API.
    Includes caching support to minimize redundant API calls.
    """
    
    def __init__(self, config):
        """
        Initialize the Ollama client.
        
        Args:
            config: Configuration object containing Ollama settings
        """
        self.host = config.ollama_host
        self.model = config.ollama_model
        self.temperature = config.ollama_temperature
        
        # Set up API endpoints
        self.api_base = config.ollama_api_endpoint or f"{self.host}/api"
        self.generate_endpoint = f"{self.api_base}/generate"
        self.show_endpoint = f"{self.api_base}/show"
        
        # Track metrics
        self.total_tokens = 0
        self.total_requests = 0
        self.total_time = 0
        
        # Connection configuration
        self.max_retries = 3
        self.timeout = 120  # seconds
        self.connection_verified = False
        
        logger.info(f"OllamaClient initialized with host={self.host}, model={self.model}, temperature={self.temperature}")
        # Verify connection on initialization
        self.verify_connection()
        
    def verify_connection(self) -> bool:
        """
        Verify connection to Ollama service.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Try a simple request to verify connection
            response = requests.get(
                f"{self.host}/api/version",
                timeout=5
            )
            response.raise_for_status()
            self.connection_verified = True
            logger.info(f"Successfully connected to Ollama service: {response.json().get('version', 'unknown version')}")
            return True
        except (requests.exceptions.RequestException, socket.error) as e:
            logger.warning(f"Could not connect to Ollama service at {self.host}: {e}")
            return False
        
    @cached(ttl=7200)  # Cache responses for 2 hours
    def generate(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate text using Ollama API with caching.
        
        Args:
            prompt: The prompt text
            options: Additional generation options
            
        Returns:
            str: Generated text
        """
        start_time = time.time()
        self.total_requests += 1
        
        # Prepare request
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature
        }
        
        # Add any additional options
        if options:
            request_data.update(options)
            
        logger.debug(f"Sending request to Ollama API: model={self.model}, temp={self.temperature}, prompt_len={len(prompt)}")
        
        # Implement retry logic for network-related errors
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                response = requests.post(
                    self.generate_endpoint, 
                    json=request_data, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Update metrics
                self.total_tokens += result.get('eval_count', 0)
                elapsed = time.time() - start_time
                self.total_time += elapsed
                
                logger.debug(f"Ollama API response received in {elapsed:.2f}s, tokens: {result.get('eval_count', 0)}")
                
                return result.get("response", "")
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, socket.error) as e:
                # Only retry for connection-related errors
                retries += 1
                last_error = str(e)
                
                if retries <= self.max_retries:
                    wait_time = 2 ** retries  # Exponential backoff
                    logger.warning(f"Connection error to Ollama API (attempt {retries}/{self.max_retries}). Retrying in {wait_time}s. Error: {last_error}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to connect to Ollama API after {self.max_retries} attempts: {last_error}")
                    return f"Error: Could not connect to Ollama service after multiple attempts. Please verify that Ollama is running at {self.host}."
            except requests.exceptions.RequestException as e:
                # Don't retry for other types of errors
                logger.error(f"Error calling Ollama API: {str(e)}")
                return f"Error: {str(e)}"
            
    def generate_with_thinking(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Generate text and extract thinking process if available.
        
        Args:
            prompt: The prompt text
            options: Additional generation options
            
        Returns:
            Dict: Dictionary with 'response' and 'reasoning' keys
        """
        content = self.generate(prompt, options)
        
        if content.startswith("Error:"):
            return {"response": "", "reasoning": f"Error: {content}"}
            
        # Extract thinking output (if any)
        thinking = ""
        if "<think>" in content and "</think>" in content:
            import re
            thinking_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
                # Remove the thinking tags from content
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                
        return {"response": content, "reasoning": thinking}
        
    def generate_with_retry(self, prompt: str, max_retries: int = 3, 
                           options: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate text with automatic retries on failure.
        
        Args:
            prompt: The prompt text
            max_retries: Maximum number of retry attempts
            options: Additional generation options
            
        Returns:
            str: Generated text
        """
        retries = 0
        backoff = 2  # Initial backoff in seconds
        last_response = ""
        
        while retries <= max_retries:
            result = self.generate(prompt, options)
            
            # Check for error
            if not result.startswith("Error:"):
                return result
                
            last_response = result
            retries += 1
            
            if retries <= max_retries:
                wait_time = backoff * (2 ** (retries - 1))  # Exponential backoff
                logger.warning(f"Retry {retries}/{max_retries} after {wait_time}s: {result}")
                time.sleep(wait_time)
                
        # Return the last error response after all retries
        return last_response
        
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Dict: Model information
        """
        try:
            response = requests.post(
                self.show_endpoint,
                json={"name": self.model},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Error getting model info: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
            
    def get_metrics(self) -> Dict[str, Union[int, float]]:
        """
        Get usage metrics for the client.
        
        Returns:
            Dict: Usage metrics
        """
        avg_time = self.total_time / self.total_requests if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_time": round(self.total_time, 2),
            "avg_time_per_request": round(avg_time, 2)
        }
        
    def reset_metrics(self) -> None:
        """
        Reset usage metrics.
        """
        self.total_tokens = 0
        self.total_requests = 0
        self.total_time = 0
        logger.debug("OllamaClient metrics reset")