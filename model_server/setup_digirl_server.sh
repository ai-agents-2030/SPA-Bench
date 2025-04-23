#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# shellcheck disable=SC1091
source activate base

name="AutoUI_Server"
python_version="3.10"
conda create -n $name python=$python_version -y
echo "Created conda environment ${name} with Python ${python_version}."
conda activate $name
pip install -r autoui_server_requirements.txt
echo "Installed packages in ${name}."
conda deactivate

# Sharing same env as AutoUI