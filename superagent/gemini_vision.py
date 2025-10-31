"""
Gemini Vision API Adapter for SuperAgent
Uses Google's FREE Gemini 1.5 Pro with vision capabilities
"""

import os
import time
import base64
import json
import requests
from io import BytesIO
from typing import Dict, Any, Optional
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class GeminiVisionAPI:
    """
    Gemini Vision API - FREE tier with great vision capabilities
    
    Features:
    - Free tier: 15 requests/minute
    - Excellent vision understanding
    - Fast responses (~2-4s)
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro-vision",  # Correct model name
        timeout: int = 30
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
        
        # Stats
        self.total_calls = 0
        self.success_count = 0
        self.total_time = 0.0
        self.avg_response_time = 0.0
        
        logger.info(f"GeminiVisionAPI initialized (model: {model})")
    
    def analyze_screen(
        self,
        screenshot: Image.Image,
        task: str,
        context: Dict[str, Any],
        mode: str = "action"
    ) -> Dict[str, Any]:
        """Main entry point for screen analysis"""
        
        start_time = time.time()
        
        try:
            # Build prompt
            prompt = self._build_prompt(task, context, mode)
            
            # Encode image
            img_base64 = self._encode_image(screenshot)
            
            # Call Gemini API
            response = self._call_gemini_api(prompt, img_base64)
            
            # Parse response
            result = self._parse_response(response)
            
            # Update stats
            duration = time.time() - start_time
            self.total_calls += 1
            self.total_time += duration
            self.avg_response_time = self.total_time / self.total_calls
            self.success_count += 1
            
            logger.info(f"Gemini API: {duration:.2f}s, avg: {self.avg_response_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            duration = time.time() - start_time
            self.total_calls += 1
            self.total_time += duration
            
            # Return safe fallback
            return self._create_fallback_response(task, str(e))
    
    def _build_prompt(self, task: str, context: Dict[str, Any], mode: str) -> str:
        """Build optimized prompt for Gemini"""
        
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
    "type": "click|type|hotkey|scroll|wait|done|double_click|right_click|open_app",
    "x": <pixel_x>,
    "y": <pixel_y>,
    "text": "text to type",
    "keys": ["ctrl", "t"],
    "amount": <number>,
    "app": "chrome|gmail|slack|notion|zoom|facebook|instagram|salesforce",
    "target": "what element",
    "reason": "why this action",
    "expected_outcome": "what should happen"
  }}
}}

DECISION RULES:
- To open an app: {{"action": {{"type": "open_app", "app": "chrome", "reason": "opening chrome"}}}}
- If you just opened an app (check history): DON'T open it again! Wait or try other action
- If screen is blank BUT you already opened app in last 2 actions: Use wait or hotkey, NOT open_app again
- If screen is blank and NO recent app open: Use open_app
- If task complete: {{"action": {{"type": "done"}}}}
- If stuck (3+ similar actions): Try completely different approach
- High confidence only: Set confidence based on visual clarity
- Precise coordinates: Measure pixel positions carefully
- Be fast: Choose simplest path to goal"""
    
    def _encode_image(self, screenshot: Image.Image) -> str:
        """Encode image for Gemini API"""
        
        # Resize if too large
        max_size = 1920
        if screenshot.width > max_size or screenshot.height > max_size:
            ratio = max_size / max(screenshot.width, screenshot.height)
            new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
            screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to JPEG (Gemini prefers JPEG)
        buffer = BytesIO()
        screenshot.save(buffer, format='JPEG', quality=85)
        img_bytes = buffer.getvalue()
        
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _call_gemini_api(self, prompt: str, img_base64: str, max_retries: int = 3) -> Dict:
        """Call Gemini API with retry logic"""
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": img_base64
                                    }
                                }
                            ]
                        }],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2048,  # Increased from 600 to prevent truncation
                        }
                    },
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Timeout, retry {attempt+1}/{max_retries} after {wait}s")
                    time.sleep(wait)
                else:
                    raise
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Gemini API call failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise
    
    def _parse_response(self, api_response: Dict) -> Dict[str, Any]:
        """Parse Gemini response"""
        
        try:
            # Check if response is complete
            candidate = api_response.get('candidates', [{}])[0]
            finish_reason = candidate.get('finishReason', '')
            
            # Handle truncated responses
            if finish_reason == 'MAX_TOKENS':
                logger.warning("Response truncated due to MAX_TOKENS - using fallback")
                return self._create_fallback_response("", "MAX_TOKENS")
            
            # Extract text from Gemini response
            content = candidate.get('content', {})
            parts = content.get('parts', [])
            
            if not parts or 'text' not in parts[0]:
                logger.error("No text in response parts")
                raise ValueError("Missing text in response")
            
            text = parts[0]['text']
            
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
            
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Response: {str(api_response)[:500]}")
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
                'target': 'system',
                'reason': f'API error: {error}',
                'expected_outcome': 'System recovers'
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'total_calls': self.total_calls,
            'success_count': self.success_count,
            'success_rate': self.success_count / max(self.total_calls, 1),
            'avg_response_time': self.avg_response_time,
            'total_time': self.total_time
        }
    
    def get_action(
        self,
        screenshot: Image.Image,
        task: str,
        context: Dict[str, Any],
        mode: str = "action"
    ) -> Optional['Action']:
        """
        Get next action from vision API (wrapper for analyze_screen)
        Returns Action object or None
        """
        from .actions import Action, ActionType
        
        # Analyze screen using vision API
        result = self.analyze_screen(screenshot, task, context, mode)
        
        if not result or 'action' not in result:
            return None
        
        # Convert result to Action object
        try:
            # Extract action dict
            action_data = result['action']
            action_type = ActionType[action_data['type'].upper()]
            
            return Action(
                type=action_type,
                x=action_data.get('x'),
                y=action_data.get('y'),
                text=action_data.get('text'),
                keys=action_data.get('keys'),
                amount=action_data.get('amount'),
                target=action_data.get('target'),
                reason=action_data.get('reason', ''),
                confidence=result.get('confidence', 0.0),
                expected_outcome=action_data.get('expected_outcome')
            )
        except Exception as e:
            logger.error(f"Failed to create Action from result: {e}")
            logger.error(f"Result structure: {result}")
            return None
    
    def verify_action(
        self,
        screenshot_before: Image.Image,
        screenshot_after: Image.Image,
        expected_outcome: str
    ) -> bool:
        """
        Verify if action achieved expected outcome
        """
        # Use verify mode to check outcome
        context = {
            'expected_outcome': expected_outcome,
            'verification': True
        }
        
        result = self.analyze_screen(
            screenshot_after,
            f"Verify: {expected_outcome}",
            context,
            mode="verify"
        )
        
        return result.get('success', False)
