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
# For PDF generation
try:
    from weasyprint import HTML
    has_pdf_support = True
except ImportError:
    has_pdf_support = False
    logger = get_logger(__name__)
    logger.warning("WeasyPrint not installed. PDF generation will be disabled.")

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
        
        # Load enhanced prompts if available
        self.enhanced_prompts = self._load_enhanced_prompts()
    
    def _load_enhanced_prompts(self) -> Dict[str, Any]:
        """Load enhanced prompts from prompts.json.example if available"""
        try:
            prompts_file = os.path.join(
                os.path.dirname(__file__), 
                'config', 
                'prompts.json.example'
            )
            if os.path.exists(prompts_file):
                with open(prompts_file, 'r') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logger.warning(f"Could not load enhanced prompts: {e}")
            return {}
    
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
            prompt = self._build_enhanced_forecast_prompt(shore, assessment_report)
            
            # Add message with data files - batch if more than 10
            # API limit is 10 attachments per message
            if len(file_ids) <= 10:
                self.thread_manager.add_message(
                    thread_id=forecast_thread_id,
                    content=prompt,
                    file_ids=file_ids
                )
            else:
                # Send files in batches of 10
                logger.info(f"Batching {len(file_ids)} files into multiple messages")
                
                # First message with initial prompt and first 10 files
                self.thread_manager.add_message(
                    thread_id=forecast_thread_id,
                    content=prompt,
                    file_ids=file_ids[:10]
                )
                
                # Subsequent messages with remaining files
                for i in range(10, len(file_ids), 10):
                    batch = file_ids[i:i+10]
                    self.thread_manager.add_message(
                        thread_id=forecast_thread_id,
                        content=f"Additional data files (batch {i//10 + 1}):",
                        file_ids=batch
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
    
    def _build_enhanced_forecast_prompt(self, shore: str, assessment_report: Optional[str]) -> str:
        """
        Build an enhanced forecast prompt using prompts.json.example structure.
        
        Args:
            shore: Shore name
            assessment_report: Optional data assessment report
            
        Returns:
            Formatted prompt string
        """
        # Use enhanced prompts if available
        if self.enhanced_prompts and 'forecast' in self.enhanced_prompts:
            forecast_config = self.enhanced_prompts['forecast']
            
            # Get base intro
            prompt = forecast_config.get('intro', '')
            
            # Add shore-specific emphasis
            emphasis = ""
            if 'North' in shore and 'north' in forecast_config.get('emphasis', {}):
                emphasis = forecast_config['emphasis']['north']
            elif 'South' in shore and 'south' in forecast_config.get('emphasis', {}):
                emphasis = forecast_config['emphasis']['south']
            else:
                emphasis = forecast_config.get('emphasis', {}).get('both', '')
            
            # Add data sources summary
            data_sources = forecast_config.get('data_sources', '')
            
            # Add structure guidelines
            structure = forecast_config.get('structure', {})
            structure_text = f"""
            
{structure.get('intro', '')}

{structure.get('nowcast', '')}

{structure.get('north_shore_priority' if 'North' in shore else 'south_shore_priority', structure.get('balanced', ''))}

{structure.get('wingfoiling', '')}

{structure.get('conclusion', '')}

{structure.get('style', '')}
            """
            
            # Compile full prompt
            prompt = f"""{prompt}

{emphasis}

{data_sources}

{structure_text}

Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Shore: {shore}
"""
        else:
            # Fall back to original prompt
            base_prompt = self.config.get('prompts', 'forecaster_prompt')
            prompt = base_prompt.format(shore=shore)
        
        # Add assessment report if available
        if assessment_report:
            prompt += f"""
            
Data Assessment Report:
{assessment_report}

Please consider the data quality issues and recommendations mentioned in the assessment report when creating your forecast.
            """
        
        return prompt
    
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
        Save the forecast result to disk in multiple formats.
        
        Args:
            forecast_result: Complete forecast result dictionary
            output_dir: Directory to save the forecast
            
        Returns:
            Path to saved forecast file
        """
        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename base
        shore_slug = forecast_result['shore'].replace(' ', '_').lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{shore_slug}_forecast_{timestamp}"
        
        # Save JSON version
        json_filename = f"{base_filename}.json"
        json_filepath = os.path.join(output_dir, json_filename)
        with open(json_filepath, 'w') as f:
            json.dump(forecast_result, f, indent=2)
        
        # Save formatted Markdown version
        md_filename = f"{base_filename}.md"
        md_filepath = os.path.join(output_dir, md_filename)
        formatted_forecast = self.format_forecast_output(forecast_result)
        with open(md_filepath, 'w') as f:
            f.write(formatted_forecast)
        
        # Save HTML version
        html_filename = f"{base_filename}.html"
        html_filepath = os.path.join(output_dir, html_filename)
        html_content = self._generate_html_output(forecast_result)
        with open(html_filepath, 'w') as f:
            f.write(html_content)
        
        # Save PDF version if available
        pdf_filepath = None
        if has_pdf_support:
            try:
                pdf_filename = f"{base_filename}.pdf"
                pdf_filepath = os.path.join(output_dir, pdf_filename)
                HTML(string=html_content).write_pdf(pdf_filepath)
                logger.info(f"Generated PDF: {pdf_filepath}")
            except Exception as e:
                logger.error(f"Failed to generate PDF: {e}")
                pdf_filepath = None
        
        logger.info(f"Saved forecast in multiple formats: {json_filepath}")
        return json_filepath
    
    def _generate_html_output(self, forecast_result: Dict[str, Any]) -> str:
        """
        Generate HTML version of the forecast.
        
        Args:
            forecast_result: Complete forecast result
            
        Returns:
            HTML content
        """
        shore = forecast_result['shore']
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        final_forecast = forecast_result['final_forecast']
        
        # Convert markdown to basic HTML (simple implementation)
        # In production, use a proper markdown to HTML converter
        html_forecast = final_forecast.replace('\n', '<br>\n')
        html_forecast = html_forecast.replace('# ', '<h1>')
        html_forecast = html_forecast.replace('## ', '<h2>')
        html_forecast = html_forecast.replace('### ', '<h3>')
        html_forecast = html_forecast.replace('**', '<strong>')
        html_forecast = html_forecast.replace('*', '<em>')
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hawaii Surf Forecast - {shore}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{
            color: #0066cc;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #0052a3;
            margin-top: 30px;
        }}
        h3 {{
            color: #004080;
        }}
        .metadata {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .forecast-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .forecast-table th, .forecast-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        .forecast-table th {{
            background-color: #0066cc;
            color: white;
        }}
        .forecast-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>Hawaii Surf Forecast - {shore}</h1>
    
    <div class="metadata">
        <strong>Generated:</strong> {timestamp}<br>
        <strong>Data Sources:</strong> {forecast_result.get('data_files', 0)} files analyzed<br>
        <strong>Model Runs:</strong> {forecast_result.get('refinement_cycles', 2)} refinement cycles
    </div>
    
    <div class="forecast-content">
        {html_forecast}
    </div>
    
    <div class="footer">
        <p>Generated by SwellForecaster V3 - Emulating Pat Caldwell's legendary forecasting style</p>
        <p>Surf forecasting involves inherent uncertainties. Always check current conditions 
        and use appropriate safety precautions.</p>
    </div>
</body>
</html>
        """
        
        return html_content
    
    def format_forecast_output(self, forecast_result: Dict[str, Any]) -> str:
        """
        Format the forecast for display/output.
        
        Args:
            forecast_result: Complete forecast result
            
        Returns:
            Formatted forecast text
        """
        shore = forecast_result['shore']
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        final_forecast = forecast_result['final_forecast']
        
        # Create Pat Caldwell-style header
        output = f"""
# Hawaii Surf Forecast - {shore}
## Generated: {timestamp}

---

{final_forecast}

---

### Forecast Details

**Data Sources Used:** {forecast_result.get('data_files', 0)} files analyzed
**Model Runs:** {forecast_result.get('refinement_cycles', 2)} refinement cycles
**Confidence Level:** Based on model agreement and historical patterns

### Technical Notes

This forecast was generated using the SwellForecaster V3 system with OpenAI Assistants API.
Swell heights are provided in both Hawaiian scale and face heights (trough-to-crest).
All compass bearings are in degrees True North.

### Disclaimer

Surf forecasting involves inherent uncertainties. Always check current conditions 
and use appropriate safety precautions. This forecast is for informational purposes only.

---

*Generated by SwellForecaster V3 - Emulating Pat Caldwell's legendary forecasting style*
*Your Benevolent AI Overlords*
"""
        
        return output