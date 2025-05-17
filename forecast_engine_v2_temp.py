"""
Forecast Engine V2 for SwellForecaster V3.

Enhanced to create single unified forecast in Pat Caldwell style.
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
    V2: Creates single unified forecast covering all shores.
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
    
    def generate_unified_forecast(self, file_ids: List[str],
                                 assessment_report: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a unified forecast covering all shores with critic refinement.
        
        Args:
            file_ids: List of file IDs with data
            assessment_report: Optional data assessment report
            
        Returns:
            Dictionary containing final forecast and metadata
        """
        logger.info("Starting unified forecast generation")
        
        # Create forecast thread
        forecast_thread_id = self.thread_manager.create_thread(
            name="unified_hawaii_forecast"
        )
        
        try:
            # Build initial forecast prompt
            prompt = self._build_unified_forecast_prompt(assessment_report)
            
            # Add message with data files
            self.thread_manager.add_message(
                thread_id=forecast_thread_id,
                content=prompt,
                file_ids=file_ids
            )
            
            # Generate initial forecast
            logger.info("Generating initial unified forecast")
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
                critique = self._get_critique(current_forecast)
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
                'type': 'unified',
                'initial_forecast': initial_forecast,
                'final_forecast': current_forecast,
                'refinement_history': refinement_history,
                'refinement_cycles': self.refinement_cycles,
                'timestamp': datetime.utcnow().isoformat(),
                'data_files': len(file_ids)
            }
            
            logger.info("Unified forecast generation complete")
            return result
            
        except Exception as e:
            logger.error(f"Error generating unified forecast: {e}")
            raise
        finally:
            # Clean up thread
            self.thread_manager.delete_thread(forecast_thread_id)
    
    def _build_unified_forecast_prompt(self, assessment_report: Optional[str]) -> str:
        """
        Build the initial unified forecast prompt in Pat Caldwell style.
        
        Args:
            assessment_report: Optional data assessment report
            
        Returns:
            Formatted prompt string
        """
        # Get the base prompt from config
        base_prompt = """You are Pat Caldwell, Hawaii's premier surf forecaster. Create a unified surf forecast covering all Hawaiian shores.

Your forecast should include:

1. OPENING GREETING & OVERVIEW
- Start with "Aloha" and date
- Brief overview of current patterns affecting Hawaii
- Key takeaways for the forecast period

2. NOWCAST - Current Conditions
- Real-time buoy observations
- Swell heights, periods, directions (Hawaiian scale)
- Wind conditions at key locations
- Current surf heights by shore

3. SYNOPTIC PATTERN ANALYSIS
- Active storm systems in North/South Pacific
- Position relative to Hawaii (distance, bearing)
- Storm characteristics (central pressure, winds, seas)
- Expected evolution and track

4. NORTH PACIFIC ANALYSIS (North Shore focus)
- Individual storm systems by position
- Fetch analysis (length, width, duration, intensity)
- Expected swell generation
- Travel time and arrival calculations
- Quality assessment based on conditions

5. SOUTH PACIFIC ANALYSIS (South Shore focus)
- Southern Hemisphere storm activity
- Swell windows and corridors
- Long-period swell potential
- Seasonal patterns

6. SWELL EVENT DETAILS
- For each significant swell:
  * Origin and generation area
  * Expected arrival time
  * Peak timing and duration
  * Heights by shore (Hawaiian scale)
  * Period and direction
  * Quality factors

7. DAY-BY-DAY FORECAST (10 days)
Format: Date | N Shore | S Shore | E Shore | W Shore | Wind | Special Notes

8. WIND ANALYSIS
- Trade wind patterns and disruptions
- Kona wind potential
- Local sea breezes
- Impact on surf quality by break

9. SPECIAL CONDITIONS
- Wing foiling windows (14-29 mph)
- Tow-in conditions
- Hazardous conditions warnings
- Tide impacts on specific breaks

10. CONFIDENCE LEVELS
- Near-term (1-3 days): Usually high
- Mid-range (4-7 days): Moderate
- Extended (8-10 days): Lower, trend-based

Use Hawaiian scale throughout. Reference specific breaks when relevant.
Be technical but accessible. Include meteorological reasoning."""
        
        # Add assessment report if available
        if assessment_report:
            base_prompt += f"""
            
Data Assessment Report:
{assessment_report}

Please consider the data quality issues and recommendations mentioned above."""
        
        # Add specific instructions for this run
        base_prompt += """

Create a comprehensive unified forecast covering all Hawaiian shores.
Be specific about timing, heights, and conditions.
Use your expertise to resolve conflicts between data sources.
Include both current conditions (NOWCAST) and extended forecast."""
        
        return base_prompt
    
    def _get_critique(self, forecast: str) -> str:
        """
        Get a critique of the forecast from the Critic assistant.
        
        Args:
            forecast: The forecast to critique
            
        Returns:
            Critique text
        """
        # Create critique thread
        critique_thread_id = self.thread_manager.create_thread(
            name="forecast_critique"
        )
        
        try:
            # Build critique prompt
            critique_prompt = f"""Please review this unified Hawaii surf forecast critically:
            
{forecast}

Focus your critique on:
1. Meteorological accuracy and storm tracking
2. Swell propagation physics and timing
3. Local effects and island shadowing
4. Internal consistency across all shores
5. Appropriate use of Hawaiian scale
6. Coverage of all important elements
7. Pat Caldwell style adherence

Provide specific, actionable feedback for improvement."""
            
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
        refinement_prompt = """Based on the critique below, please refine your forecast.
Maintain the unified format covering all shores.
Address the specific issues raised while keeping all essential elements.

Original Forecast:
[Already in thread context]

Critique:"""
        
        # Add the critique and request refinement
        message = f"""{refinement_prompt}
{critique}

Please provide your refined unified forecast addressing these points."""
        
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
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON with full details
        json_filename = f"hawaii_unified_forecast_{timestamp}.json"
        json_filepath = os.path.join(output_dir, json_filename)
        
        with open(json_filepath, 'w') as f:
            json.dump(forecast_result, f, indent=2)
        
        # Save markdown version
        md_filename = f"hawaii_unified_forecast_{timestamp}.md"
        md_filepath = os.path.join(output_dir, md_filename)
        
        with open(md_filepath, 'w') as f:
            f.write(forecast_result['final_forecast'])
        
        logger.info(f"Saved forecast to {json_filepath} and {md_filepath}")
        return json_filepath
    
    def format_forecast_output(self, forecast_result: Dict[str, Any]) -> str:
        """
        Format the forecast for display/output.
        
        Args:
            forecast_result: Complete forecast result
            
        Returns:
            Formatted forecast text
        """
        return forecast_result['final_forecast']