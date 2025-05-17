#!/usr/bin/env python3
"""
SwellForecaster V3 - Main Orchestrator

This module orchestrates the complete workflow:
1. Data collection from various sources
2. Upload to Assistants API
3. Forecast generation with critic refinement
4. Output formatting
"""

import os
import sys
import time
import argparse
import asyncio
from configparser import ConfigParser
from openai import OpenAI

# Import our modules
from assistants import AssistantManager, ThreadManager, FileManager
from logging_config import setup_logging, get_logger, patch_openai_client
from collector import DataCollector
from agents.file_adapter import FileAdapter
from data_assessment import DataAssessment
from forecast_engine import ForecastEngine

# Load configuration
config = ConfigParser()
config.read('config/config.ini')

# Set up logging based on config
setup_logging(config)
logger = get_logger('surf_forecast')


def main():
    """Main entry point for the orchestrator."""
    parser = argparse.ArgumentParser(description='SwellForecaster V3')
    parser.add_argument('command', choices=['collect', 'analyze', 'forecast', 'full'],
                        help='Command to run')
    parser.add_argument('--shore', help='Specific shore to forecast (for forecast command)')
    parser.add_argument('--bundle-id', help='Specific data bundle to analyze')
    
    args = parser.parse_args()
    
    # Initialize OpenAI client
    client = OpenAI(api_key=config['openai']['api_key'])
    
    # Patch client for debug logging if enabled
    patch_openai_client(client)
    
    # Initialize managers
    assistant_manager = AssistantManager(client, config)
    thread_manager = ThreadManager(client)
    file_manager = FileManager(client)
    
    # Initialize data collection
    file_adapter = FileAdapter(config)
    collector = DataCollector(config)
    
    # Initialize data assessment
    data_assessment = DataAssessment(assistant_manager, thread_manager, file_manager)
    
    # Initialize forecast engine
    forecast_engine = ForecastEngine(assistant_manager, thread_manager, file_manager, config)
    
    # Execute command
    if args.command == 'collect':
        bundle_metadata = asyncio.run(run_collection(collector))
        bundle_id = bundle_metadata.get('bundle_id', bundle_metadata.get('bundle_info', {}).get('bundle_id', 'unknown'))
        logger.info(f"Collection complete: {bundle_id}")
    elif args.command == 'analyze':
        run_analysis(assistant_manager, thread_manager, file_manager, 
                    collector, data_assessment, args.bundle_id)
    elif args.command == 'forecast':
        run_forecast(assistant_manager, thread_manager, file_manager,
                    collector, data_assessment, forecast_engine, args.shore)
    elif args.command == 'full':
        bundle_metadata = asyncio.run(run_collection(collector))
        run_full_pipeline(assistant_manager, thread_manager, file_manager,
                         collector, data_assessment, forecast_engine, 
                         bundle_metadata)
    
    logger.info(f"Completed {args.command} command")


async def run_collection(collector: DataCollector):
    """Run data collection from all configured sources."""
    logger.info("Starting data collection")
    if hasattr(logger, 'verbose'):
        logger.verbose("Initializing data collection agents")
    logger.debug("Debug: Collection configuration loaded")
    
    # Run collection
    bundle_metadata = await collector.collect_all()
    return bundle_metadata


def run_analysis(assistant_manager, thread_manager, file_manager, 
                collector, data_assessment, bundle_id=None):
    """Run analysis on collected data."""
    logger.info(f"Starting analysis{' for bundle ' + bundle_id if bundle_id else ''}")
    
    # Get bundle metadata
    if bundle_id:
        # TODO: Load specific bundle by ID
        pass
    else:
        # Get latest bundle
        bundle_metadata = collector.get_latest_bundle()
        if not bundle_metadata:
            logger.error("No data bundles found")
            return
    
    # Perform data assessment
    assessment_report = data_assessment.assess_bundle(
        file_ids=bundle_metadata['file_ids'],
        bundle_info=bundle_metadata['bundle_info']
    )
    
    logger.info("Data assessment complete")
    # TODO: Use assessment report in forecasting workflow
    pass


def run_forecast(assistant_manager, thread_manager, file_manager,
                collector, data_assessment, forecast_engine, shore=None):
    """Generate forecast for specific shore."""
    # Get latest bundle for data
    bundle_metadata = collector.get_latest_bundle()
    if not bundle_metadata:
        logger.error("No data bundles found")
        return
    
    # Get assessment report
    assessment_report = data_assessment.assess_bundle(
        file_ids=bundle_metadata.get('file_ids', []),
        bundle_info=bundle_metadata.get('bundle_info', {})
    )
    
    shores = assistant_manager.config['general']['shores'].split(',') if not shore else [shore]
    
    for shore in shores:
        shore = shore.strip()
        logger.info(f"Generating forecast for {shore}")
        
        # Get relevant files for this shore
        file_ids = bundle_metadata.get('uploaded_file_ids', [])  # TODO: Filter by shore
        
        # Generate forecast
        forecast_result = forecast_engine.generate_forecast(
            shore=shore,
            file_ids=file_ids,
            assessment_report=assessment_report
        )
        
        # Save forecast
        output_dir = assistant_manager.config.get('general', 'output_directory')
        forecast_path = forecast_engine.save_forecast(forecast_result, output_dir)
        logger.info(f"Saved {shore} forecast to {forecast_path}")


def run_full_pipeline(assistant_manager, thread_manager, file_manager,
                     collector, data_assessment, forecast_engine,
                     bundle_metadata):
    """Run the complete pipeline: collection -> assessment -> forecast."""
    logger.info("Running full pipeline")
    
    # Perform data assessment
    assessment_report = data_assessment.assess_bundle(
        file_ids=bundle_metadata.get('uploaded_file_ids', []),
        bundle_info=bundle_metadata
    )
    
    # Generate forecasts for all shores  
    shores = assistant_manager.config['general']['shores'].split(',')
    
    for shore in shores:
        shore = shore.strip()
        logger.info(f"Generating forecast for {shore}")
        
        # Get relevant files for this shore
        file_ids = bundle_metadata.get('uploaded_file_ids', [])  # TODO: Filter by shore
        
        # Generate forecast
        forecast_result = forecast_engine.generate_forecast(
            shore=shore,
            file_ids=file_ids,
            assessment_report=assessment_report
        )
        
        # Save forecast
        output_dir = assistant_manager.config.get('general', 'output_directory')
        forecast_path = forecast_engine.save_forecast(forecast_result, output_dir)
        logger.info(f"Saved {shore} forecast to {forecast_path}")
    
    logger.info("Full pipeline complete")


if __name__ == "__main__":
    main()