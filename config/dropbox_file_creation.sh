#!/bin/bash

# Activate virtual environment
source /home/ubuntu/Repos/gd-second-brain-os/venv/bin/activate

# Source the .env file
source /home/ubuntu/Repos/gd-second-brain-os/.env

# Run the specified Python script
python /home/ubuntu/Repos/gd-second-brain-os/dropbox-api/file-creation/$1

# Deactivate virtual environment
deactivate
