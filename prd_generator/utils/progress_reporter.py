"""
Progress Reporter for PRD Generator.
Provides a consistent progress reporting mechanism for long-running operations.
"""
import sys
import time
from typing import Callable, Optional, Dict, Any, List
from threading import Lock

from prd_generator.core.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class ProgressReporter:
    """
    Reports progress for long-running operations.
    Supports both console output and callback functions.
    """
    
    def __init__(self, total_steps: int = 100, description: str = "Processing", 
                 callback: Optional[Callable] = None, console: bool = True):
        """
        Initialize the progress reporter.
        
        Args:
            total_steps: Total number of steps in the operation
            description: Description of the operation
            callback: Optional callback function to be called with progress updates
            console: Whether to output progress to console
        """
        self.total_steps = max(1, total_steps)  # Ensure at least 1 step
        self.current_step = 0
        self.description = description
        self.callback = callback
        self.console = console
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.lock = Lock()  # For thread safety
        self._completed = False
        
        logger.debug(f"Progress reporter initialized: {description} ({total_steps} steps)")
        
    def update(self, steps: int = 1, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Update the progress by a number of steps.
        
        Args:
            steps: Number of steps completed
            message: Optional message to include with the update
            
        Returns:
            Dict: Progress information
        """
        with self.lock:
            self.current_step = min(self.current_step + steps, self.total_steps)
            current_time = time.time()
            
            # Calculate progress percentage
            percentage = (self.current_step / self.total_steps) * 100.0
            
            # Calculate elapsed and estimated remaining time
            elapsed_time = current_time - self.start_time
            if self.current_step > 0:
                estimated_total_time = elapsed_time * (self.total_steps / self.current_step)
                remaining_time = estimated_total_time - elapsed_time
            else:
                remaining_time = 0
                
            # Format message
            if message is None:
                message = f"{self.description}: {percentage:.1f}% completed"
                
            # Create progress info dictionary
            progress_info = {
                'step': self.current_step,
                'total': self.total_steps,
                'percentage': percentage,
                'elapsed_seconds': elapsed_time,
                'remaining_seconds': remaining_time,
                'message': message,
                'description': self.description,
                'completed': (self.current_step >= self.total_steps)
            }
            
            # Call the callback if provided
            if self.callback:
                try:
                    self.callback(progress_info)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
            
            # Update console if enabled (only update console every ~500ms to avoid flooding)
            if self.console and (current_time - self.last_update_time > 0.5 or 
                               self.current_step >= self.total_steps):
                self._print_progress(progress_info)
                self.last_update_time = current_time
                
            # Log progress at certain increments
            if (percentage % 25 == 0 and percentage > 0) or percentage >= 100:
                if not self._completed and percentage >= 100:
                    logger.info(f"{self.description} completed in {elapsed_time:.2f} seconds")
                    self._completed = True
                elif not self._completed:
                    logger.info(f"{self.description}: {percentage:.1f}% completed")
                
            return progress_info
            
    def set_total(self, total_steps: int) -> None:
        """
        Update the total number of steps.
        Useful when the total is not known at initialization.
        
        Args:
            total_steps: New total number of steps
        """
        with self.lock:
            self.total_steps = max(1, total_steps)
            logger.debug(f"Updated total steps to {total_steps}")
            
    def _print_progress(self, progress_info: Dict[str, Any]) -> None:
        """
        Print progress to console.
        
        Args:
            progress_info: Dictionary containing progress information
        """
        percentage = progress_info['percentage']
        elapsed = progress_info['elapsed_seconds']
        remaining = progress_info['remaining_seconds']
        message = progress_info['message']
        
        # Create a progress bar
        bar_length = 30
        filled_length = int(bar_length * progress_info['step'] // progress_info['total'])
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Format times
        elapsed_str = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}" if elapsed >= 60 else f"{elapsed:.1f}s"
        remaining_str = f"{int(remaining // 60)}:{int(remaining % 60):02d}" if remaining >= 60 else f"{remaining:.1f}s"
        
        # Print progress line (clear the line first)
        sys.stdout.write('\r' + ' ' * 80)  # Clear line
        sys.stdout.write(f"\r[{bar}] {percentage:.1f}% | {message} | {elapsed_str} elapsed, {remaining_str} remaining")
        sys.stdout.flush()
        
        # Add a newline if completed
        if progress_info['completed']:
            sys.stdout.write('\n')
            sys.stdout.flush()
            
    def complete(self, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Mark the operation as complete.
        
        Args:
            message: Optional completion message
            
        Returns:
            Dict: Final progress information
        """
        with self.lock:
            remaining_steps = self.total_steps - self.current_step
            if remaining_steps > 0:
                return self.update(remaining_steps, message or f"{self.description}: Completed")
            return self.update(0, message or f"{self.description}: Completed")


class MultiTaskProgressReporter:
    """
    Reports progress for multiple tasks with different weights.
    Aggregates progress from multiple tasks into a single overall progress.
    """
    
    def __init__(self, tasks: Dict[str, float], description: str = "Overall Progress",
                callback: Optional[Callable] = None, console: bool = True):
        """
        Initialize the multi-task progress reporter.
        
        Args:
            tasks: Dictionary of task names and their relative weights
            description: Description of the overall operation
            callback: Optional callback function to be called with progress updates
            console: Whether to output progress to console
        """
        self.tasks = {}
        self.description = description
        self.callback = callback
        self.console = console
        self.lock = Lock()
        
        # Normalize weights to sum to 1.0
        total_weight = sum(tasks.values())
        for task_name, weight in tasks.items():
            self.tasks[task_name] = {
                'weight': weight / total_weight if total_weight > 0 else 0,
                'progress': 0.0,
                'status': 'Pending'
            }
            
        # Create main reporter
        self.reporter = ProgressReporter(100, description, callback, console)
        logger.debug(f"Multi-task progress reporter initialized with {len(tasks)} tasks")
        
    def update_task(self, task_name: str, progress: float, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Update progress for a specific task.
        
        Args:
            task_name: Name of the task to update
            progress: Progress value (0-100)
            status: Optional status message
            
        Returns:
            Dict: Overall progress information
        """
        with self.lock:
            if task_name not in self.tasks:
                logger.warning(f"Attempt to update unknown task: {task_name}")
                return self._get_overall_progress()
                
            # Update this task's progress
            task = self.tasks[task_name]
            old_progress = task['progress']
            task['progress'] = min(100.0, max(0.0, progress))
            
            # Update status if provided
            if status:
                task['status'] = status
                
            # Calculate progress delta for overall progress
            progress_delta = (task['progress'] - old_progress) * task['weight']
            overall_step_delta = int(progress_delta)
            
            # Update overall progress
            if overall_step_delta > 0:
                self.reporter.update(overall_step_delta, self._get_status_message())
                
            return self._get_overall_progress()
            
    def complete_task(self, task_name: str, status: str = "Completed") -> Dict[str, Any]:
        """
        Mark a specific task as complete.
        
        Args:
            task_name: Name of the task to mark complete
            status: Status message for the completed task
            
        Returns:
            Dict: Overall progress information
        """
        return self.update_task(task_name, 100.0, status)
        
    def complete_all(self, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Mark all tasks as complete.
        
        Args:
            message: Optional completion message
            
        Returns:
            Dict: Final progress information
        """
        with self.lock:
            # Complete each task
            for task_name in self.tasks:
                self.tasks[task_name]['progress'] = 100.0
                self.tasks[task_name]['status'] = "Completed"
                
            # Complete overall progress
            return self.reporter.complete(message or f"{self.description}: All tasks completed")
            
    def _get_overall_progress(self) -> Dict[str, Any]:
        """
        Calculate the current overall progress.
        
        Returns:
            Dict: Overall progress information
        """
        # Calculate weighted progress
        weighted_sum = sum(task['progress'] * task['weight'] for task in self.tasks.values())
        
        # Add task-specific information to the overall progress
        progress_info = {
            'overall_percentage': weighted_sum,
            'tasks': {name: {
                'progress': task['progress'], 
                'weight': task['weight'],
                'status': task['status']
            } for name, task in self.tasks.items()}
        }
        
        return progress_info
        
    def _get_status_message(self) -> str:
        """
        Create a status message based on in-progress tasks.
        
        Returns:
            str: Status message
        """
        active_tasks = [name for name, task in self.tasks.items() 
                       if 0 < task['progress'] < 100]
        
        if not active_tasks:
            return f"{self.description}"
        
        if len(active_tasks) <= 2:
            task_str = " and ".join(active_tasks)
            return f"{self.description}: Processing {task_str}"
        
        return f"{self.description}: Processing {len(active_tasks)} tasks"