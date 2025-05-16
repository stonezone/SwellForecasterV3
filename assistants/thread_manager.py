"""
Thread Manager for SwellForecaster V3.

This module handles thread creation, message management, and run execution
for the OpenAI Assistants API.
"""

import time
from typing import List, Optional, Dict, Any
from openai import OpenAI
from logging_config import get_logger

logger = get_logger(__name__)


class ThreadManager:
    """
    Manages threads, messages, and runs for OpenAI Assistants.
    """
    
    def __init__(self, client: OpenAI):
        """
        Initialize the ThreadManager.
        
        Args:
            client: OpenAI client instance
        """
        self.client = client
        self.active_threads: Dict[str, str] = {}  # thread_name -> thread_id
    
    def create_thread(self, name: Optional[str] = None) -> str:
        """
        Create a new thread.
        
        Args:
            name: Optional name for tracking the thread
            
        Returns:
            Thread ID
        """
        try:
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            
            if name:
                self.active_threads[name] = thread_id
                
            logger.info(f"Created thread{' ' + name if name else ''}: {thread_id}")
            return thread_id
        except Exception as e:
            logger.error(f"Error creating thread: {e}")
            raise
    
    def add_message(self, thread_id: str, content: str, role: str = "user", 
                   file_ids: Optional[List[str]] = None):
        """
        Add a message to a thread.
        
        Args:
            thread_id: Thread ID
            content: Message content
            role: Message role (user or assistant)
            file_ids: Optional list of file IDs to attach
            
        Returns:
            Message object
        """
        try:
            message_data = {
                "thread_id": thread_id,
                "role": role,
                "content": content
            }
            
            if file_ids:
                message_data["file_ids"] = file_ids
            
            message = self.client.beta.threads.messages.create(**message_data)
            logger.debug(f"Added message to thread {thread_id}")
            return message
        except Exception as e:
            logger.error(f"Error adding message to thread: {e}")
            raise
    
    def run_assistant(self, thread_id: str, assistant_id: str,
                     instructions: Optional[str] = None) -> str:
        """
        Run an assistant on a thread.
        
        Args:
            thread_id: Thread ID
            assistant_id: Assistant ID
            instructions: Optional additional instructions
            
        Returns:
            Run ID
        """
        try:
            run_data = {
                "thread_id": thread_id,
                "assistant_id": assistant_id
            }
            
            if instructions:
                run_data["instructions"] = instructions
            
            run = self.client.beta.threads.runs.create(**run_data)
            logger.info(f"Started run {run.id} on thread {thread_id}")
            return run.id
        except Exception as e:
            logger.error(f"Error starting run: {e}")
            raise
    
    def wait_for_run(self, thread_id: str, run_id: str, 
                    timeout: int = 300, poll_interval: int = 5) -> Any:
        """
        Wait for a run to complete.
        
        Args:
            thread_id: Thread ID
            run_id: Run ID
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Completed run object
            
        Raises:
            TimeoutError: If run doesn't complete within timeout
            Exception: If run fails
        """
        start_time = time.time()
        
        while True:
            try:
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                if run.status == 'completed':
                    logger.info(f"Run {run_id} completed successfully")
                    return run
                elif run.status in ['failed', 'cancelled', 'expired']:
                    error_msg = f"Run {run_id} {run.status}"
                    if run.last_error:
                        error_msg += f": {run.last_error}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                # Check timeout
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Run {run_id} timed out after {timeout} seconds")
                
                logger.debug(f"Run {run_id} status: {run.status}")
                time.sleep(poll_interval)
                
            except Exception as e:
                if not isinstance(e, (TimeoutError, Exception)):
                    logger.error(f"Error checking run status: {e}")
                raise
    
    def get_messages(self, thread_id: str, limit: int = 20,
                    order: str = "desc") -> List[Any]:
        """
        Get messages from a thread.
        
        Args:
            thread_id: Thread ID
            limit: Maximum number of messages to retrieve
            order: Sort order (asc or desc)
            
        Returns:
            List of message objects
        """
        try:
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                limit=limit,
                order=order
            )
            return messages.data
        except Exception as e:
            logger.error(f"Error retrieving messages: {e}")
            raise
    
    def get_last_assistant_message(self, thread_id: str) -> Optional[str]:
        """
        Get the most recent assistant message from a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Message content or None if no assistant message found
        """
        messages = self.get_messages(thread_id, order="desc")
        
        for message in messages:
            if message.role == "assistant":
                # Extract text content from message
                content_text = ""
                for content in message.content:
                    if content.type == "text":
                        content_text += content.text.value
                return content_text
        
        return None
    
    def delete_thread(self, thread_id: str):
        """
        Delete a thread.
        
        Args:
            thread_id: Thread ID to delete
        """
        try:
            self.client.beta.threads.delete(thread_id)
            
            # Remove from active threads tracking
            for name, tid in list(self.active_threads.items()):
                if tid == thread_id:
                    del self.active_threads[name]
            
            logger.info(f"Deleted thread {thread_id}")
        except Exception as e:
            logger.warning(f"Error deleting thread {thread_id}: {e}")
    
    def cleanup_threads(self):
        """Clean up all tracked threads."""
        for name, thread_id in list(self.active_threads.items()):
            self.delete_thread(thread_id)
        
        self.active_threads.clear()
        logger.info("Cleaned up all threads")