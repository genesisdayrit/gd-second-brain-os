#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set the project root (assuming the script is in the config directory)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Source the .env file
source "$PROJECT_ROOT/.env"

# Run the specified Python script
python "$PROJECT_ROOT/dropbox-api/file-creation/$1"

# Deactivate virtual environment
deactivate
