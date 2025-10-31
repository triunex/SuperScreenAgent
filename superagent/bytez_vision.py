"""
Bytez Vision API - FREE UNLIMITED vision models!
Using meta-llama/Llama-3.2-11B-Vision-Instruct
"""

import os
import time
import base64
import json
from io import BytesIO
from typing import Dict, Any, Optional
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class BytezVisionAPI:
    """
    Bytez Vision API - FREE UNLIMITED vision model
    
    Features:
    - NO costs, unlimited usage
    - meta-llama/Llama-3.2-11B-Vision-Instruct
    - Excellent vision understanding
    - Fast responses
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.bytez.com/v1"
        
        # Stats
        self.total_calls = 0
        self.success_count = 0
        self.total_time = 0.0
        self.avg_response_time = 0.0
        
        # Initialize cluster
        self._cluster_id = None
        
        logger.info(f"BytezVisionAPI initialized (model: {model}, FREE unlimited)")
    
    def analyze_screen(
        self,
        screenshot: Image.Image,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze screen using Bytez vision model
        
        Args:
            screenshot: PIL Image of current screen
            task: The task being performed
            context: Additional context (last_action, history, etc)
            
        Returns:
            Dict with observation, action, confidence, etc.
        """
        start_time = time.time()
        
        try:
            # Encode image
            img_base64 = self._encode_image(screenshot)
            
            # Build prompt
            prompt = self._build_prompt(task, context)
            
            # Call Bytez API
            result = self._call_bytez_api(prompt, img_base64)
            
            # Parse response
            parsed = self._parse_response(result)
            
            # Update stats
            duration = time.time() - start_time
            self.total_calls += 1
            self.success_count += 1
            self.total_time += duration
            self.avg_response_time = self.total_time / self.total_calls
            
            logger.info(f"Bytez API: {duration:.2f}s, avg: {self.avg_response_time:.2f}s")
            
            return parsed
            
        except Exception as e:
            logger.error(f"Bytez API error: {e}")
            duration = time.time() - start_time
            self.total_calls += 1
            self.total_time += duration
            
            # Return safe fallback
            return self._create_fallback_response(task, str(e))
    
    def _encode_image(self, screenshot: Image.Image) -> str:
        """Encode image for Bytez API"""
        
        # Resize if too large
        max_size = 1920
        if screenshot.width > max_size or screenshot.height > max_size:
            ratio = max_size / max(screenshot.width, screenshot.height)
            new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
            screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to PNG for better quality
        buffer = BytesIO()
        screenshot.save(buffer, format='PNG')
        img_bytes = buffer.getvalue()
        
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _build_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """Build optimized prompt for Bytez vision model"""
        
        last_action = context.get('last_action', 'None')
        steps = context.get('steps', 0)
        max_steps = context.get('max_steps', 20)
        history = context.get('history', [])
        
        history_str = "None"
        if history:
            history_str = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(history[-3:]))
        
        return f"""You are an AI controlling a Linux desktop (1920x1080) to complete tasks with superhuman speed and accuracy.

TASK: {task}

CURRENT STATE:
- Step: {steps}/{max_steps}
- Last action: {last_action}
- Recent history:
{history_str}

ANALYZE THE SCREENSHOT:
1. What app/window is active?
2. Did last action succeed? (look for visual changes)
3. What's the next optimal step?
4. Where exactly should I interact?

RESPOND WITH JSON ONLY (no markdown, no code blocks):
{{
  "observation": "one-sentence description of screen",
  "current_app": "app name",
  "last_success": true/false,
  "next_step": "concise plan",
  "confidence": 0.0-1.0,
  "action": {{
    "type": "click|type|hotkey|scroll|wait|done|double_click|right_click",
    "x": <pixel_x>,
    "y": <pixel_y>,
    "text": "text to type",
    "keys": ["ctrl", "t"],
    "amount": <number>,
    "target": "what element",
    "reason": "why this action",
    "expected_outcome": "what should happen"
  }}
}}

DECISION RULES:
- If task complete: {{"action": {{"type": "done"}}}}
- If stuck (3+ similar actions): {{"action": {{"type": "wait", "amount": 2}}}}
- High confidence only: Set confidence based on visual clarity
- Precise coordinates: Measure pixel positions carefully
- Be fast: Choose simplest path to goal"""
    
    def _call_bytez_api(self, prompt: str, img_base64: str, max_retries: int = 3) -> str:
        """Call Bytez API with retry logic"""
        
        import requests
        
        for attempt in range(max_retries):
            try:
                # Prepare the request using OpenAI-compatible format
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful AI that controls desktop applications by analyzing screenshots and deciding the next action."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3
                }
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Extract text from response
                text = result['choices'][0]['message']['content']
                return text
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Timeout, retry {attempt+1}/{max_retries} after {wait}s")
                    time.sleep(wait)
                else:
                    raise Exception("Bytez API timeout")
            
            except requests.exceptions.HTTPError as e:
                logger.error(f"Bytez API HTTP error: {e}")
                logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"HTTP error, retry {attempt+1}/{max_retries} after {wait}s")
                    time.sleep(wait)
                else:
                    raise
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Bytez API error: {e}, retry {attempt+1}/{max_retries}")
                    time.sleep(wait)
                else:
                    raise
        
        raise Exception("Bytez API failed after all retries")
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse Bytez response"""
        
        try:
            # Clean up markdown if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            
            # Parse JSON
            result = json.loads(text.strip())
            
            # Validate required fields
            if 'action' not in result:
                raise ValueError("Missing 'action' field in response")
            
            return result
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse Bytez response: {e}")
            logger.error(f"Response: {text[:500]}")
            raise
    
    def _create_fallback_response(self, task: str, error: str) -> Dict[str, Any]:
        """Create safe fallback when API fails"""
        
        logger.warning(f"Using fallback response due to: {error}")
        
        return {
            'observation': 'API error occurred',
            'current_app': 'unknown',
            'last_success': False,
            'next_step': 'Wait and retry',
            'confidence': 0.0,
            'action': {
                'type': 'wait',
                'amount': 2,
                'reason': f'API error: {error}',
                'target': 'retry',
                'expected_outcome': 'System recovery'
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            'total_calls': self.total_calls,
            'success_count': self.success_count,
            'success_rate': self.success_count / self.total_calls if self.total_calls > 0 else 0,
            'avg_response_time': self.avg_response_time,
            'model': self.model
        }
