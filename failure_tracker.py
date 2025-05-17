"""
Failure Tracker V2 for SwellForecaster V3.

Enhanced with correct method names and new failure tracking functionality.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from logging_config import get_logger

logger = get_logger(__name__)


class FailureTracker:
    """
    Tracks data source failures for monitoring and debugging.
    """
    
    def __init__(self, log_file: str = "logs/failure_log.json"):
        """
        Initialize the FailureTracker.
        
        Args:
            log_file: Path to the failure log file
        """
        self.log_file = log_file
        self.failures: List[Dict[str, Any]] = []
        self.current_session_failures: List[Dict[str, Any]] = []
        self._load_failures()
    
    def _load_failures(self):
        """Load existing failures from log file."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    self.failures = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning(f"Could not load failure log from {self.log_file}")
                self.failures = []
    
    def _save_failures(self):
        """Save failures to log file."""
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, 'w') as f:
                json.dump(self.failures, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Could not save failure log: {e}")
    
    def add_failure(self, source: str, error_type: str, message: str, 
                   url: Optional[str] = None, agent: Optional[str] = None):
        """
        Add a failure to the tracker (new method matching collector expectations).
        
        Args:
            source: Data source name
            error_type: Type of error (e.g., class name)
            message: Error message
            url: URL that failed (optional)
            agent: Agent name that encountered the failure
        """
        failure = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': source,
            'error_type': error_type,
            'message': str(message),
            'url': url,
            'agent': agent
        }
        
        self.failures.append(failure)
        self.current_session_failures.append(failure)
        self._save_failures()
        
        logger.warning(f"Failure added: {source} - {error_type} - {message}")
    
    def log_failure(self, source: str, url: str, error: str, 
                   agent: Optional[str] = None):
        """
        Log a data source failure (legacy method).
        
        Args:
            source: Data source name
            url: URL that failed
            error: Error message
            agent: Agent name that encountered the failure
        """
        self.add_failure(source, "ConnectionError", error, url, agent)
    
    def get_recent_failures(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get failures from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of recent failures
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_failures = []
        for failure in self.failures:
            failure_time = datetime.fromisoformat(failure['timestamp'])
            if failure_time > cutoff_time:
                recent_failures.append(failure)
        
        return recent_failures
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """
        Get a summary of failures by source.
        
        Returns:
            Dictionary with failure statistics
        """
        summary = {
            'total_failures': len(self.failures),
            'by_source': {},
            'by_agent': {},
            'by_error_type': {},
            'recent_24h': len(self.get_recent_failures(24))
        }
        
        for failure in self.failures:
            source = failure['source']
            agent = failure.get('agent', 'unknown')
            error_type = failure.get('error_type', 'unknown')
            
            if source not in summary['by_source']:
                summary['by_source'][source] = 0
            summary['by_source'][source] += 1
            
            if agent not in summary['by_agent']:
                summary['by_agent'][agent] = 0
            summary['by_agent'][agent] += 1
            
            if error_type not in summary['by_error_type']:
                summary['by_error_type'][error_type] = 0
            summary['by_error_type'][error_type] += 1
        
        return summary
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of failures (alias for get_failure_summary).
        This method is expected by the collector.
        
        Returns:
            Dictionary with failure statistics
        """
        # Include current session failures in the summary
        summary = self.get_failure_summary()
        summary['session_failures'] = len(self.current_session_failures)
        return summary
    
    def save_summary(self, filepath: str):
        """
        Save the failure summary to a file.
        
        Args:
            filepath: Path to save the summary
        """
        try:
            summary = self.get_summary()
            with open(filepath, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Saved failure summary to {filepath}")
        except Exception as e:
            logger.error(f"Error saving failure summary: {str(e)}")
    
    def clear_old_failures(self, days: int = 7):
        """
        Clear failures older than N days.
        
        Args:
            days: Number of days to keep
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        self.failures = [
            f for f in self.failures 
            if datetime.fromisoformat(f['timestamp']) > cutoff_time
        ]
        
        self._save_failures()
        logger.info(f"Cleared failures older than {days} days")
    
    def generate_failure_report(self) -> str:
        """
        Generate a human-readable failure report.
        
        Returns:
            Formatted failure report
        """
        summary = self.get_summary()
        recent = self.get_recent_failures(24)
        
        report = f"""
Data Source Failure Report
Generated: {datetime.utcnow().isoformat()}

Summary:
- Total Failures: {summary['total_failures']}
- Session Failures: {summary['session_failures']}
- Failures in Last 24h: {summary['recent_24h']}

Failures by Source:
"""
        
        for source, count in summary['by_source'].items():
            report += f"- {source}: {count}\n"
        
        report += "\nFailures by Agent:\n"
        for agent, count in summary['by_agent'].items():
            report += f"- {agent}: {count}\n"
            
        report += "\nFailures by Error Type:\n"
        for error_type, count in summary['by_error_type'].items():
            report += f"- {error_type}: {count}\n"
        
        if recent:
            report += "\nRecent Failures (Last 24h):\n"
            for failure in recent[:10]:  # Show max 10 recent
                report += f"- {failure['timestamp']}: {failure['source']} ({failure.get('url', 'N/A')})\n"
                report += f"  Error: {failure.get('error_type', 'Unknown')} - {failure['message']}\n"
        
        return report