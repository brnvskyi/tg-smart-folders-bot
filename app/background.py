import asyncio
from typing import Dict, Callable, Awaitable, Optional, Any
from datetime import datetime
import time
from app.logger import setup_logger
from app.config import settings
from app.analytics import analytics

logger = setup_logger(__name__)

class BackgroundTaskManager:
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.results: Dict[str, Any] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.start_times: Dict[str, float] = {}
    
    async def add_task(
        self,
        task_id: str,
        coro: Awaitable,
        callback: Optional[Callable] = None,
        timeout: Optional[int] = None
    ):
        """Add new background task"""
        if not settings.BACKGROUND_TASKS_ENABLED:
            # Execute synchronously if background tasks are disabled
            result = await coro
            if callback:
                callback(result)
            return
        
        if len(self.tasks) >= settings.MAX_BACKGROUND_TASKS:
            # Remove completed tasks
            self._cleanup_tasks()
            if len(self.tasks) >= settings.MAX_BACKGROUND_TASKS:
                raise RuntimeError("Maximum number of background tasks reached")
        
        # Create task wrapper
        async def task_wrapper():
            start_time = time.time()
            self.start_times[task_id] = start_time
            
            try:
                if timeout:
                    result = await asyncio.wait_for(coro, timeout)
                else:
                    result = await coro
                
                self.results[task_id] = result
                if callback:
                    callback(result)
                
                # Track performance
                duration = time.time() - start_time
                analytics.track_performance(f"background_task_{task_id}", duration)
                
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id} timed out after {timeout} seconds")
                analytics.track_error(f"task_timeout_{task_id}")
            except Exception as e:
                logger.error(f"Error in background task {task_id}: {e}")
                analytics.track_error(f"task_error_{task_id}")
            finally:
                # Cleanup
                self._remove_task(task_id)
        
        # Create and start task
        task = asyncio.create_task(task_wrapper())
        self.tasks[task_id] = task
        self.callbacks[task_id] = callback
        
        logger.info(f"Started background task {task_id}")
    
    def get_task_status(self, task_id: str) -> dict:
        """Get status of background task"""
        if task_id not in self.tasks:
            return {
                'status': 'not_found',
                'result': None,
                'duration': None
            }
        
        task = self.tasks[task_id]
        start_time = self.start_times.get(task_id)
        current_time = time.time()
        
        if task.done():
            status = 'completed' if not task.exception() else 'failed'
            result = self.results.get(task_id)
        else:
            status = 'running'
            result = None
        
        return {
            'status': status,
            'result': result,
            'duration': current_time - start_time if start_time else None
        }
    
    def cancel_task(self, task_id: str):
        """Cancel background task"""
        if task_id in self.tasks:
            self.tasks[task_id].cancel()
            self._remove_task(task_id)
            logger.info(f"Cancelled task {task_id}")
    
    def _remove_task(self, task_id: str):
        """Remove task and its associated data"""
        self.tasks.pop(task_id, None)
        self.results.pop(task_id, None)
        self.callbacks.pop(task_id, None)
        self.start_times.pop(task_id, None)
    
    def _cleanup_tasks(self):
        """Remove completed tasks"""
        completed_tasks = [
            task_id for task_id, task in self.tasks.items()
            if task.done()
        ]
        for task_id in completed_tasks:
            self._remove_task(task_id)
    
    async def stop_all(self):
        """Stop all background tasks"""
        for task_id in list(self.tasks.keys()):
            self.cancel_task(task_id)
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        
        self.tasks.clear()
        self.results.clear()
        self.callbacks.clear()
        self.start_times.clear()
        
        logger.info("All background tasks stopped")

# Create global background task manager instance
task_manager = BackgroundTaskManager() 