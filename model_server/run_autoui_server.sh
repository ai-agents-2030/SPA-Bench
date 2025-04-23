#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# shellcheck disable=SC1091
source activate base

conda activate AutoUI_Server
python ../framework/models/AutoUI/server.py

read -p "Press [Enter] key to exit..."