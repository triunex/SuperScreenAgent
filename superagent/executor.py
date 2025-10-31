"""
Action Executor - Execute actions on X11 display with superhuman precision

Optimized for:
- Speed: Minimal delays between actions
- Reliability: Verify execution success
- Safety: Validate coordinates and inputs
"""

import os
import time
import subprocess
import logging
from typing import Optional, Tuple
from PIL import Image

try:
    import pyautogui
except ImportError:
    pyautogui = None
    logging.warning("pyautogui not available - install for full functionality")

from .actions import Action, ActionType, ActionResult

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    High-performance action executor for X11
    
    Features:
    - Direct X11 control via pyautogui
    - Action verification
    - Performance tracking
    - Safety bounds checking
    """
    
    def __init__(self, display: str = ':100', screen_size: Tuple[int, int] = (1920, 1080)):
        self.display = display
        self.screen_width, self.screen_height = screen_size
        
        # Configure environment
        os.environ['DISPLAY'] = display
        
        # Configure pyautogui for headless
        if pyautogui:
            pyautogui.FAILSAFE = False  # Disable mouse corner failsafe
            pyautogui.PAUSE = 0.1  # Minimal pause between actions
        
        # Performance tracking
        self.total_actions = 0
        self.successful_actions = 0
        self.total_time = 0.0
        
        logger.info(f"ActionExecutor initialized on {display} ({screen_size[0]}x{screen_size[1]})")
    
    def execute(self, action: Action, verify: bool = True) -> ActionResult:
        """
        Execute action and optionally verify success
        
        Args:
            action: Action to execute
            verify: Whether to verify execution (slower but safer)
        
        Returns:
            ActionResult with success status
        """
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None
        
        try:
            # Capture before state if verifying
            if verify and action.type not in [ActionType.WAIT, ActionType.DONE]:
                screenshot_before = self._capture_screen()
            
            # Execute the action
            success = self._execute_action(action)
            
            # Small delay for UI to respond
            if action.type != ActionType.WAIT:
                time.sleep(0.3)
            
            # Capture after state if verifying
            if verify and success and action.type not in [ActionType.WAIT, ActionType.DONE]:
                screenshot_after = self._capture_screen()
            
            # Track performance
            duration = time.time() - start_time
            self.total_actions += 1
            self.total_time += duration
            
            if success:
                self.successful_actions += 1
            
            logger.info(f"Executed {action.type.value}: {success} ({duration:.3f}s)")
            
            return ActionResult(
                success=success,
                action=action,
                duration=duration,
                screenshot_before=screenshot_before,
                screenshot_after=screenshot_after
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.total_actions += 1
            self.total_time += duration
            
            logger.error(f"Action execution failed: {e}")
            
            return ActionResult(
                success=False,
                action=action,
                error=str(e),
                duration=duration
            )
    
    def _execute_action(self, action: Action) -> bool:
        """Execute specific action type"""
        
        if not pyautogui:
            logger.error("pyautogui not available")
            return False
        
        try:
            if action.type == ActionType.CLICK:
                return self._click(action.x, action.y)
            
            elif action.type == ActionType.DOUBLE_CLICK:
                return self._double_click(action.x, action.y)
            
            elif action.type == ActionType.RIGHT_CLICK:
                return self._right_click(action.x, action.y)
            
            elif action.type == ActionType.TYPE:
                return self._type_text(action.text)
            
            elif action.type == ActionType.HOTKEY:
                return self._hotkey(action.keys)
            
            elif action.type == ActionType.SCROLL:
                return self._scroll(action.amount)
            
            elif action.type == ActionType.DRAG:
                return self._drag(action.x, action.y)
            
            elif action.type == ActionType.WAIT:
                return self._wait(action.amount)
            
            elif action.type == ActionType.DONE:
                logger.info("Task completed successfully")
                return True
            
            else:
                logger.warning(f"Unknown action type: {action.type}")
                return False
                
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return False
    
    def _click(self, x: int, y: int) -> bool:
        """Click at coordinates with bounds checking"""
        if not self._validate_coordinates(x, y):
            return False
        
        pyautogui.click(x, y)
        return True
    
    def _double_click(self, x: int, y: int) -> bool:
        """Double-click at coordinates"""
        if not self._validate_coordinates(x, y):
            return False
        
        pyautogui.doubleClick(x, y)
        return True
    
    def _right_click(self, x: int, y: int) -> bool:
        """Right-click at coordinates"""
        if not self._validate_coordinates(x, y):
            return False
        
        pyautogui.rightClick(x, y)
        return True
    
    def _type_text(self, text: str) -> bool:
        """Type text with optimal speed"""
        if not text:
            logger.warning("Empty text to type")
            return False
        
        # Type with minimal interval for speed
        pyautogui.write(text, interval=0.02)
        return True
    
    def _hotkey(self, keys: list) -> bool:
        """Execute hotkey combination"""
        if not keys or not isinstance(keys, list):
            logger.warning(f"Invalid hotkey: {keys}")
            return False
        
        # Normalize key names
        normalized_keys = [self._normalize_key(k) for k in keys]
        
        pyautogui.hotkey(*normalized_keys)
        return True
    
    def _scroll(self, amount: int) -> bool:
        """Scroll by amount (negative = down, positive = up)"""
        if amount is None:
            amount = -3  # Default scroll down
        
        pyautogui.scroll(amount)
        return True
    
    def _drag(self, x: int, y: int) -> bool:
        """Drag to coordinates"""
        if not self._validate_coordinates(x, y):
            return False
        
        pyautogui.drag(x, y, duration=0.3)
        return True
    
    def _wait(self, duration: float) -> bool:
        """Wait for specified duration"""
        if duration is None:
            duration = 1.0
        
        time.sleep(duration)
        return True
    
    def _validate_coordinates(self, x: int, y: int) -> bool:
        """Validate coordinates are within screen bounds"""
        if x is None or y is None:
            logger.error("Missing coordinates")
            return False
        
        if not (0 <= x < self.screen_width and 0 <= y < self.screen_height):
            logger.error(f"Coordinates ({x}, {y}) out of bounds (0-{self.screen_width}, 0-{self.screen_height})")
            return False
        
        return True
    
    def _normalize_key(self, key: str) -> str:
        """Normalize key names for pyautogui"""
        key_map = {
            'control': 'ctrl',
            'ctl': 'ctrl',
            'return': 'enter',
            'escape': 'esc'
        }
        return key_map.get(key.lower(), key.lower())
    
    def _capture_screen(self) -> Optional[Image.Image]:
        """Capture current screen state"""
        try:
            subprocess.run(
                ['scrot', '/tmp/action_verify.png'],
                env={'DISPLAY': self.display},
                check=True,
                capture_output=True
            )
            return Image.open('/tmp/action_verify.png')
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        if pyautogui:
            return pyautogui.position()
        return (0, 0)
    
    def move_mouse(self, x: int, y: int, duration: float = 0.2) -> bool:
        """Move mouse to position smoothly"""
        if not self._validate_coordinates(x, y):
            return False
        
        if pyautogui:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        return False
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_actions == 0:
            return 0.0
        return (self.successful_actions / self.total_actions) * 100
    
    @property
    def avg_execution_time(self) -> float:
        """Average action execution time"""
        if self.total_actions == 0:
            return 0.0
        return self.total_time / self.total_actions
    
    def get_stats(self) -> dict:
        """Get performance statistics"""
        return {
            'total_actions': self.total_actions,
            'successful_actions': self.successful_actions,
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'total_time': self.total_time
        }
