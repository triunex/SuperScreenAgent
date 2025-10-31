"""
Action definitions for SuperAgent

All possible actions the agent can take to control the OS.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class ActionType(Enum):
    """All possible action types"""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    DONE = "done"
    EXPLORE = "explore"
    VERIFY = "verify"
    OPEN_APP = "open_app"  # NEW: Direct app launching


@dataclass
class Action:
    """
    Single executable action
    
    Attributes:
        type: Type of action to perform
        x, y: Pixel coordinates for mouse actions
        text: Text to type
        keys: Keys for hotkey combinations
        amount: Scroll amount or wait duration
        app: App name for open_app action
        target: High-level target description
        reason: Why this action (for debugging)
        confidence: Agent's confidence (0-1)
        expected_outcome: What should happen after
    """
    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    amount: Optional[int] = None
    app: Optional[str] = None  # NEW: For open_app action
    target: Optional[str] = None
    reason: str = ""
    confidence: float = 1.0
    expected_outcome: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'type': self.type.value,
            'x': self.x,
            'y': self.y,
            'text': self.text[:50] + '...' if self.text and len(self.text) > 50 else self.text,
            'keys': self.keys,
            'amount': self.amount,
            'app': self.app,  # NEW
            'target': self.target,
            'reason': self.reason,
            'confidence': self.confidence
        }
    
    def __str__(self) -> str:
        """Human-readable representation"""
        if self.type == ActionType.CLICK:
            return f"Click at ({self.x}, {self.y}) - {self.reason}"
        elif self.type == ActionType.TYPE:
            return f"Type '{self.text}' - {self.reason}"
        elif self.type == ActionType.HOTKEY:
            return f"Press {'+'.join(self.keys)} - {self.reason}"
        elif self.type == ActionType.SCROLL:
            return f"Scroll {self.amount} - {self.reason}"
        elif self.type == ActionType.WAIT:
            return f"Wait {self.amount}s - {self.reason}"
        else:
            return f"{self.type.value} - {self.reason}"


@dataclass
class ActionResult:
    """Result of executing an action"""
    success: bool
    action: Action
    error: Optional[str] = None
    duration: float = 0.0
    screenshot_before: Optional[Any] = None
    screenshot_after: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'action': self.action.to_dict(),
            'error': self.error,
            'duration': self.duration
        }
