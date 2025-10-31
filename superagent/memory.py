"""
Memory System - Short-term and long-term memory for learning and adaptation

Features:
- Remember recent actions for context
- Learn UI patterns across sessions
- Track what works and what fails
- Optimize future decisions
"""

import time
import json
from typing import List, Dict, Any, Optional
from collections import deque
from dataclasses import dataclass, asdict
import logging

from .actions import Action, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Single memory entry"""
    timestamp: float
    action: Dict[str, Any]
    success: bool
    context: Dict[str, Any]
    outcome: Optional[str] = None


class ShortTermMemory:
    """
    Working memory for current task
    
    Remembers:
    - Last N actions taken
    - Success/failure patterns
    - Context for LLM
    """
    
    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.memory = deque(maxlen=max_size)
        self.current_task = None
        self.start_time = None
    
    def start_task(self, task: str):
        """Initialize memory for new task"""
        self.current_task = task
        self.start_time = time.time()
        self.memory.clear()
        logger.info(f"Started new task: {task}")
    
    def add(self, action: Action, result: ActionResult, context: Dict[str, Any] = None):
        """Add action to memory"""
        entry = MemoryEntry(
            timestamp=time.time(),
            action=action.to_dict(),
            success=result.success,
            context=context or {},
            outcome=result.error if not result.success else "success"
        )
        
        self.memory.append(entry)
        logger.debug(f"Memory: {len(self.memory)}/{self.max_size} entries")
    
    def get_context(self) -> Dict[str, Any]:
        """Get context for LLM decision making"""
        if not self.memory:
            return {
                'last_action': None,
                'history': [],
                'success_rate': 0.0,
                'duration': 0.0
            }
        
        # Build concise history
        history = []
        for entry in list(self.memory)[-5:]:  # Last 5 actions
            status = "✓" if entry.success else "✗"
            action_type = entry.action.get('type', 'unknown')
            reason = entry.action.get('reason', '')
            history.append(f"{status} {action_type}: {reason}")
        
        # Calculate success rate
        successes = sum(1 for e in self.memory if e.success)
        success_rate = successes / len(self.memory) if self.memory else 0.0
        
        # Get last action
        last_entry = self.memory[-1]
        last_action_str = f"{last_entry.action.get('type')}: {last_entry.action.get('reason')}"
        
        # Task duration
        duration = time.time() - self.start_time if self.start_time else 0.0
        
        return {
            'last_action': last_action_str,
            'history': history,
            'success_rate': success_rate,
            'duration': duration,
            'total_actions': len(self.memory)
        }
    
    def get_last_action(self) -> Optional[Action]:
        """Get the last action taken"""
        if not self.memory:
            return None
        return self.memory[-1].action
    
    def detect_loop(self, threshold: int = 3) -> bool:
        """
        Detect if agent is stuck in a loop
        
        Returns True if same action repeated multiple times
        """
        if len(self.memory) < threshold:
            return False
        
        recent_actions = [e.action.get('type') for e in list(self.memory)[-threshold:]]
        
        # Check if all recent actions are the same
        if len(set(recent_actions)) == 1:
            logger.warning(f"Loop detected: {recent_actions[0]} repeated {threshold} times")
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        if not self.memory:
            return {
                'entries': 0,
                'success_rate': 0.0,
                'duration': 0.0
            }
        
        successes = sum(1 for e in self.memory if e.success)
        
        return {
            'entries': len(self.memory),
            'success_rate': (successes / len(self.memory)) * 100,
            'duration': time.time() - self.start_time if self.start_time else 0.0,
            'current_task': self.current_task
        }


class WorkflowMemory:
    """
    Long-term memory for workflows and patterns
    
    Learns:
    - Successful action sequences
    - UI element locations
    - Common patterns per app
    """
    
    def __init__(self, persistence_path: Optional[str] = None):
        self.persistence_path = persistence_path
        self.workflows = {}  # task -> successful action sequence
        self.ui_patterns = {}  # app -> UI element patterns
        self.success_patterns = {}  # task type -> what works
        
        # Load from disk if path provided
        if persistence_path:
            self.load()
    
    def record_successful_workflow(self, task: str, actions: List[Action], duration: float):
        """Record a successful task completion"""
        workflow_key = self._normalize_task(task)
        
        workflow_data = {
            'task': task,
            'actions': [a.to_dict() for a in actions],
            'duration': duration,
            'success_count': self.workflows.get(workflow_key, {}).get('success_count', 0) + 1,
            'last_used': time.time()
        }
        
        self.workflows[workflow_key] = workflow_data
        logger.info(f"Recorded successful workflow: {workflow_key}")
        
        # Persist if configured
        if self.persistence_path:
            self.save()
    
    def get_similar_workflow(self, task: str) -> Optional[Dict[str, Any]]:
        """Find similar successful workflow"""
        task_key = self._normalize_task(task)
        
        # Direct match
        if task_key in self.workflows:
            return self.workflows[task_key]
        
        # Fuzzy match on task keywords
        task_words = set(task_key.lower().split())
        
        best_match = None
        best_score = 0
        
        for workflow_key, workflow_data in self.workflows.items():
            workflow_words = set(workflow_key.lower().split())
            overlap = len(task_words & workflow_words)
            
            if overlap > best_score:
                best_score = overlap
                best_match = workflow_data
        
        if best_score >= 2:  # At least 2 words in common
            logger.info(f"Found similar workflow with score {best_score}")
            return best_match
        
        return None
    
    def record_ui_pattern(self, app: str, element: str, location: Dict[str, int]):
        """Record UI element location for future reference"""
        if app not in self.ui_patterns:
            self.ui_patterns[app] = {}
        
        self.ui_patterns[app][element] = {
            'location': location,
            'last_seen': time.time(),
            'confidence': self.ui_patterns[app].get(element, {}).get('confidence', 0) + 0.1
        }
        
        logger.debug(f"Recorded UI pattern: {app}/{element} at {location}")
    
    def get_ui_hint(self, app: str, element: str) -> Optional[Dict[str, Any]]:
        """Get hint about where UI element might be"""
        if app in self.ui_patterns and element in self.ui_patterns[app]:
            pattern = self.ui_patterns[app][element]
            
            # Only return if recently seen (within 7 days)
            age = time.time() - pattern['last_seen']
            if age < 7 * 24 * 3600:
                return pattern
        
        return None
    
    def _normalize_task(self, task: str) -> str:
        """Normalize task string for matching"""
        return task.lower().strip()
    
    def save(self):
        """Save memory to disk"""
        if not self.persistence_path:
            return
        
        try:
            data = {
                'workflows': self.workflows,
                'ui_patterns': self.ui_patterns,
                'success_patterns': self.success_patterns
            }
            
            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved memory to {self.persistence_path}")
            
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def load(self):
        """Load memory from disk"""
        if not self.persistence_path:
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)
            
            self.workflows = data.get('workflows', {})
            self.ui_patterns = data.get('ui_patterns', {})
            self.success_patterns = data.get('success_patterns', {})
            
            logger.info(f"Loaded memory from {self.persistence_path}")
            logger.info(f"  - {len(self.workflows)} workflows")
            logger.info(f"  - {len(self.ui_patterns)} UI patterns")
            
        except FileNotFoundError:
            logger.info("No existing memory file found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            'total_workflows': len(self.workflows),
            'total_ui_patterns': sum(len(patterns) for patterns in self.ui_patterns.values()),
            'apps_learned': len(self.ui_patterns)
        }
