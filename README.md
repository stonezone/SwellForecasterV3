# SwellForecaster V3

A multi-agent AI system using OpenAI's Assistants API to generate comprehensive 10-day surf and wind forecasts for Oahu's north and south shores. The system emulates the style and accuracy of renowned surf forecaster Pat Caldwell.

## Overview

SwellForecaster V3 leverages GPT-4.1 for critical forecasting components and GPT-4.1 Nano for support functions. The system collects data from multiple sources, assesses data quality, and generates forecasts with critic refinement cycles.

## Architecture

```
┌─────────────────┐
│ Orchestrator    │
│ (Main Controller)│
└─────────────────┘
         │
┌────────▼─────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Data Collection  │ │ Data Assessment │ │ Forecast Engine │
│ Agents           │ │ Assistant       │ │                 │
└────────┬─────────┘ └─────┬───────────┘ └────┬────────────┘
         │                 │                   │
┌────────▼─────────┐       │            ┌─────▼───────────┐
│ - Buoy Agent     │       │            │ - Forecaster    │
│ - Weather Agent  │       │            │   (GPT-4.1)     │
│ - Model Agent    │       │            └─────┬───────────┘
│ - Satellite Agent│       │                  │
└──────────────────┘       │            ┌─────▼───────────┐
                           │            │ - Critic        │
                           │            │   (GPT-4.1)     │
                           │            └─────────────────┘
```

## Features

- **Multi-Agent Data Collection**: Parallel collection from buoys, weather stations, wave models, and satellite imagery
- **Assistants API Integration**: Persistent assistants with specialized roles
- **Data Quality Assessment**: AI-driven analysis of data consistency and completeness
- **Forecast Refinement**: Critic-based improvement cycles for accuracy
- **Flexible Configuration**: Easy customization of data sources and parameters
- **Failure Tracking**: Automatic logging and reporting of connection failures
- **Three-Tier Logging**: INFO, VERBOSE, and DEBUG levels with API call tracking

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Valid OpenAI API key
- Optional: API keys for additional data sources (Windy, ECMWF, StormGlass, Surfline)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SwellForecasterV3.git
cd SwellForecasterV3
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the system:
   - Copy `config/config.ini.example` to `config/config.ini`
   - Add your OpenAI API key
   - Configure data sources and other settings
   - Optionally modify prompts in `config/prompts.json`

## Configuration

### config.ini

```ini
[general]
output_directory = ./output
data_directory = ./data
log_level = INFO  # INFO, VERBOSE, DEBUG
forecast_days = 10
shores = North Shore, South Shore
refinement_cycles = 2

[openai]
api_key = your_api_key_here
organization =  # Optional
forecasting_model = gpt-4.1
support_model = gpt-4.1-nano
max_tokens = 4000
temperature = 0.2

[data_sources]
buoy_urls = https://www.ndbc.noaa.gov/station_page.php?station=51201
satellite_urls = https://www.nhc.noaa.gov/satellite.php
model_urls = https://www.pacioos.hawaii.edu/waves/model-hawaii/

[sources]
enable_buoy = true
enable_weather = true
enable_model = true
enable_satellite = true

[assistants]
save_assistant_ids = true
assistants_file = ./config/assistants.json
```

### prompts.json

Custom prompts for each assistant are stored in `config/prompts.json`. Modify these to adjust the style and focus of forecasts.

## Usage

### Basic Commands

```bash
# Collect data from all configured sources
python orchestrator.py collect

# Analyze the latest data bundle
python orchestrator.py analyze

# Generate forecast for specific shore
python orchestrator.py forecast --shore "North Shore"

# Run complete pipeline (collect → analyze → forecast)
python orchestrator.py full
```

### Command Options

- `--shore`: Specify shore for forecast (North Shore or South Shore)
- `--bundle-id`: Analyze specific data bundle by ID

### Example Workflow

1. **Data Collection**:
```bash
python orchestrator.py collect
```
Collects data from all enabled sources and uploads to Assistants API.

2. **Data Analysis**:
```bash
python orchestrator.py analyze
```
Assesses data quality and identifies issues or inconsistencies.

3. **Forecast Generation**:
```bash
python orchestrator.py forecast
```
Generates forecasts for all configured shores with critic refinement.

## Code Structure

### Core Modules

- `orchestrator.py`: Main entry point and command dispatcher
- `assistants/`: Assistants API management
  - `manager.py`: Assistant creation and persistence
  - `thread_manager.py`: Thread and message handling
  - `file_manager.py`: File upload management
- `agents/`: Data collection agents
  - `buoy_agent.py`: NOAA buoy data collection
  - `weather_agent.py`: Weather station data
  - `model_agent.py`: Wave model data
  - `satellite_agent.py`: Satellite imagery
- `collector.py`: Orchestrates agent-based data collection
- `data_assessment.py`: AI-driven data quality analysis
- `forecast_engine.py`: Forecast generation with critic refinement
- `failure_tracker.py`: Connection failure monitoring

### Data Flow

1. **Collection Phase**:
   - Agents fetch data from configured sources
   - Data saved locally in bundle directory
   - Files uploaded to Assistants API
   - Metadata tracked for organization

2. **Assessment Phase**:
   - Data Assessment Assistant analyzes all files
   - Identifies quality issues and inconsistencies
   - Generates assessment report

3. **Forecast Phase**:
   - Forecaster Assistant generates initial forecast
   - Critic Assistant reviews and suggests improvements
   - Refinement cycles improve accuracy
   - Final forecast saved to output directory

## Logging

The system supports three logging levels:

- **INFO**: Basic operational information
- **VERBOSE**: Detailed process flow
- **DEBUG**: Full API request/response logging

Logs are saved to:
- `logs/swellforecaster_YYYYMMDD.log`: Main application log
- `logs/api_debug.log`: OpenAI API interactions (DEBUG only)
- `logs/failure_log.json`: Data source failure tracking

## Failure Tracking

Failed connections are automatically logged with:
- Timestamp
- Source and URL
- Error message
- Agent that encountered the failure

View failure report:
```python
from failure_tracker import FailureTracker
tracker = FailureTracker()
print(tracker.generate_failure_report())
```

## Development

### Adding New Data Agents

1. Create agent module in `agents/`:
```python
async def my_agent(ctx, session):
    # Fetch data
    # Save to ctx
    # Return metadata
    return metadata_list
```

2. Register in `collector.py`:
```python
self.agents = {
    'my_agent': my_agent,
    # ...
}
```

3. Add configuration in `config.ini`:
```ini
[sources]
enable_my_agent = true
```

### Customizing Forecasts

1. Modify prompts in `config/prompts.json`
2. Adjust refinement cycles in `config.ini`
3. Update forecast template in `templates/forecast_template.md`

## Troubleshooting

### Common Issues

1. **Assistant Not Found**:
   - Delete `config/assistants.json`
   - Assistants will be recreated on next run

2. **API Rate Limits**:
   - Reduce parallel agent execution
   - Increase delays between API calls

3. **Connection Failures**:
   - Check `logs/failure_log.json`
   - Verify API keys and URLs
   - Test network connectivity

### Debug Mode

Enable debug logging for detailed troubleshooting:
```ini
[general]
log_level = DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by Pat Caldwell's legendary surf forecasts
- Built on OpenAI's Assistants API
- Data sources: NOAA, PacIOOS, Surfline, and others

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review logs for error details