"""
SuperAgent - Core OODA Loop Implementation

Architecture:
OBSERVE → Get screenshot, build context
ORIENT  → Analyze situation with vision
DECIDE  → Pick best action
ACT     → Execute action, verify result

Goals:
- 90-95% success rate
- <3s response time
- Enterprise-grade safety
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .vision import VisionAPI
from .executor import ActionExecutor
from .memory import ShortTermMemory, WorkflowMemory
from .actions import Action, ActionType, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of task execution"""
    success: bool
    task: str
    actions_taken: int
    duration: float
    error: Optional[str] = None
    final_state: Optional[str] = None


class SuperAgent:
    """
    Main agent with OODA loop
    
    Usage:
        agent = SuperAgent(api_key="...")
        result = agent.execute_task("Find and open Chrome browser")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "anthropic/claude-3.5-sonnet",
        max_iterations: int = 30,
        memory_path: Optional[str] = None,
        vision_api: Optional[Any] = None  # Accept pre-initialized vision API
    ):
        # Use provided vision API or create default
        if vision_api:
            self.vision = vision_api
        elif api_key:
            self.vision = VisionAPI(api_key=api_key, base_url=base_url, model=model)
        else:
            raise ValueError("Either vision_api or api_key must be provided")
            
        self.executor = ActionExecutor()
        self.short_memory = ShortTermMemory(max_size=10)
        self.long_memory = WorkflowMemory(persistence_path=memory_path)
        
        self.max_iterations = max_iterations
        self.current_task = None
        
        model_name = getattr(self.vision, 'model', model)
        logger.info(f"SuperAgent initialized (model: {model_name}, max_iterations: {max_iterations})")
    
    def execute_task(self, task: str, timeout: float = 240.0) -> TaskResult:
        """
        Execute task using OODA loop
        
        Args:
            task: Natural language task description
            timeout: Maximum time in seconds
            
        Returns:
            TaskResult with outcome
        """
        logger.info(f"=== Starting Task: {task} ===")
        
        self.current_task = task
        self.short_memory.start_task(task)
        start_time = time.time()
        
        # Check if we've done similar task before
        similar = self.long_memory.get_similar_workflow(task)
        if similar:
            logger.info(f"Found similar workflow (used {similar['success_count']} times)")
        
        iteration = 0
        actions_taken = []
        
        try:
            while iteration < self.max_iterations:
                iteration += 1
                
                # Check timeout
                if time.time() - start_time > timeout:
                    return TaskResult(
                        success=False,
                        task=task,
                        actions_taken=len(actions_taken),
                        duration=time.time() - start_time,
                        error=f"Timeout after {timeout}s"
                    )
                
                logger.info(f"\n--- Iteration {iteration}/{self.max_iterations} ---")
                
                # OODA LOOP
                action = self._ooda_cycle(task)
                
                if not action:
                    logger.error("Failed to get action from vision API")
                    break
                
                # Check for completion
                if action.type == ActionType.DONE:
                    logger.info(f"✓ Task completed: {action.reason}")
                    
                    # Record successful workflow
                    duration = time.time() - start_time
                    self.long_memory.record_successful_workflow(task, actions_taken, duration)
                    
                    return TaskResult(
                        success=True,
                        task=task,
                        actions_taken=len(actions_taken),
                        duration=duration,
                        final_state=action.reason
                    )
                
                # Execute action
                logger.info(f"Executing: {action}")
                result = self.executor.execute(action, verify=True)
                
                # Remember it
                self.short_memory.add(action, result, context={'iteration': iteration})
                actions_taken.append(action)
                
                if not result.success:
                    logger.warning(f"Action failed: {result.error}")
                    
                    # Check if stuck in loop
                    if self.short_memory.detect_loop(threshold=3):
                        logger.error("Stuck in loop, trying exploration")
                        self._explore_alternative()
                
                # Brief pause for stability
                time.sleep(0.2)
            
            # Max iterations reached
            logger.warning(f"Max iterations ({self.max_iterations}) reached")
            return TaskResult(
                success=False,
                task=task,
                actions_taken=len(actions_taken),
                duration=time.time() - start_time,
                error="Max iterations reached without completion"
            )
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return TaskResult(
                success=False,
                task=task,
                actions_taken=len(actions_taken),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def _ooda_cycle(self, task: str) -> Optional[Action]:
        """
        Execute one OODA cycle
        
        Returns:
            Next action to take
        """
        # OBSERVE - Get current state
        screenshot = self.executor._capture_screen()
        if not screenshot:
            logger.error("Failed to capture screen")
            return None
        
        # Get context from memory
        context = self.short_memory.get_context()
        
        # ORIENT + DECIDE - Vision API analyzes and decides
        action = self.vision.get_action(
            screenshot=screenshot,
            task=task,
            context=context
        )
        
        return action
    
    def _explore_alternative(self) -> Optional[Action]:
        """
        When stuck, explore for alternative paths
        
        Uses vision API in exploration mode to find different approaches
        """
        logger.info("Exploring alternative approaches...")
        
        screenshot = self.executor._capture_screen()
        if not screenshot:
            return None
        
        context = self.short_memory.get_context()
        context['stuck'] = True
        context['instruction'] = 'Find alternative way to proceed'
        
        # Use exploration mode
        action = self.vision.get_action(
            screenshot=screenshot,
            task=self.current_task,
            context=context,
            mode='explore'
        )
        
        return action
    
    def verify_completion(self, expected_outcome: str) -> bool:
        """
        Verify task was completed successfully
        
        Args:
            expected_outcome: Description of expected state
            
        Returns:
            True if outcome matches expectations
        """
        screenshot = self.executor._capture_screen()
        if not screenshot:
            return False
        
        result = self.vision.verify_action(
            screenshot_before=screenshot,
            screenshot_after=screenshot,
            expected_outcome=expected_outcome
        )
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'vision': self.vision.get_stats(),
            'executor': self.executor.get_stats(),
            'short_memory': self.short_memory.get_stats(),
            'long_memory': self.long_memory.get_stats(),
            'current_task': self.current_task
        }
    
    def reset(self):
        """Reset agent state"""
        self.short_memory = ShortTermMemory(max_size=10)
        self.current_task = None
        logger.info("Agent reset")


class MultiTaskAgent(SuperAgent):
    """
    Extended agent for sequential multi-task workflows
    
    Example:
        agent = MultiTaskAgent(api_key="...")
        tasks = [
            "Open Gmail",
            "Find email from john@example.com",
            "Extract lead info",
            "Open HubSpot",
            "Create new contact with extracted info"
        ]
        result = agent.execute_workflow(tasks)
    """
    
    def execute_workflow(self, tasks: List[str], timeout_per_task: float = 60.0) -> Dict[str, Any]:
        """
        Execute sequence of tasks
        
        Args:
            tasks: List of task descriptions
            timeout_per_task: Max time per task
            
        Returns:
            Workflow result with per-task outcomes
        """
        logger.info(f"=== Starting Workflow: {len(tasks)} tasks ===")
        
        start_time = time.time()
        results = []
        workflow_data = {}  # Data passed between tasks
        
        for i, task in enumerate(tasks, 1):
            logger.info(f"\n>>> Task {i}/{len(tasks)}: {task}")
            
            # Add context from previous tasks
            enriched_task = task
            if workflow_data:
                enriched_task = f"{task}\n\nContext: {workflow_data}"
            
            # Execute task
            result = self.execute_task(enriched_task, timeout=timeout_per_task)
            results.append({
                'task': task,
                'success': result.success,
                'duration': result.duration,
                'actions': result.actions_taken,
                'error': result.error
            })
            
            # Stop on failure
            if not result.success:
                logger.error(f"Task {i} failed, stopping workflow")
                break
            
            # TODO: Extract data from completed task for next task
            # This would use vision API to extract relevant info from screen
        
        total_duration = time.time() - start_time
        success_count = sum(1 for r in results if r['success'])
        
        workflow_result = {
            'success': success_count == len(tasks),
            'total_tasks': len(tasks),
            'completed_tasks': success_count,
            'duration': total_duration,
            'results': results
        }
        
        logger.info(f"=== Workflow Complete: {success_count}/{len(tasks)} tasks succeeded ===")
        
        return workflow_result
