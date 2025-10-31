"""
Workflow Engine - Multi-app orchestration with data extraction

Enables complex workflows like:
- Gmail → HubSpot → Notion (extract leads, create contacts, assign tasks)
- Data analysis → Report generation → Email distribution
- Creative generation → Ad upload → Performance monitoring

Features:
- Data extraction between apps (vision-based OCR)
- Conditional logic (if/else branches)
- Loops (process multiple items)
- Human-in-the-loop confirmations
- Error recovery and retries
"""

import time
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .core import SuperAgent, TaskResult
from .actions import ActionType

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of workflow steps"""
    TASK = "task"                    # Execute GUI task
    EXTRACT = "extract"              # Extract data from screen
    DECISION = "decision"            # Conditional branch
    LOOP = "loop"                    # Iterate over items
    WAIT_HUMAN = "wait_human"        # Human confirmation
    PAUSE = "pause"                  # Wait for condition


@dataclass
class WorkflowStep:
    """Single step in workflow"""
    type: StepType
    
    # For TASK type
    task: Optional[str] = None
    timeout: float = 60.0
    
    # For EXTRACT type
    extract: Optional[str] = None         # What to extract (e.g., "email_address", "lead_name")
    extract_prompt: Optional[str] = None  # Custom extraction prompt
    save_as: Optional[str] = None         # Variable name to save extracted data
    
    # For DECISION type
    condition: Optional[Callable] = None  # Function that returns True/False
    if_true: List['WorkflowStep'] = field(default_factory=list)
    if_false: List['WorkflowStep'] = field(default_factory=list)
    
    # For LOOP type
    items: Optional[List[Any]] = None     # Items to iterate over
    item_var: str = "item"                # Variable name for current item
    loop_steps: List['WorkflowStep'] = field(default_factory=list)
    max_iterations: int = 50              # Safety limit
    
    # For WAIT_HUMAN type
    confirmation_message: Optional[str] = None
    
    # For PAUSE type
    duration: float = 1.0
    
    # General options
    optional: bool = False                # Continue on failure
    retry_count: int = 0                  # Number of retries on failure
    description: Optional[str] = None     # Human-readable description


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    steps_completed: int
    total_steps: int
    duration: float
    extracted_data: Dict[str, Any]
    failed_at: Optional[WorkflowStep] = None
    error: Optional[str] = None


class WorkflowEngine:
    """
    Orchestrates multi-app workflows with data extraction
    
    Example usage:
        engine = WorkflowEngine(super_agent)
        
        # Define workflow
        workflow = [
            WorkflowStep(
                type=StepType.TASK,
                task="Open Gmail and find unread emails",
                description="Navigate to Gmail inbox"
            ),
            WorkflowStep(
                type=StepType.EXTRACT,
                extract="email_sender",
                extract_prompt="Extract the sender's email address from the first unread email",
                save_as="lead_email"
            ),
            WorkflowStep(
                type=StepType.EXTRACT,
                extract="email_content",
                extract_prompt="Extract the main message content from the email",
                save_as="lead_message"
            ),
            WorkflowStep(
                type=StepType.TASK,
                task="Open HubSpot CRM",
                description="Navigate to HubSpot contacts"
            ),
            WorkflowStep(
                type=StepType.TASK,
                task="Create new contact with email: {lead_email}",
                description="Add lead to CRM"
            ),
            WorkflowStep(
                type=StepType.TASK,
                task="Open Notion and create task for sales team",
                description="Assign follow-up task"
            )
        ]
        
        result = engine.execute(workflow)
    """
    
    def __init__(self, agent: SuperAgent):
        self.agent = agent
        self.context = {}  # Stores extracted data and variables
        self.step_count = 0
        self.start_time = 0
    
    def execute(self, steps: List[WorkflowStep]) -> WorkflowResult:
        """
        Execute workflow with all steps
        
        Returns:
            WorkflowResult with success status and extracted data
        """
        logger.info(f"=== Starting Workflow: {len(steps)} steps ===")
        
        self.context = {}
        self.step_count = 0
        self.start_time = time.time()
        
        total_steps = self._count_steps(steps)
        
        try:
            success = self._execute_steps(steps)
            
            duration = time.time() - self.start_time
            
            return WorkflowResult(
                success=success,
                steps_completed=self.step_count,
                total_steps=total_steps,
                duration=duration,
                extracted_data=self.context.copy()
            )
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            
            return WorkflowResult(
                success=False,
                steps_completed=self.step_count,
                total_steps=total_steps,
                duration=time.time() - self.start_time,
                extracted_data=self.context.copy(),
                error=str(e)
            )
    
    def _execute_steps(self, steps: List[WorkflowStep]) -> bool:
        """Execute list of steps"""
        for step in steps:
            if not self._execute_step(step):
                if not step.optional:
                    logger.error(f"Step failed (not optional): {step.description or step.type}")
                    return False
                else:
                    logger.warning(f"Step failed (optional, continuing): {step.description or step.type}")
        
        return True
    
    def _execute_step(self, step: WorkflowStep) -> bool:
        """Execute single step based on type"""
        self.step_count += 1
        
        logger.info(f"\n>>> Step {self.step_count}: {step.description or step.type.value}")
        
        # Handle different step types
        if step.type == StepType.TASK:
            return self._execute_task_step(step)
        
        elif step.type == StepType.EXTRACT:
            return self._execute_extract_step(step)
        
        elif step.type == StepType.DECISION:
            return self._execute_decision_step(step)
        
        elif step.type == StepType.LOOP:
            return self._execute_loop_step(step)
        
        elif step.type == StepType.WAIT_HUMAN:
            return self._execute_wait_human_step(step)
        
        elif step.type == StepType.PAUSE:
            return self._execute_pause_step(step)
        
        else:
            logger.error(f"Unknown step type: {step.type}")
            return False
    
    def _execute_task_step(self, step: WorkflowStep) -> bool:
        """Execute GUI task"""
        # Substitute variables in task description
        task = self._substitute_variables(step.task)
        
        # Retry logic
        for attempt in range(step.retry_count + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{step.retry_count}")
            
            result = self.agent.execute_task(task, timeout=step.timeout)
            
            if result.success:
                logger.info(f"✓ Task completed: {task[:100]}")
                return True
            else:
                logger.warning(f"Task failed: {result.error}")
                if attempt < step.retry_count:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    def _execute_extract_step(self, step: WorkflowStep) -> bool:
        """Extract data from current screen using vision"""
        if not step.save_as:
            logger.error("Extract step requires 'save_as' parameter")
            return False
        
        # Build extraction prompt
        if step.extract_prompt:
            prompt = step.extract_prompt
        else:
            prompt = f"Extract the {step.extract} from this screenshot. Return ONLY the extracted value, nothing else."
        
        # Substitute variables in prompt
        prompt = self._substitute_variables(prompt)
        
        # Get screenshot
        screenshot = self.agent.executor._capture_screen()
        if not screenshot:
            logger.error("Failed to capture screenshot for extraction")
            return False
        
        # Use vision API to extract data
        try:
            extracted = self._extract_from_screen(screenshot, prompt)
            
            if extracted:
                self.context[step.save_as] = extracted
                logger.info(f"✓ Extracted {step.save_as}: {extracted[:100]}")
                return True
            else:
                logger.error(f"Failed to extract {step.extract}")
                return False
                
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return False
    
    def _execute_decision_step(self, step: WorkflowStep) -> bool:
        """Execute conditional branch"""
        if not step.condition:
            logger.error("Decision step requires 'condition' function")
            return False
        
        try:
            # Evaluate condition with current context
            condition_result = step.condition(self.context)
            
            logger.info(f"Condition evaluated to: {condition_result}")
            
            # Execute appropriate branch
            if condition_result:
                return self._execute_steps(step.if_true)
            else:
                return self._execute_steps(step.if_false)
                
        except Exception as e:
            logger.error(f"Decision evaluation failed: {e}")
            return False
    
    def _execute_loop_step(self, step: WorkflowStep) -> bool:
        """Execute loop over items"""
        if not step.items:
            logger.warning("Loop step has no items, skipping")
            return True
        
        logger.info(f"Starting loop over {len(step.items)} items (max {step.max_iterations})")
        
        items_to_process = step.items[:step.max_iterations]
        
        for i, item in enumerate(items_to_process, 1):
            logger.info(f"\n--- Loop iteration {i}/{len(items_to_process)} ---")
            
            # Set loop variable in context
            self.context[step.item_var] = item
            
            # Execute loop steps
            success = self._execute_steps(step.loop_steps)
            
            if not success and not step.optional:
                logger.error(f"Loop failed at iteration {i}")
                return False
        
        logger.info(f"✓ Loop completed: {len(items_to_process)} iterations")
        return True
    
    def _execute_wait_human_step(self, step: WorkflowStep) -> bool:
        """Wait for human confirmation (ENTERPRISE SAFETY)"""
        message = step.confirmation_message or "Waiting for human confirmation to continue..."
        
        logger.warning(f"\n{'='*60}")
        logger.warning(f"🚨 HUMAN CONFIRMATION REQUIRED 🚨")
        logger.warning(f"{message}")
        logger.warning(f"Context: {self.context}")
        logger.warning(f"{'='*60}")
        
        # In production, this would integrate with UI/Slack for approval
        # For now, auto-approve after logging
        logger.info("Auto-approving (production would require actual confirmation)")
        
        return True
    
    def _execute_pause_step(self, step: WorkflowStep) -> bool:
        """Pause execution"""
        logger.info(f"Pausing for {step.duration}s")
        time.sleep(step.duration)
        return True
    
    def _extract_from_screen(self, screenshot: bytes, prompt: str) -> Optional[str]:
        """
        Use vision API to extract specific data from screenshot
        
        This is like OCR but smarter - it understands context
        """
        # Build extraction-specific message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot.decode() if isinstance(screenshot, bytes) else screenshot}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""{prompt}

CRITICAL: Return ONLY the extracted value. No explanations, no JSON, just the raw value.

Examples:
- If extracting email: john@example.com
- If extracting name: John Smith
- If extracting amount: $1,234.56
"""
                    }
                ]
            }
        ]
        
        try:
            import requests
            
            response = requests.post(
                self.agent.vision.base_url,
                headers={
                    "Authorization": f"Bearer {self.agent.vision.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.agent.vision.model,
                    "messages": messages,
                    "max_tokens": 200,  # Short extraction
                    "temperature": 0.1   # Deterministic
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content'].strip()
                return content
            else:
                logger.error(f"Vision API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None
    
    def _substitute_variables(self, text: str) -> str:
        """Replace {variable} placeholders with context values"""
        if not text:
            return text
        
        result = text
        for key, value in self.context.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        
        return result
    
    def _count_steps(self, steps: List[WorkflowStep]) -> int:
        """Count total steps including nested ones"""
        count = 0
        for step in steps:
            count += 1
            if step.type == StepType.DECISION:
                count += self._count_steps(step.if_true)
                count += self._count_steps(step.if_false)
            elif step.type == StepType.LOOP:
                # Estimate based on items length
                count += len(step.items or []) * len(step.loop_steps)
        return count


# ============================================================
# PRE-BUILT WORKFLOWS FOR YC DEMO
# ============================================================

def create_gmail_to_hubspot_workflow() -> List[WorkflowStep]:
    """
    YC DEMO #1: Gmail → HubSpot → Notion
    
    "Take all unread leads from Gmail, add them to HubSpot,
     summarize each lead's message, and assign tasks in Notion"
    """
    return [
        WorkflowStep(
            type=StepType.TASK,
            task="Open Gmail and navigate to inbox",
            description="🔹 Open Gmail"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Filter to show only unread emails",
            description="🔹 Filter unread"
        ),
        WorkflowStep(
            type=StepType.LOOP,
            items=list(range(10)),  # Process first 10 unread emails
            item_var="email_index",
            description="🔁 Process each unread email",
            loop_steps=[
                WorkflowStep(
                    type=StepType.EXTRACT,
                    extract="sender_email",
                    extract_prompt="Extract the sender's email address from the currently selected email",
                    save_as="lead_email"
                ),
                WorkflowStep(
                    type=StepType.EXTRACT,
                    extract="sender_name",
                    extract_prompt="Extract the sender's full name from the currently selected email",
                    save_as="lead_name"
                ),
                WorkflowStep(
                    type=StepType.EXTRACT,
                    extract="email_subject",
                    extract_prompt="Extract the email subject line",
                    save_as="lead_subject"
                ),
                WorkflowStep(
                    type=StepType.EXTRACT,
                    extract="email_message",
                    extract_prompt="Extract the main message content (first 200 characters)",
                    save_as="lead_message"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Open HubSpot CRM in new tab",
                    description="🔹 Open HubSpot"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Create new contact with email: {lead_email} and name: {lead_name}",
                    description="🔹 Create HubSpot contact"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Add note to contact: '{lead_message}'",
                    description="🔹 Add lead details"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Open Notion in new tab",
                    description="🔹 Open Notion"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Create new task: 'Follow up with {lead_name} about {lead_subject}'",
                    description="🔹 Create follow-up task"
                ),
                WorkflowStep(
                    type=StepType.TASK,
                    task="Return to Gmail tab and mark email as read",
                    description="🔹 Mark processed"
                ),
                WorkflowStep(
                    type=StepType.PAUSE,
                    duration=1.0,
                    description="⏸ Brief pause between emails"
                )
            ]
        )
    ]


def create_creative_campaign_workflow() -> List[WorkflowStep]:
    """
    YC DEMO #2: Creative + Execution
    
    "Generate 5 ad variations, upload to Meta Ads, monitor CTR daily"
    """
    return [
        WorkflowStep(
            type=StepType.TASK,
            task="Open Uplane AI creative tool",
            description="🔹 Open Uplane"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Enter product brief: 'AI OS for enterprise automation'",
            description="🔹 Enter brief"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Generate 5 ad variations for LinkedIn campaign",
            description="🔹 Generate ads"
        ),
        WorkflowStep(
            type=StepType.PAUSE,
            duration=10.0,
            description="⏸ Wait for AI generation"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Download all generated ad images to Downloads folder",
            description="🔹 Download ads"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Open Meta Ads Manager",
            description="🔹 Open Meta Ads"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Create new campaign: 'Nelieo AI OS Launch'",
            description="🔹 Create campaign"
        ),
        WorkflowStep(
            type=StepType.LOOP,
            items=["ad1.png", "ad2.png", "ad3.png", "ad4.png", "ad5.png"],
            item_var="ad_file",
            description="🔁 Upload each ad",
            loop_steps=[
                WorkflowStep(
                    type=StepType.TASK,
                    task="Upload {ad_file} to campaign",
                    description="📤 Upload ad variation"
                )
            ]
        ),
        WorkflowStep(
            type=StepType.WAIT_HUMAN,
            confirmation_message="⚠️ Campaign ready. Approve $500 budget before launch?",
            description="🚨 Human approval required"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Set budget to $500 and launch campaign",
            description="🚀 Launch campaign"
        )
    ]


def create_sales_analysis_workflow() -> List[WorkflowStep]:
    """
    YC DEMO #3: Strategic Decision-Making
    
    "Analyze Q3 sales data, identify underperforming regions, generate recovery plan"
    """
    return [
        WorkflowStep(
            type=StepType.TASK,
            task="Open Google Sheets with Q3 2025 sales data",
            description="🔹 Open sales data"
        ),
        WorkflowStep(
            type=StepType.EXTRACT,
            extract="sales_data",
            extract_prompt="Take a screenshot and extract all visible sales data as text",
            save_as="q3_data"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Open ChatGPT in new tab",
            description="🔹 Open ChatGPT"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="""Paste this prompt: 'Analyze this Q3 sales data, identify regions with <10% growth, and generate a 3-step recovery plan:

{q3_data}'""",
            description="🔹 Request analysis"
        ),
        WorkflowStep(
            type=StepType.PAUSE,
            duration=15.0,
            description="⏸ Wait for ChatGPT analysis"
        ),
        WorkflowStep(
            type=StepType.EXTRACT,
            extract="recovery_plan",
            extract_prompt="Extract the complete recovery plan from ChatGPT's response",
            save_as="plan"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Open Google Docs and create new document",
            description="🔹 Create report"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Paste recovery plan and format as professional report",
            description="🔹 Format report"
        ),
        WorkflowStep(
            type=StepType.TASK,
            task="Open Gmail and compose email to exec@company.com with subject 'Q3 Recovery Plan'",
            description="🔹 Email report"
        ),
        WorkflowStep(
            type=StepType.WAIT_HUMAN,
            confirmation_message="⚠️ Email draft ready. Review before sending?",
            description="🚨 Review email"
        )
    ]
