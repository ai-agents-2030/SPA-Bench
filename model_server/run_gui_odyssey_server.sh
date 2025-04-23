#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# shellcheck disable=SC1091
source activate base

conda activate GUI_Odyssey_Server
cd ../framework/models/GUI-Odyssey
python server.py

read -p "Press [Enter] key to exit..."