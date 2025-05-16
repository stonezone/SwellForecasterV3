#!/usr/bin/env python3
"""
Test script for enhanced features:
1. New prompts from prompts.json.example
2. New data sources integration
3. Multi-format output (MD, HTML, PDF)
"""

import asyncio
import sys
import os
import shutil
from datetime import datetime

# Backup original files
def backup_files():
    files_to_backup = [
        'config/prompts.json',
        'collector.py',
        'forecast_engine.py'
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            backup_name = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file, backup_name)
            print(f"Backed up {file} to {backup_name}")

# Replace with enhanced versions
def install_enhanced_files():
    replacements = [
        ('config/prompts_enhanced.json', 'config/prompts.json'),
        ('collector_temp.py', 'collector.py'),
        ('forecast_engine_temp.py', 'forecast_engine.py'),
        ('agents/opc_agent_temp.py', 'agents/opc_agent.py'),
        ('agents/stormsurf_agent_temp.py', 'agents/stormsurf_agent.py')
    ]
    
    for src, dst in replacements:
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"Installed {src} as {dst}")
        else:
            print(f"Warning: {src} not found")

# Test the enhanced system
async def test_enhanced_system():
    print("\n=== Testing Enhanced SwellForecaster V3 ===")
    
    # Test data collection with new sources
    print("\n1. Testing data collection with new sources...")
    os.system("python orchestrator.py collect Hawaii")
    
    # Test forecast generation with enhanced prompts
    print("\n2. Testing forecast generation with enhanced prompts...")
    os.system("python orchestrator.py forecast North")
    
    # Verify multi-format output
    print("\n3. Checking output formats...")
    output_dir = "output"
    formats = ['.json', '.md', '.html', '.pdf']
    
    latest_files = []
    for file in os.listdir(output_dir):
        if any(file.endswith(fmt) for fmt in formats):
            latest_files.append(file)
    
    print(f"Found output files: {latest_files}")
    
    # Check for all formats
    for fmt in formats:
        if any(f.endswith(fmt) for f in latest_files):
            print(f"✓ {fmt} format found")
        else:
            print(f"✗ {fmt} format missing")

if __name__ == "__main__":
    print("Enhanced SwellForecaster V3 Test Script")
    
    # Ask for confirmation
    response = input("\nThis will backup and replace current files. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Test cancelled")
        sys.exit(0)
    
    # Backup original files
    backup_files()
    
    # Install enhanced versions
    install_enhanced_files()
    
    # Run tests
    asyncio.run(test_enhanced_system())
    
    print("\n=== Test Complete ===")
    print("Check the output directory for generated forecasts in multiple formats.")
    print("To restore original files, copy the .backup_* files back to their original names.")