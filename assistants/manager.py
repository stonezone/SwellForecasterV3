"""
Assistant Manager for SwellForecaster V3.

This module handles the creation, persistence, and management of OpenAI Assistants.
"""

import json
import os
from typing import Dict, Optional
from openai import OpenAI
from logging_config import get_logger

logger = get_logger(__name__)


class AssistantManager:
    """
    Manages OpenAI Assistants including creation, persistence, and updates.
    """
    
    def __init__(self, client: OpenAI, config):
        """
        Initialize the AssistantManager.
        
        Args:
            client: OpenAI client instance
            config: Configuration object
        """
        self.client = client
        self.config = config
        self.assistants: Dict[str, str] = {}  # name -> assistant_id mapping
        
        # Load persistence settings
        self.save_assistant_ids = config.getboolean('assistants', 'save_assistant_ids')
        self.assistants_file = config.get('assistants', 'assistants_file')
        
        # Load or create assistants
        self._initialize_assistants()
    
    def _initialize_assistants(self):
        """Initialize assistants by loading from file or creating new ones."""
        if self.save_assistant_ids and os.path.exists(self.assistants_file):
            self._load_assistants()
        else:
            self._create_assistants()
            if self.save_assistant_ids:
                self._save_assistants()
    
    def _load_prompts(self):
        """Load prompts from JSON file."""
        prompts_file = self.config.get('prompts', 'prompts_file', fallback='./config/prompts.json')
        try:
            with open(prompts_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading prompts file: {e}")
            return {}
    
    def _load_assistants(self):
        """Load assistants from persistence file."""
        try:
            with open(self.assistants_file, 'r') as f:
                self.assistants = json.load(f)
            
            # Verify assistants still exist
            for name, assistant_id in self.assistants.items():
                try:
                    self.client.beta.assistants.retrieve(assistant_id)
                    logger.info(f"Loaded assistant '{name}' with ID: {assistant_id}")
                except Exception as e:
                    logger.warning(f"Assistant '{name}' not found, will recreate: {e}")
                    del self.assistants[name]
            
            # Create any missing assistants
            if len(self.assistants) < 3:  # Should have forecaster, critic, and data_assessment
                self._create_missing_assistants()
                self._save_assistants()
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Error loading assistants file: {e}")
            self._create_assistants()
            self._save_assistants()
    
    def _create_assistants(self):
        """Create all required assistants."""
        logger.info("Creating new assistants")
        
        # Load prompts from JSON file
        prompts = self._load_prompts()
        
        # Create forecaster assistant
        self.assistants['forecaster'] = self._create_assistant(
            name="Surf Forecaster",
            instructions=prompts.get('forecaster_prompt', self.config.get('prompts', 'forecaster_prompt')),
            model=self.config.get('openai', 'forecasting_model'),
            tools=[{"type": "file_search"}]
        )
        
        # Create critic assistant
        self.assistants['critic'] = self._create_assistant(
            name="Forecast Critic",
            instructions=prompts.get('critic_prompt', self.config.get('prompts', 'critic_prompt')),
            model=self.config.get('openai', 'forecasting_model'),
            tools=[]  # Critic doesn't need file access
        )
        
        # Create data assessment assistant
        self.assistants['data_assessment'] = self._create_assistant(
            name="Data Assessment",
            instructions=prompts.get('data_assessment_prompt', self.config.get('prompts', 'data_assessment_prompt')),
            model=self.config.get('openai', 'support_model'),
            tools=[{"type": "file_search"}]
        )
    
    def _create_missing_assistants(self):
        """Create only the missing assistants."""
        # Load prompts from JSON file
        prompts = self._load_prompts()
        
        required_assistants = {
            'forecaster': {
                'name': "Surf Forecaster",
                'instructions': prompts.get('forecaster_prompt', self.config.get('prompts', 'forecaster_prompt')),
                'model': self.config.get('openai', 'forecasting_model'),
                'tools': [{"type": "file_search"}]
            },
            'critic': {
                'name': "Forecast Critic",
                'instructions': prompts.get('critic_prompt', self.config.get('prompts', 'critic_prompt')),
                'model': self.config.get('openai', 'forecasting_model'),
                'tools': []
            },
            'data_assessment': {
                'name': "Data Assessment",
                'instructions': prompts.get('data_assessment_prompt', self.config.get('prompts', 'data_assessment_prompt')),
                'model': self.config.get('openai', 'support_model'),
                'tools': [{"type": "file_search"}]
            }
        }
        
        for key, specs in required_assistants.items():
            if key not in self.assistants:
                self.assistants[key] = self._create_assistant(**specs)
    
    def _create_assistant(self, name: str, instructions: str, model: str, tools: list) -> str:
        """
        Create a single assistant.
        
        Args:
            name: Assistant name
            instructions: Assistant instructions/prompt
            model: Model to use
            tools: List of tools to enable
            
        Returns:
            Assistant ID
        """
        try:
            assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                model=model,
                tools=tools
            )
            logger.info(f"Created assistant '{name}' with ID: {assistant.id}")
            return assistant.id
        except Exception as e:
            logger.error(f"Error creating assistant '{name}': {e}")
            raise
    
    def _save_assistants(self):
        """Save assistant IDs to file."""
        try:
            os.makedirs(os.path.dirname(self.assistants_file), exist_ok=True)
            with open(self.assistants_file, 'w') as f:
                json.dump(self.assistants, f, indent=2)
            logger.info(f"Saved {len(self.assistants)} assistants to {self.assistants_file}")
        except Exception as e:
            logger.error(f"Error saving assistants: {e}")
    
    def get_assistant(self, name: str) -> Optional[str]:
        """
        Get assistant ID by name.
        
        Args:
            name: Assistant name
            
        Returns:
            Assistant ID or None if not found
        """
        return self.assistants.get(name)
    
    def update_assistant(self, name: str, **kwargs):
        """
        Update an assistant's configuration.
        
        Args:
            name: Assistant name
            **kwargs: Fields to update (instructions, model, etc.)
        """
        assistant_id = self.get_assistant(name)
        if not assistant_id:
            logger.error(f"Assistant '{name}' not found")
            return
        
        try:
            self.client.beta.assistants.update(
                assistant_id,
                **kwargs
            )
            logger.info(f"Updated assistant '{name}'")
        except Exception as e:
            logger.error(f"Error updating assistant '{name}': {e}")
    
    def delete_all_assistants(self):
        """Delete all managed assistants (for cleanup)."""
        for name, assistant_id in self.assistants.items():
            try:
                self.client.beta.assistants.delete(assistant_id)
                logger.info(f"Deleted assistant '{name}'")
            except Exception as e:
                logger.warning(f"Error deleting assistant '{name}': {e}")
        
        self.assistants.clear()
        if self.save_assistant_ids and os.path.exists(self.assistants_file):
            os.remove(self.assistants_file)