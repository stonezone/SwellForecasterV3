"""
Forecast Engine for SwellForecaster V3.

This module implements the main forecasting workflow using the Forecaster
and Critic assistants with refinement cycles.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from assistants import AssistantManager, ThreadManager, FileManager
from agents.file_adapter import FileAdapter
from logging_config import get_logger

logger = get_logger(__name__)


class ForecastEngine:
    """
    Manages the forecast generation workflow with critic refinement.
    """
    
    def __init__(self, assistant_manager: AssistantManager,
                 thread_manager: ThreadManager,
                 file_manager: FileManager,
                 config):
        """
        Initialize the ForecastEngine.
        
        Args:
            assistant_manager: AssistantManager instance
            thread_manager: ThreadManager instance  
            file_manager: FileManager instance
            config: Configuration object
        """
        self.assistant_manager = assistant_manager
        self.thread_manager = thread_manager
        self.file_manager = file_manager
        self.config = config
        
        # Get assistant IDs
        self.forecaster_id = assistant_manager.get_assistant('forecaster')
        self.critic_id = assistant_manager.get_assistant('critic')
        
        if not self.forecaster_id or not self.critic_id:
            raise ValueError("Forecaster or Critic assistant not found")
        
        # Get refinement cycles from config
        self.refinement_cycles = config.getint('general', 'refinement_cycles', fallback=2)
    
    def generate_forecast(self, shore: str, file_ids: List[str],
                         assessment_report: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a forecast for a specific shore with critic refinement.
        
        Args:
            shore: Shore name (North Shore or South Shore)
            file_ids: List of file IDs with data
            assessment_report: Optional data assessment report
            
        Returns:
            Dictionary containing final forecast and metadata
        """
        logger.info(f"Starting forecast generation for {shore}")
        
        # Create forecast thread
        forecast_thread_id = self.thread_manager.create_thread(
            name=f"forecast_{shore.replace(' ', '_').lower()}"
        )
        
        try:
            # Build initial forecast prompt
            prompt = self._build_forecast_prompt(shore, assessment_report)
            
            # Add message with data files
            self.thread_manager.add_message(
                thread_id=forecast_thread_id,
                content=prompt,
                file_ids=file_ids
            )
            
            # Generate initial forecast
            logger.info(f"Generating initial forecast for {shore}")
            run_id = self.thread_manager.run_assistant(
                thread_id=forecast_thread_id,
                assistant_id=self.forecaster_id
            )
            
            self.thread_manager.wait_for_run(forecast_thread_id, run_id)
            initial_forecast = self.thread_manager.get_last_assistant_message(forecast_thread_id)
            
            # Refinement cycles
            current_forecast = initial_forecast
            refinement_history = []
            
            for cycle in range(self.refinement_cycles):
                logger.info(f"Starting refinement cycle {cycle + 1}/{self.refinement_cycles}")
                
                # Get critique
                critique = self._get_critique(current_forecast, shore)
                refinement_history.append({
                    'cycle': cycle + 1,
                    'critique': critique
                })
                
                # Refine forecast based on critique
                refined_forecast = self._refine_forecast(
                    forecast_thread_id,
                    current_forecast,
                    critique
                )
                
                refinement_history[-1]['refined_forecast'] = refined_forecast
                current_forecast = refined_forecast
            
            # Prepare final result
            result = {
                'shore': shore,
                'initial_forecast': initial_forecast,
                'final_forecast': current_forecast,
                'refinement_history': refinement_history,
                'refinement_cycles': self.refinement_cycles,
                'timestamp': datetime.utcnow().isoformat(),
                'data_files': len(file_ids)
            }
            
            logger.info(f"Forecast generation complete for {shore}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating forecast for {shore}: {e}")
            raise
        finally:
            # Clean up thread
            self.thread_manager.delete_thread(forecast_thread_id)
    
    def _build_forecast_prompt(self, shore: str, assessment_report: Optional[str]) -> str:
        """
        Build the initial forecast prompt.
        
        Args:
            shore: Shore name
            assessment_report: Optional data assessment report
            
        Returns:
            Formatted prompt string
        """
        # Get the base prompt from config
        base_prompt = self.config.get('prompts', 'forecaster_prompt')
        formatted_prompt = base_prompt.format(shore=shore)
        
        # Add assessment report if available
        if assessment_report:
            formatted_prompt += f"""
            
            Data Assessment Report:
            {assessment_report}
            
            Please consider the data quality issues and recommendations mentioned in the assessment report when creating your forecast.
            """
        
        # Add specific instructions for this run
        formatted_prompt += f"""
        
        Please generate a detailed 10-day surf forecast for {shore} starting from today.
        Include all required elements as specified in your instructions.
        Be specific about swell heights, directions, periods, and local conditions.
        """
        
        return formatted_prompt
    
    def _get_critique(self, forecast: str, shore: str) -> str:
        """
        Get a critique of the forecast from the Critic assistant.
        
        Args:
            forecast: The forecast to critique
            shore: Shore name for context
            
        Returns:
            Critique text
        """
        # Create critique thread
        critique_thread_id = self.thread_manager.create_thread(
            name=f"critique_{shore.replace(' ', '_').lower()}"
        )
        
        try:
            # Build critique prompt
            critique_prompt = f"""
            Please review this surf forecast for {shore} critically:
            
            {forecast}
            
            Focus your critique on:
            1. Meteorological accuracy and plausibility
            2. Internal consistency of predictions
            3. Appropriate consideration of local effects
            4. Clarity and completeness of information
            5. Any missing or questionable elements
            
            Provide specific, actionable feedback for improvement.
            """
            
            # Add message
            self.thread_manager.add_message(
                thread_id=critique_thread_id,
                content=critique_prompt
            )
            
            # Run critic
            run_id = self.thread_manager.run_assistant(
                thread_id=critique_thread_id,
                assistant_id=self.critic_id
            )
            
            self.thread_manager.wait_for_run(critique_thread_id, run_id)
            critique = self.thread_manager.get_last_assistant_message(critique_thread_id)
            
            return critique
            
        finally:
            # Clean up thread
            self.thread_manager.delete_thread(critique_thread_id)
    
    def _refine_forecast(self, forecast_thread_id: str, 
                        current_forecast: str, critique: str) -> str:
        """
        Refine the forecast based on critique.
        
        Args:
            forecast_thread_id: Thread ID for the forecast
            current_forecast: Current forecast text
            critique: Critique to address
            
        Returns:
            Refined forecast text
        """
        # Build refinement prompt
        refinement_prompt = self.config.get('prompts', 'refinement_prompt')
        
        # Add the critique and request refinement
        message = f"""
        {refinement_prompt}
        
        Original Forecast:
        {current_forecast}
        
        Critique:
        {critique}
        
        Please provide your refined forecast, addressing the critique while maintaining all essential forecast elements.
        """
        
        # Add message to forecast thread
        self.thread_manager.add_message(
            thread_id=forecast_thread_id,
            content=message
        )
        
        # Run forecaster for refinement
        run_id = self.thread_manager.run_assistant(
            thread_id=forecast_thread_id,
            assistant_id=self.forecaster_id
        )
        
        self.thread_manager.wait_for_run(forecast_thread_id, run_id)
        refined_forecast = self.thread_manager.get_last_assistant_message(forecast_thread_id)
        
        return refined_forecast
    
    def save_forecast(self, forecast_result: Dict[str, Any], output_dir: str) -> str:
        """
        Save the forecast result to disk.
        
        Args:
            forecast_result: Complete forecast result dictionary
            output_dir: Directory to save the forecast
            
        Returns:
            Path to saved forecast file
        """
        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        shore_slug = forecast_result['shore'].replace(' ', '_').lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{shore_slug}_forecast_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Save forecast
        with open(filepath, 'w') as f:
            json.dump(forecast_result, f, indent=2)
        
        logger.info(f"Saved forecast to {filepath}")
        return filepath
    
    def format_forecast_output(self, forecast_result: Dict[str, Any]) -> str:
        """
        Format the forecast for display/output.
        
        Args:
            forecast_result: Complete forecast result
            
        Returns:
            Formatted forecast text
        """
        # TODO: Implement markdown/HTML formatting based on template
        # For now, return the final forecast
        return forecast_result['final_forecast']