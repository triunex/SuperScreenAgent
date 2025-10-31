"""
Ollama Llama 3.2 Vision API Adapter for SuperAgent
Uses local Llama 3.2 Vision 11B - FREE and NO RATE LIMITS
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


class OllamaVisionAPI:
    """
    Ollama Llama 3.2 Vision 11B - Local, free, unlimited
    Slower but ACTUALLY WORKS
    """
    
    def __init__(
        self,
        base_url: str = "http://host.docker.internal:11434",
        model: str = "llama3.2-vision:11b",
        timeout: int = 120
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        
        # Stats
        self.total_calls = 0
        self.success_count = 0
        self.total_time = 0.0
        self.avg_response_time = 0.0
        
        logger.info(f"OllamaVisionAPI initialized (model: {model}, url: {base_url})")
    
    def analyze_screen(
        self,
        screenshot: Image.Image,
        task: str,
        context: Dict[str, Any],
        mode: str = "action"
    ) -> Dict[str, Any]:
        """Main entry point for screen analysis"""
        
        start_time = time.time()
        logger.info(f"🔍 analyze_screen called (mode={mode})")
        
        try:
            # Build prompt
            prompt = self._build_prompt(task, context, mode)
            
            # Encode image
            img_base64 = self._encode_image(screenshot)
            
            # Call Ollama API
            response = self._call_ollama_api(prompt, img_base64)
            
            # Parse response
            result = self._parse_response(response)
            
            # Update stats
            duration = time.time() - start_time
            self.total_calls += 1
            self.total_time += duration
            self.avg_response_time = self.total_time / self.total_calls
            self.success_count += 1
            
            logger.info(f"Ollama API: {duration:.2f}s, avg: {self.avg_response_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ollama API error in analyze_screen: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            duration = time.time() - start_time
            self.total_calls += 1
            self.total_time += duration
            
            # Return fallback WAIT action
            return {
                "thinking": f"API error: {str(e)}",
                "next_step": "Waiting due to error",
                "confidence": 0.1,
                "action": {
                    "type": "wait",
                    "amount": 2,
                    "reason": f"API error: {str(e)}"
                }
            }
    
    def get_action(
        self,
        screenshot: Image.Image,
        task: str,
        context: Dict[str, Any],
        mode: str = "action"
    ) -> Optional['Action']:
        """
        Get next action from vision API
        
        Returns Action object or None
        """
        from superagent.actions import Action, ActionType
        
        # Analyze screen using vision API
        result = self.analyze_screen(screenshot, task, context, mode)
        
        if not result or 'action' not in result:
            logger.error("No action in Ollama response")
            return None
        
        # Convert result to Action object
        try:
            # Extract action dict
            action_data = result['action']
            action_type_str = action_data.get('type', 'wait').upper()
            
            # Convert string to ActionType enum
            action_type = ActionType[action_type_str]
            
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
            logger.error(f"Failed to create Action from Ollama result: {e}")
            logger.error(f"Result structure: {result}")
            return None
    
    def verify_action(
        self,
        screenshot: Image.Image,
        expected_outcome: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify if action had expected outcome"""
        return self.analyze_screen(
            screenshot,
            f"Verify: {expected_outcome}",
            context,
            mode="verify"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "success_rate": self.success_count / max(1, self.total_calls),
            "avg_response_time": self.avg_response_time,
            "total_time": self.total_time
        }
    
    def _build_prompt(self, task: str, context: Dict[str, Any], mode: str) -> str:
        """Build prompt for vision model"""
        
        # Get context
        history = context.get('history', [])
        current_state = context.get('current_state', {})
        
        # Build history summary
        history_text = ""
        if history:
            history_text = "Previous actions:\n"
            for i, action in enumerate(history[-5:], 1):  # Last 5 actions
                # Handle both dict and Action object
                if hasattr(action, 'type'):
                    # It's an Action object
                    action_type = action.type.value if hasattr(action.type, 'value') else str(action.type)
                    reason = action.reason if hasattr(action, 'reason') else ''
                elif isinstance(action, dict):
                    # It's a dict
                    action_type = action.get('type', 'unknown')
                    reason = action.get('reason', '')
                else:
                    # It's something else (maybe string)
                    action_type = str(action)
                    reason = ''
                history_text += f"{i}. {action_type} - {reason}\n"
        
        return f"""You are a screen automation agent. Analyze this screenshot and decide the next action.

TASK: {task}

{history_text}

IMPORTANT CONTEXT:
- All 12 apps are ALREADY OPEN with windows/tabs visible on screen
- Apps: Chrome, Firefox, Slack, Gmail, Calendar, Notes, Terminal, Files, VS Code, Spotify, Discord, Zoom
- There are NO desktop icons - apps are already running
- To switch apps: click on their window/tab or use Alt+Tab
- Screen is 1920x1080 pixels

Your response MUST be valid JSON with this structure:
{{
  "thinking": "analyze what you see on screen",
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
- Apps are already running - just interact with their windows
- Be fast: Choose simplest path to goal

RESPOND ONLY WITH JSON, NO OTHER TEXT."""
    
    def _encode_image(self, screenshot: Image.Image) -> str:
        """Encode image for Ollama API"""
        
        # Ollama prefers smaller images for faster processing
        max_size = 1024
        if screenshot.width > max_size or screenshot.height > max_size:
            ratio = max_size / max(screenshot.width, screenshot.height)
            new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
            screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {new_size} for faster Ollama processing")
        
        # Convert to PNG
        buffer = BytesIO()
        screenshot.save(buffer, format='PNG', optimize=True)
        img_bytes = buffer.getvalue()
        
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _call_ollama_api(self, prompt: str, img_base64: str, max_retries: int = 2) -> Dict:
        """Call Ollama API with retry logic"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Ollama {self.model}... (this takes 25-40s)")
                
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [img_base64],
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 500
                        }
                    },
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Ollama returns {"response": "text"}
                if not isinstance(result, dict):
                    logger.error(f"Ollama returned non-dict: {type(result)} - {result}")
                    raise Exception(f"Invalid Ollama response type: {type(result)}")
                
                response_text = result.get("response", "")
                if not response_text:
                    logger.error(f"Empty response from Ollama. Full result: {result}")
                    raise Exception("Empty response from Ollama")
                
                return {"content": response_text}
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout, retry {attempt+1}/{max_retries}")
                    time.sleep(2)
                else:
                    raise Exception("Ollama timeout after retries")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama API call failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise
    
    def _parse_response(self, api_response: Dict) -> Dict[str, Any]:
        """Parse Ollama response"""
        
        try:
            # Handle error cases where api_response might be a string
            if isinstance(api_response, str):
                logger.error(f"API response is string, not dict: {api_response[:200]}")
                return {
                    "thinking": "Parse error - response is string",
                    "next_step": "Wait",
                    "confidence": 0.1,
                    "action": {"type": "wait", "amount": 2, "reason": "API returned string"}
                }
            
            # Extract text from Ollama response
            text = api_response.get('content', '')
            
            if not text:
                logger.error("Empty content from Ollama")
                return {
                    "thinking": "Empty response",
                    "next_step": "Wait",
                    "confidence": 0.1,
                    "action": {"type": "wait", "amount": 2, "reason": "Empty response"}
                }
            
            # Clean up markdown if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            
            # Parse JSON
            result = json.loads(text.strip())
            
            # Validate structure
            if 'action' not in result:
                raise ValueError("No 'action' in response")
            
            # Ensure action has type
            if 'type' not in result['action']:
                raise ValueError("No 'type' in action")
            
            # Set defaults
            result.setdefault('thinking', 'Processing...')
            result.setdefault('next_step', 'Taking action')
            result.setdefault('confidence', 0.5)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Raw response: {text[:500]}")
            
            # Try to extract action type from text
            if 'done' in text.lower():
                return {
                    "thinking": "Parsing failed, assuming done",
                    "next_step": "Complete",
                    "confidence": 0.3,
                    "action": {"type": "done"}
                }
            else:
                return {
                    "thinking": "Parsing failed, waiting",
                    "next_step": "Wait and retry",
                    "confidence": 0.2,
                    "action": {"type": "wait", "amount": 2, "reason": "Parse error"}
                }
        
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return {
                "thinking": f"Error: {str(e)}",
                "next_step": "Wait",
                "confidence": 0.1,
                "action": {"type": "wait", "amount": 2, "reason": str(e)}
            }
