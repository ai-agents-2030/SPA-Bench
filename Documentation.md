# 🌿🪑 SPA-Bench Documentation

## Guidelines

### Prerequisites

1. Ensure that `conda` is available on your system. You can download it from the [conda.io website](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).
2. Download and install the [Android Debug Bridge (adb)](https://developer.android.com/tools/adb) on your PC. This command-line tool allows you to communicate with your Android device from your PC. After installation, add the adb tool to your system's environment variables.

### Setup

1. **Using a Physical Android Device:**

   - Obtain an Android device.
   - Enable USB debugging by going to `Settings` > `Developer Options` > `USB debugging`. If Developer Options is not visible, go to `Settings` > `About phone` and tap on `Build number` seven times to enable it.
   - Connect your Android device to your PC using a USB cable.

2. **Using an Android Emulator:**

   - If you do not have access to a physical Android device, download and install [Android Studio](https://developer.android.com/studio).
   - Use the emulator that comes with Android Studio. You can access the emulator via the Device Manager in Android Studio.
   - To install apps on the emulator, download the APK files from the internet and drag them onto the emulator window.

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

3. Update Configuration:

   Before running the script, rename `config.yaml.example` to `config.yaml`, then open the `config.yaml` file and modify any configuration keys or file paths according to your setup. Ensure that all necessary configurations are correctly specified for your environment.

4. Update Environment:

   Please (copy and) rename `.env.example` as `.env` to store necessary environment variable.

5. (Optional)

   If you want to evaluate CogAgent, follow the steps in `./framework/models/CogAgent/README.md` to deploy the model in a GPU server.
   If you want to evaluate GUI-Odyssey, follow the steps in `./framework/models/GUI-Odyssey/README.md` to deploy the model in a GPU server.
   If you want to evaluate Mobile-Agent-v2 without the official Qwen API, follow the steps in `./framework/self_hosted_vlm/README.md` to deploy the model on a GPU server to obtain an API URL. Then, fill in the `QWEN_API_URL` field in the `.env` file with this URL, and set the `QWEN_API_KEY` to `self_hosted`.

## Running the Script

To run the main script, execute the following sample command:

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
- `--skip_key_components`: Disable key components matching.
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
