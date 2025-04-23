#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# shellcheck disable=SC1091
source activate base

name="CogAgent_Server"
python_version="3.10"
conda create -n $name python=$python_version -y
echo "Created conda environment ${name} with Python ${python_version}."
conda activate $name
# Separate SwissArmyTransformer since its dependency `deepspeed` only supports linux, but is not required in this benchmark codebase
pip install 'SwissArmyTransformer>=0.4.9' --no-deps
# Install all other dependencies of SwissArmyTransformer except `deepspeed`
pip install -r SwissArmyTransformer_dependencies.txt
pip install -r cogagent_server_requirements.txt
pip install spacy
python -m spacy download en_core_web_sm
echo "Installed packages in ${name}."
conda deactivate
