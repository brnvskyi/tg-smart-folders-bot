import asyncio
from typing import Optional, Dict
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

class MessageQueue:
    def __init__(self):
        self.queues: Dict[int, asyncio.Queue] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self._stop_events: Dict[int, asyncio.Event] = {}
    
    def get_queue(self, channel_id: int) -> asyncio.Queue:
        """Get or create queue for channel"""
        if channel_id not in self.queues:
            self.queues[channel_id] = asyncio.Queue(maxsize=settings.QUEUE_MAX_SIZE)
            self._stop_events[channel_id] = asyncio.Event()
        return self.queues[channel_id]
    
    async def add_message(self, channel_id: int, message):
        """Add message to queue with timeout"""
        try:
            queue = self.get_queue(channel_id)
            await asyncio.wait_for(queue.put(message), timeout=settings.QUEUE_TIMEOUT)
            logger.debug(f"Message added to queue for channel {channel_id}")
        except asyncio.TimeoutError:
            logger.warning(f"Queue is full for channel {channel_id}, message dropped")
        except Exception as e:
            logger.error(f"Error adding message to queue: {e}")
    
    async def process_messages(self, channel_id: int, handler):
        """Process messages from queue"""
        queue = self.get_queue(channel_id)
        stop_event = self._stop_events[channel_id]
        
        while not stop_event.is_set():
            try:
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                finally:
                    queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)
    
    def start_processing(self, channel_id: int, handler):
        """Start message processing for channel"""
        if channel_id in self.tasks and not self.tasks[channel_id].done():
            return
        
        self.tasks[channel_id] = asyncio.create_task(
            self.process_messages(channel_id, handler)
        )
        logger.info(f"Started message processing for channel {channel_id}")
    
    def stop_processing(self, channel_id: int):
        """Stop message processing for channel"""
        if channel_id in self._stop_events:
            self._stop_events[channel_id].set()
        
        if channel_id in self.tasks:
            self.tasks[channel_id].cancel()
            del self.tasks[channel_id]
        
        if channel_id in self.queues:
            del self.queues[channel_id]
            
        logger.info(f"Stopped message processing for channel {channel_id}")
    
    async def stop_all(self):
        """Stop all message processing"""
        for channel_id in list(self.tasks.keys()):
            self.stop_processing(channel_id)
        
        # Wait for all tasks to complete
        remaining_tasks = [t for t in self.tasks.values() if not t.done()]
        if remaining_tasks:
            await asyncio.gather(*remaining_tasks, return_exceptions=True)
        
        self.queues.clear()
        self.tasks.clear()
        self._stop_events.clear()
        logger.info("Stopped all message processing") 