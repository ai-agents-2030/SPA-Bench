# 🌿🪑 SPA-Bench Documentation

## Guidelines

### Prerequisites

1. Ensure that `conda` is available on your system. You can download it from the [conda.io website](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).
2. Download and install the [Android Debug Bridge (adb)](https://developer.android.com/tools/adb) on your PC. This command-line tool allows your PC to communicate with your Android device. After installation, add the adb tool to your system's environment variables.

### Setup

1. **Using a Physical Android Device:**

   - Obtain an Android device.
   - Enable USB debugging by going to `Settings` > `Developer Options` > `USB debugging`. If `Developer Options` is not visible, go to `Settings` > `About phone` and tap on `Build number` seven times to enable it.
   - Connect your device to your PC using a USB cable.


2. **Using an Android Emulator:**

   - If a physical Android device is unavailable, download and install [Android Studio](https://developer.android.com/studio).
   - Launch the emulator from the Device Manager in Android Studio.
   - (Optional) You may use our pre-configured emulator snapshot with all required English apps pre-installed. _(Coming soon)_
   - (Optional) To install additional apps, simply download the APK files and drag them onto the emulator window.

### Repository Setup

1. Clone this repository to your local machine:

   ```sh
   git clone --recurse-submodules https://github.com/ai-agents-2030/SPA-Bench.git
   cd SPA-Bench
   ```

2. Run the setup script to initialize the environment and install necessary dependencies:

   ```sh
   ./setup.sh
   ```


3. Rename and configure files:

   - Rename `config.yaml.example` to `config.yaml` and update it to suit your environment.
   - Rename `.env.example` to `.env` and fill in required environment variables.


### Hosting Models (Optional)
SPA-Bench supports several agents that require self-hosted model APIs. These steps are only necessary if you plan to evaluate agents that require self-hosted models.
1. Hosting MobileAgentV2

   To use MobileAgentV2 without relying on the official Qwen or OpenAI API
   - Follow the instructions in `./framework/self_hosted_vlm/README.md` to host the model on your own GPU server.
   - After deployment, set the `QWEN_API_URL` in `.env` to your endpoint, and set `QWEN_API_KEY` to `self_hosted`.


2. Hosting Other Agents (AutoUI / DigiRLAgent / CogAgent / GUI-Odyssey)

   To use these agents, you must host the models yourself. The framework provides tools for both server hosting and client-side integration.
   - **Model Servers**: Navigate to `./model_server` to find setup scripts, e.g.:
      ```sh
      ./setup_autoui_server.sh
      ./run_autoui_server.sh
      ```
   - **Clients**: Model clients live in `./framework/models`, which handle action grounding and trajectory collection.
   - **Configuration**: After starting the server, update the corresponding `API_URL` fields for each agent in `config.yaml`.

Notes:
- **Hardware Requirements**: CogAgent and GUI-Odyssey require significant resources. Hosting them typically demands a GPU-equipped server.
- **Official Repositories**: Depending on your system setup, you may need to make minor adjustments to the provided scripts. For detailed setup instructions and model-specific guidance, please refer to the official repositories:
     - AutoUI: https://github.com/cooelf/Auto-GUI
     - DigiRL: https://github.com/DigiRL-agent/digirl
     - CogAgent: https://github.com/THUDM/CogVLM
     - GUI-Odyssey: https://github.com/OpenGVLab/GUI-Odyssey/blob/master/Quickstart.md
   

## Running the Script

Activate your environment and start benchmarking with:

```sh
conda activate Smartphone-Agent-Benchmark
python run.py --agent AppAgent
```

### Arguments for `run.py`

Below are the descriptions for the optional arguments you can use with `run.py`:

- `--agents`: Specifies the agents to be used. List multiple agents by separating them with commas. For example: `--agents AppAgent,MobileAgent,MobileAgentV2`.
- `--mode`: Choose from `full` (execution + evaluation) / `exec` (execution only) / `eval` (evaluation only).
- `--session_id`: Provides an ID for an isolated benchmark session.
- `--task_id`: Defines the specific task to be executed or evaluated. Iterates all tasks if omitted.
- `--no_concurrent`: Disables concurrent evaluation. Note that enabling concurrency may result in hitting API rate limits.
- `--skip_key_components`: Disables key components matching. It is recommended for use when running new single-app tasks beyond those provided in this benchmark, which has been annotated with key components.
- `--reasoning_mode`: Choose from `result_only` (MLLM evaluator only gives 0 or 1) / `direct` (MLLM evaluator gives reasoning thoughts before the results)
- `--action_mode`: Choose from `no_action` / `with_action` (image-based actions) / `text_action` (textual actions)


### Benchmark Session

Each session ID creates a benchmark folder in `./results`.
Upon initialization, the dataset located at `DATASET_PATH` is duplicated to this folder as `results.csv` to track progress and store results.
From this point forward, all operations will read from and write to this folder, ceasing any further reads from `DATASET_PATH`.
Re-running the same session ID allows you to resume from any incomplete executions or evaluations.

The session folder has structure as follows:

```
├── <task_id_1>
│   ├── <agent_name_1>
│   │   ├── log.json
│   │   ├── 0.png
│   │   ├── 1.png
│   │   ...
│   ├── <agent_name_2>
│   │   ├── log.json
│   │   ├── 0.png
│   │   ├── 1.png
│   │   ...
│   │── 0.png
│   │── 1.png
│   ...
├── <task_id_2>
│   ...
├── results.csv
```

Running execution and evaluation with agents will output log files and screenshot trajectories to `<session-folder>/<task_id>/<agent_name>/`.
This benchmark also supports evaluation without an agent (e.g., handcrafted trajectory). In such cases, screenshot trajectories should be placed in `<session-folder>/<task_id>/`.

### Adding New Agents

Our benchmark is designed to be easily extendable, allowing the addition of new agents. To add a new agent, follow these steps:

1. Update Configuration: Append the new agent's configuration to the `config.yaml` file.
2. Implement Agent Class: Implement an agent class in `src/agents.py` to handle the initialization and execution of tasks from the new agent's repository.
3. Modify Main Script for Evaluation: Ensure the main script for the new agent outputs screenshot trajectories (`0.png`,`1.png`, ...) or any log file (`log.json`) to the specified destination using `output_dir`.
4. Configure Agent Environment (Optional): Add the environment requirement file to `./requirements` and update `setup.sh` to include any necessary setup steps.
5. Exit Codes for Execution (Optional): To allow the framework to accurately capture the completion of agent execution, exit the program with code 0 upon success and code 1 upon any failure.

The `setup.sh` script will create a separate conda environment for each agent to avoid conflicts in Python versions and package dependencies. This ensures that each agent operates in an isolated environment, preventing any compatibility issues.

## Additional Information

- Make sure that your Android device or emulator is properly connected and recognized by adb. You can check this by running:

  ```sh
  adb devices
  ```

  This command should list your connected devices.

- If you encounter any issues during setup, ensure that your adb is correctly installed and configured, and that your conda environment is properly set up.

## Contact

For any questions or issues, please open an issue on the GitHub repository.
