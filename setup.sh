#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# shellcheck disable=SC1091
source activate base

conda create -n Smartphone-Agent-Benchmark python=3.11.0 -y
echo "Created conda environment Smartphone-Agent-Benchmark with Python 3.11.0."

conda activate Smartphone-Agent-Benchmark
pip install -r requirements.txt
echo "Installed packages in Smartphone-Agent-Benchmark from requirements.txt."

# Create conda environments and install dependencies for each app agent
### AppAgent ###
name="AppAgent"
python_version="3.12.3"
conda create -n $name python=$python_version -y
echo "Created conda environment ${name} with Python ${python_version}."
conda activate $name
pip install -r ./requirements/${name}.txt
echo "Installed packages in ${name}."
conda deactivate

### MobileAgent, MobileAgentV2 ###
name="MobileAgent"
python_version="3.9.7"
conda create -n $name python=$python_version -y
echo "Created conda environment ${name} with Python ${python_version}."
conda activate $name
pip install -r ./requirements/${name}.txt
echo "Installed packages in ${name}."
# Download local models
python ./framework/models/MobileAgent/Mobile-Agent/load_models.py
conda deactivate

echo "Script completed successfully."
