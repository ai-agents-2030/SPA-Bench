import os
import yaml
import argparse
import subprocess
import time
from dotenv import load_dotenv

from framework import utils
from concurrent_execution import run_task_with_multi_devices
from pipeline.evaluator import evaluator
from pipeline.cross_evaluator import cross_evaluator


load_dotenv(verbose=True, override=True)
with open("./config.yaml") as file:
    config = yaml.safe_load(file)

parser = argparse.ArgumentParser()
parser.add_argument("--agents", type=str, default="AppAgent")
parser.add_argument("--mode", type=str, default="full", choices=["full", "exec", "eval"])
parser.add_argument("--session_id", type=str, default=config["SESSION_ID"])
parser.add_argument("--task_id", type=str, default=None)
parser.add_argument("--no_concurrent", action="store_true")
parser.add_argument("--setup_avd", action="store_true")
parser.add_argument("--setup_emulator", action="store_true")
parser.add_argument("--skip_key_components", action="store_true")
parser.add_argument("--reasoning_mode", type=str, default="direct", choices=["result_only", "direct"])
parser.add_argument("--action_mode", type=str, default="with_action", choices=["no_action", "with_action", "text_action"])
parser.add_argument("--overwrite", action="store_true")
parser.add_argument("--overwrite_session", action="store_true")
args = parser.parse_args()

output_dir = utils.setup_output_directory(
    os.path.join(os.getcwd(), config["RESULTS_DIR"]), args.session_id, args.overwrite_session
)

result_overwrite = [args.overwrite]
print("Overwrite:", result_overwrite)

if args.mode in ("full", "exec"):
    if args.setup_avd:
        utils.setup_avd(
            config["SYS_AVD_HOME"],
            os.path.join(os.getcwd(), config["SOURCE_AVD_HOME"]),
            config["SOURCE_AVD_NAME"],
            config["NUM_OF_EMULATOR"],
            config["ANDROID_SDK_PATH"],
        )
        devices = utils.setup_emulator(config["EMULATOR_PATH"], config["SOURCE_AVD_NAME"], config["NUM_OF_EMULATOR"])
    elif args.setup_emulator:
        devices = utils.setup_emulator(config["EMULATOR_PATH"], config["SOURCE_AVD_NAME"], config["NUM_OF_EMULATOR"])
    else:
        devices = utils.setup_devices()
    if args.agents is None:
        # All agents as defined in config
        agent_scope = [agent_config["NAME"] for agent_config in config["AGENTS"]]
    else:
        agent_scope = args.agents.split(",")
        # Verify agent names
        for agent_name in agent_scope:
            utils.get_agent(agent_name)(config)
else:
    devices = [{}]
    agent_scope = [""]

results_df = utils.setup_results_csv(
    output_dir, config["DATASET_PATH"], agent_scope, args.reasoning_mode, args.action_mode
)
config["output_dir"] = output_dir
config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
config["QWEN_API_KEY"] = os.getenv("QWEN_API_KEY")


def run_task(agent_name, task, subprocess_list, device):
    prefix = f"{agent_name}_" if agent_name else ""
    if args.mode in ("full", "exec") and getattr(task, prefix + "completion") == "N":
        agent = utils.get_agent(agent_name)(config)
        print(f"Executing task: {task.task_identifier}")
        if task.is_cross_app == "N":
            utils.setup_app_activity(device["serial"], task.adb_app, task.adb_home_page)
        task_completed, task_exit_code = agent.execute_task(task, device)
        print(f"Finished task: {task.task_identifier}")
        utils.close_app_activity(device["serial"], task.adb_app if task.is_cross_app == "N" else None)
        utils.save_result__completed_execution(
            output_dir, task.task_identifier, agent_name, task_completed, task_exit_code, device["serial"]
        )
    else:
        task_completed = True

    if args.mode in ("full", "eval") and task_completed:
        # overwrite?
        if (
            not result_overwrite[0]
            and getattr(task, args.reasoning_mode + "_" + args.action_mode + "_" + prefix + "evaluation") != "N"
        ):
            # Directory exists, prompt the user
            response = (
                input(
                    f"The <{args.reasoning_mode}  + '_' + {args.action_mode}> evaluation result for task <{task.task_identifier}> already exists."
                    "Do you want to overwrite the result? (y/n): "
                )
                .strip()
                .lower()
            )
            if response in ["yes", "y"]:
                skip_response = (
                    input("Do you want to overwrite all the future results that exist? (y/n): ").strip().lower()
                )
                if skip_response in ["yes", "y"]:
                    result_overwrite[0] = True
            else:
                return

        # call evaluator
        if args.no_concurrent:
            print(f"Evaluating task: {task.task_identifier}")
            if task.is_cross_app == "Y":
                cross_evaluator(
                    task.task_identifier,
                    output_dir,
                    args.mode,
                    agent_name,
                )
            else:
                evaluator(
                    task.task_identifier,
                    output_dir,
                    args.skip_key_components,
                    args.reasoning_mode,
                    args.action_mode,
                    args.mode,
                    agent_name,
                )
        else:
            if task.is_cross_app == "Y":
                command = (
                    f"python {os.path.join(os.getcwd(),'pipeline/evaluator.py')} "  # NOTE: try to fix file not found error
                    f"--task_identifier {task.task_identifier} "
                    f"--result_dir {output_dir} "
                    f"--mode {args.mode} "
                )
                if agent_name:
                    command += f"--agent {agent_name} "
            else:
                command = (
                    f"python {os.path.join(os.getcwd(),'pipeline/evaluator.py')} "  # NOTE: try to fix file not found error
                    f"--task_identifier {task.task_identifier} "
                    f"--result_dir {output_dir} "
                    f"--reasoning_mode {args.reasoning_mode} "
                    f"--action_mode {args.action_mode} "
                    f"--mode {args.mode} "
                )
                if args.skip_key_components:
                    command += "--skip_key_components "
                if agent_name:
                    command += f"--agent {agent_name} "

            while len(subprocess_list) >= config["MAX_EVAL_SUBPROCESS"]:
                # Check which processes have finished
                for process in subprocess_list:
                    if process.poll() is not None:  # Process has finished
                        subprocess_list.remove(process)

                # Pause for a short time before checking again
                print("Reached max # of subprocess, wait 5 seconds")
                time.sleep(5)

            print(f"Evaluating task concurrently: {task.task_identifier} {args.reasoning_mode} {args.action_mode}")
            process = subprocess.Popen(command, text=True, shell=True)  # NOTE: try to fix file not found error
            subprocess_list.append(process)
            time.sleep(0.5)


subprocess_list = []  # a list to store any concurrent subprocess
if args.task_id is None:
    task_scope = list(results_df.itertuples(index=False))
else:
    task_scope = list(results_df.loc[[args.task_id]].itertuples(index=False))

# Loop every agent and task (and device)
if len(devices) > 1:
    task_arg_list = [(agent_name, task, subprocess_list) for agent_name in agent_scope for task in task_scope]
    run_task_with_multi_devices(run_task, task_arg_list, devices)
else:
    for agent_name in agent_scope:
        for task in task_scope:
            run_task(agent_name, task, subprocess_list, devices[0])

# Terminates all emulators
if args.setup_avd or args.setup_emulator:
    utils.terminate_emulator([device["serial"] for device in devices])
if args.mode != "eval":
    print("All execution completed.")
    if args.task_id is None:
        utils.print_execution_summary(output_dir, agent_scope)

# Wait for all subprocesses to complete
for process in subprocess_list:
    process.wait()
if args.mode != "exec":
    print("All evaluation finished.")
