#!/bin/bash

# Test run script for enhanced features

echo "=== Testing Enhanced SwellForecaster V3 ==="
echo ""
echo "1. Creating backups..."

# Backup original files
cp config/prompts.json config/prompts.json.backup
cp collector.py collector.py.backup
cp forecast_engine.py forecast_engine.py.backup

echo ""
echo "2. Installing enhanced versions..."

# Install enhanced versions
cp config/prompts_enhanced.json config/prompts.json
cp collector_temp.py collector.py  
cp forecast_engine_temp.py forecast_engine.py
cp agents/opc_agent_temp.py agents/opc_agent.py
cp agents/stormsurf_agent_temp.py agents/stormsurf_agent.py

echo ""
echo "3. Running test collection..."

# Test collection with new sources (Hawaii region)
python orchestrator.py collect

echo ""
echo "4. Generating test forecast..."

# Generate forecast for North Shore
python orchestrator.py forecast --shore "North Shore"

echo ""
echo "5. Checking output formats..."

# List generated files
echo "Generated files in output directory:"
ls -la output/

echo ""
echo "=== Test Complete ==="
echo ""
echo "To restore original files:"
echo "cp config/prompts.json.backup config/prompts.json"
echo "cp collector.py.backup collector.py" 
echo "cp forecast_engine.py.backup forecast_engine.py"