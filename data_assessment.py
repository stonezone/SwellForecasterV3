"""
Data Assessment module for SwellForecaster V3.

This module uses the Data Assessment Assistant to analyze collected data
for quality, consistency, and completeness.
"""

from typing import Dict, Any, List, Optional
from assistants import AssistantManager, ThreadManager, FileManager
from logging_config import get_logger

logger = get_logger(__name__)


class DataAssessment:
    """
    Manages data quality assessment using the Data Assessment Assistant.
    """
    
    def __init__(self, assistant_manager: AssistantManager,
                 thread_manager: ThreadManager,
                 file_manager: FileManager):
        """
        Initialize the DataAssessment module.
        
        Args:
            assistant_manager: AssistantManager instance
            thread_manager: ThreadManager instance
            file_manager: FileManager instance
        """
        self.assistant_manager = assistant_manager
        self.thread_manager = thread_manager
        self.file_manager = file_manager
        
        # Get the data assessment assistant ID
        self.assistant_id = assistant_manager.get_assistant('data_assessment')
        if not self.assistant_id:
            raise ValueError("Data Assessment assistant not found")
    
    def _add_message_with_files(self, thread_id: str, content: str, file_ids: List[str]):
        """
        Add message with files, handling the 10-attachment limit per message.
        
        Args:
            thread_id: Thread ID
            content: Message content  
            file_ids: List of file IDs
        """
        # API limit is 10 attachments per message
        if len(file_ids) <= 10:
            self.thread_manager.add_message(
                thread_id=thread_id,
                content=content,
                file_ids=file_ids
            )
        else:
            # Send files in batches of 10
            logger.info(f"Batching {len(file_ids)} files into multiple messages")
            
            # First message with initial prompt and first 10 files
            self.thread_manager.add_message(
                thread_id=thread_id,
                content=content,
                file_ids=file_ids[:10]
            )
            
            # Subsequent messages with remaining files
            for i in range(10, len(file_ids), 10):
                batch = file_ids[i:i+10]
                self.thread_manager.add_message(
                    thread_id=thread_id,
                    content=f"Additional data files (batch {i//10 + 1}):",
                    file_ids=batch
                )
    
    def assess_bundle(self, file_ids: List[str], bundle_info: Dict[str, Any]) -> str:
        """
        Assess a data bundle for quality and consistency.
        
        Args:
            file_ids: List of file IDs to assess
            bundle_info: Information about the bundle
            
        Returns:
            Assessment report as a string
        """
        logger.info(f"Starting data assessment for bundle {bundle_info.get('bundle_id', 'unknown')}")
        
        # Create a thread for assessment
        thread_id = self.thread_manager.create_thread(
            name=f"assessment_{bundle_info.get('bundle_id', 'unknown')}"
        )
        
        try:
            # Create the assessment prompt
            prompt = f"""
            Please analyze this data bundle for quality, consistency, and completeness.
            
            Bundle Information:
            - Bundle ID: {bundle_info.get('bundle_id')}
            - Timestamp: {bundle_info.get('timestamp')}
            - Region: {bundle_info.get('region')}
            
            Focus on:
            1. Data completeness - are all expected data sources present?
            2. Data consistency - do different sources agree or contradict?
            3. Data quality - are there missing values, errors, or anomalies?
            4. Temporal alignment - are all data sources from similar time periods?
            5. Geographic relevance - is the data appropriate for the target region?
            
            Provide a structured assessment report with:
            - Executive summary
            - Detailed findings by data source
            - Potential issues that could affect forecast accuracy
            - Recommendations for data usage
            """
            
            # Add message with files
            self._add_message_with_files(thread_id, prompt, file_ids)
            
            # Run the assessment
            run_id = self.thread_manager.run_assistant(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            
            # Wait for completion
            self.thread_manager.wait_for_run(thread_id, run_id)
            
            # Get the assessment report
            report = self.thread_manager.get_last_assistant_message(thread_id)
            
            logger.info("Data assessment completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Error during data assessment: {e}")
            raise
        finally:
            # Clean up thread
            self.thread_manager.delete_thread(thread_id)
    
    def assess_regional_data(self, file_ids: List[str], shore: str) -> str:
        """
        Assess data specific to a shore region.
        
        Args:
            file_ids: List of file IDs relevant to the shore
            shore: Shore name (North Shore or South Shore)
            
        Returns:
            Regional assessment report
        """
        logger.info(f"Starting regional data assessment for {shore}")
        
        # Create a thread for assessment
        thread_id = self.thread_manager.create_thread(name=f"regional_{shore}")
        
        try:
            # Create the regional assessment prompt
            prompt = f"""
            Please analyze this data specifically for {shore} surf forecasting.
            
            Focus on:
            1. Data relevance to {shore} conditions
            2. Coverage of key swell windows for {shore}
            3. Local wind and weather patterns affecting {shore}
            4. Any missing data critical for {shore} forecasting
            5. Quality of buoy and model data for {shore} swells
            
            Consider {shore}-specific factors:
            {"- North-facing swells (NW, N, NE)" if "North" in shore else "- South-facing swells (S, SSW, SW)"}
            {"- Winter swell patterns" if "North" in shore else "- Summer swell patterns"}
            {"- Trade wind effects" if "North" in shore else "- Kona wind effects"}
            
            Provide recommendations for using this data to forecast {shore} conditions.
            """
            
            # Add message with files
            self._add_message_with_files(thread_id, prompt, file_ids)
            
            # Run the assessment
            run_id = self.thread_manager.run_assistant(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            
            # Wait for completion
            self.thread_manager.wait_for_run(thread_id, run_id)
            
            # Get the assessment report
            report = self.thread_manager.get_last_assistant_message(thread_id)
            
            logger.info(f"Regional assessment for {shore} completed")
            return report
            
        except Exception as e:
            logger.error(f"Error during regional assessment: {e}")
            raise
        finally:
            # Clean up thread
            self.thread_manager.delete_thread(thread_id)
    
    def compare_sources(self, file_ids: List[str], source_types: List[str]) -> str:
        """
        Compare different data sources for consistency.
        
        Args:
            file_ids: List of file IDs to compare
            source_types: List of source types (e.g., ['buoy', 'model', 'forecast'])
            
        Returns:
            Comparison report
        """
        logger.info(f"Comparing data sources: {source_types}")
        
        thread_id = self.thread_manager.create_thread(name="source_comparison")
        
        try:
            prompt = f"""
            Please compare these data sources for consistency:
            {', '.join(source_types)}
            
            Analysis tasks:
            1. Compare wave height predictions across sources
            2. Check swell direction consistency
            3. Verify wind speed and direction alignment
            4. Identify any major discrepancies
            5. Assess which sources appear most reliable
            
            For any discrepancies found:
            - Explain possible reasons
            - Suggest which source to prioritize
            - Note impact on forecast confidence
            
            Provide a detailed comparison report.
            """
            
            self._add_message_with_files(thread_id, prompt, file_ids)
            
            run_id = self.thread_manager.run_assistant(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            
            self.thread_manager.wait_for_run(thread_id, run_id)
            
            report = self.thread_manager.get_last_assistant_message(thread_id)
            
            logger.info("Source comparison completed")
            return report
            
        except Exception as e:
            logger.error(f"Error during source comparison: {e}")
            raise
        finally:
            self.thread_manager.delete_thread(thread_id)