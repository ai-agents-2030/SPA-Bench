import pandas as pd
from . import agents
import subprocess
import os
import shutil
import json
import time
import re
from filelock import FileLock
from functools import wraps
from datetime import datetime


def get_apk(device_serial: str, package_name: str, local_apk_path: str):
    adb_command = f"adb -s {device_serial} shell pm path {package_name}"
    apk_path = execute_adb(adb_command)
    if apk_path == "ERROR":
        return "ERROR"
    apk_path = apk_path.split("package:")[1].strip()
    adb_command = f"adb -s {device_serial} pull {apk_path} {local_apk_path}"
    return execute_adb(adb_command)


def get_agent(agent_name):
    try:
        return getattr(agents, agent_name)
    except AttributeError:
        raise Exception(f"Required agent <{agent_name}> not implemented.")


def get_agent_config(config, agent_name):
    for agent in config["AGENTS"]:
        if agent["NAME"] == agent_name:
            return agent
    raise Exception("INVALID agent_name")


def execute_adb(adb_command, verbose=True):
    result = subprocess.run(adb_command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    if verbose:
        print(f"Command execution failed: {adb_command}")
        print(result.stderr)
    return "ERROR"


def get_all_devices():
    adb_command = "adb devices"
    device_list = []
    result = execute_adb(adb_command)
    if result != "ERROR":
        devices = result.split("\n")[1:]
        for d in devices:
            device_list.append(d.split()[0])

    return device_list


def setup_devices():
    devices = get_all_devices()
    print(f"{len(devices)} device(s) found: {devices}")
    if len(devices) == 0:
        exit(1)
    elif len(devices) > 1:
        ans = input("Are you sure to run using all devices? (y/n)")
        if ans.strip().lower() != "y":
            exit(1)
    return [{"serial": serial, "console_port": None, "grpc_port": None} for serial in devices]


def setup_avd(avd_home, source_avd_home, source_avd_name, num_of_copies, target_sdk_path):
    from .utils_clone_avd import clone_avd

    for idx in range(num_of_copies):
        clone_avd(
            src_avd_dir=os.path.join(source_avd_home, source_avd_name + ".avd"),
            src_ini_file=os.path.join(source_avd_home, source_avd_name + ".ini"),
            src_avd_name=source_avd_name,
            tar_avd_name=f"{source_avd_name}_{idx}",
            src_android_avd_home=r"C:\Users\User\.android\avd",
            tar_android_avd_home=avd_home,
            src_sdk=r"C:\Users\User\AppData\Local\Android\Sdk",
            tar_sdk=target_sdk_path,
            target_linux=os.name == "posix",
        )


def parse_adb_devices(res) -> dict:
    devices = {}
    for line in res.split("\n")[1:]:
        serial, status = line.split("\t")
        devices[serial] = status
    return devices


def setup_emulator(emulator_exe, source_avd_name, num_of_emulators):
    devices = [
        {"serial": f"emulator-{5554 + (idx * 2)}", "console_port": 5554 + (idx * 2), "grpc_port": 8554 + (idx * 2)}
        for idx in range(num_of_emulators)
    ]
    devices_serial = [device["serial"] for device in devices]
    ready_devices = []
    for idx, device in enumerate(devices):
        command = [
            emulator_exe,
            "-avd",
            f"{source_avd_name}_{idx}",
            "-no-snapshot-save",
            "-no-window",
            "-no-audio",
            "-port",
            str(device["console_port"]),
            "-grpc",
            str(device["grpc_port"]),
        ]
        http_proxy = os.environ.get("HTTP_PROXY")
        if http_proxy:
            command.extend(["-http-proxy", http_proxy])
        subprocess.Popen(
            command,
            shell=True,
            text=True,
            stdout=subprocess.DEVNULL,  # to silence emulator output
            # keep any error output
        )
    adb_command = "adb devices"
    while True:
        result = execute_adb(adb_command)
        if result == "ERROR":
            raise Exception("Error in executing ADB command")
        else:
            launched_devices = [
                serial
                for serial, status in parse_adb_devices(result).items()
                if status == "device" and serial in devices_serial
            ]
            print(
                f"{len(launched_devices)}/{num_of_emulators} device(s) launched; {len(ready_devices)}/{num_of_emulators} device(s) ready"
            )
            if len(launched_devices) == num_of_emulators:
                break
            else:
                time.sleep(1)
    while True:
        for serial in launched_devices:
            if serial in ready_devices:
                continue
            result = execute_adb(f"adb -s {serial} shell getprop sys.boot_completed")
            if result == "1":
                ready_devices.append(serial)
        print(
            f"{len(launched_devices)}/{num_of_emulators} device(s) launched; {len(ready_devices)}/{num_of_emulators} device(s) ready"
        )
        if len(ready_devices) == num_of_emulators:
            break
        else:
            time.sleep(1)

    return devices


def terminate_emulator(serial_list):
    for serial in serial_list:
        execute_adb(f"adb -s {serial} emu kill")


def setup_app_activity(device_serial: str, adb_app: str, adb_home_page: str) -> bool:
    """Open the home page of the target app. Go to home-screen if failed or no info is given.

    Parameters:
    - device_serial (str): The android device serial number.
    - adb_app (str): The application package name.
    - adb_home_page (str): The activity class name.

    Returns:
    - bool: Whether the home page is successfully opened.
    """
    # Close app
    close_app_activity(device_serial, adb_app)

    # Start app
    launched = False
    if adb_app and adb_home_page:
        output = execute_adb(
            f"adb -s {device_serial} shell am start -n {adb_app}/{adb_home_page}",
            verbose=False,
        )
        if output != "ERROR":
            launched = True
    if not launched and adb_app:
        output = execute_adb(f"adb -s {device_serial} shell monkey -p {adb_app} -c android.intent.category.LAUNCHER 1")
        if output != "ERROR":
            launched = True
    if launched:
        max_retry = 30
        trial = 0
        while trial < max_retry:
            windows = execute_adb(
                f'adb -s {device_serial} shell "dumpsys window | grep -E mCurrentFocus"',
                verbose=False,
            )
            if windows == "ERROR":
                break
            m = re.search(
                r"mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\}",
                windows,
            )
            if m and m.group("package") == adb_app:
                break
            else:
                time.sleep(1)
                trial += 1
        time.sleep(10)  # For loading app content
        return True
    else:
        execute_adb(f"adb -s {device_serial} shell input keyevent KEYCODE_HOME")
        print(f"10 seconds are allowed to start the app `{adb_app}/{adb_home_page}` on {device_serial} manually:")
        time.sleep(10)
        return False


def close_app_activity(device_serial: str, adb_app: str = None, kill_every_task: bool = True) -> bool:
    """Kill every app.

    Parameters:
    - device_serial (str): The android device serial number.
    - adb_app (str): The application package name.

    Returns:
    - bool: Whether the app is successfully closed.
    """
    if kill_every_task:
        execute_adb(
            '''adb -s {{device_serial}} shell "dumpsys activity | grep topActivity | sed -n 's/.*{\\([^\\/]*\\)\\/.*/\\1/p' | while read -r package; do am force-stop $package; done"'''.replace(
                "{{device_serial}}", device_serial
            )
        )
    # Kill specific app
    if adb_app:
        output = execute_adb(f"adb -s {device_serial} shell am force-stop {adb_app}")
        if output != "ERROR":
            time.sleep(5)
            return True
    return False


def set_adb_keyboard(device_serial):
    execute_adb(f"adb -s {device_serial} shell ime enable com.android.adbkeyboard/.AdbIME")
    execute_adb(f"adb -s {device_serial} shell ime set com.android.adbkeyboard/.AdbIME")


def set_default_keyboard(device_serial, package):
    execute_adb(f"adb -s {device_serial} shell ime set {package}")


def setup_output_directory(results_dir: str, session_id: str, overwrite_session: bool) -> str:
    output_dir = os.path.join(results_dir, f"session-{session_id}")

    if os.path.exists(output_dir):
        if overwrite_session:
            # Directory exists, prompt the user
            response = (
                input(
                    f"The results session <{session_id}> already exists. Do you want to erase its contents and restart the session? (y/n): "
                )
                .strip()
                .lower()
            )
            if response in ["yes", "y"]:
                # Erase the contents
                for item in os.listdir(output_dir):
                    item_path = os.path.join(output_dir, item)
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
            else:
                pass
        else:
            pass
    else:
        # Create the directory
        os.makedirs(output_dir)
    return output_dir


def get_results_csv_path(output_dir: str) -> str:
    return os.path.join(output_dir, "results.csv")


def get_exec_json_path(output_dir: str, task_id: str, agent_name: str, content: str) -> str:
    return os.path.join(output_dir, task_id, agent_name, f"{content}.json")


def with_filelock():
    """Decorator to add a simple file lock context to the wrapped function using the 'output_dir'
    argument.

    Returns:
    - A decorated function with a file lock.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract the output_dir argument from function arguments
            output_dir = kwargs.get("output_dir") or next(
                (arg for arg_name, arg in zip(func.__code__.co_varnames, args) if arg_name == "output_dir"), None
            )

            if not output_dir:
                raise ValueError("Lock path argument output_dir is required.")

            csv_path = get_results_csv_path(output_dir)
            lock = FileLock(csv_path + ".lock")

            start_time = datetime.now()
            with lock:
                print("Time taken to get lock:", datetime.now() - start_time)
                result = func(*args, **kwargs)
                return result

        return wrapper

    return decorator


def try_save_csv(dataframe: pd.DataFrame, path: str, max_retry: int = 5, retry_interval: int = 5) -> bool:
    counter = 0
    while True:
        try:
            dataframe.to_csv(path, encoding="utf-8", index=False)
        except Exception as err:
            print("Failed to save to ", path)
            print(str(err))
            if counter < max_retry:
                counter += 1
                print(f"Retry in {retry_interval} seconds; {counter}/{max_retry}")
                time.sleep(retry_interval)
                continue
            else:
                return False
        return True


@with_filelock()
def setup_results_csv(
    output_dir: str, dataset_path: str, agent_list: list[str], reasoning_mode: str, action_mode: str
) -> pd.DataFrame:
    csv_path = get_results_csv_path(output_dir)
    if os.path.exists(csv_path):
        results_df = pd.read_csv(csv_path, encoding="utf-8")
        print("Loaded results.csv")
    else:
        results_df = pd.read_csv(dataset_path, encoding="utf-8")
        print("Created results.csv")
    # Initialize Agent columns
    for agent_name in agent_list:
        prefix = f"{agent_name}_" if agent_name else ""
        if agent_name:
            if f"{prefix}completion" not in results_df.columns:
                results_df[f"{prefix}completion"] = "N"
            if f"{prefix}device" not in results_df.columns:
                results_df[f"{prefix}device"] = "N"
            if f"{prefix}exit_code" not in results_df.columns:
                results_df[f"{prefix}exit_code"] = -1
            if f"{prefix}total_steps" not in results_df.columns:
                results_df[f"{prefix}total_steps"] = 0
            if f"{prefix}total_token_cost" not in results_df.columns:
                results_df[f"{prefix}total_token_cost"] = 0
            if f"{prefix}total_time" not in results_df.columns:
                results_df[f"{prefix}total_time"] = 0
            if f"{prefix}finish_signal" not in results_df.columns:
                results_df[f"{prefix}finish_signal"] = 0
            if f"{prefix}step_ratio" not in results_df.columns:
                results_df[f"{prefix}step_ratio"] = 0
            if f"{prefix}elapsed_time_initial" not in results_df.columns:
                results_df[f"{prefix}elapsed_time_initial"] = 0
            if f"{prefix}elapsed_time_exec" not in results_df.columns:
                results_df[f"{prefix}elapsed_time_exec"] = 0
            if f"{prefix}avg_prompt_tokens" not in results_df.columns:
                results_df[f"{prefix}avg_prompt_tokens"] = 0
            if f"{prefix}avg_completion_tokens" not in results_df.columns:
                results_df[f"{prefix}avg_completion_tokens"] = 0
            if f"{prefix}exec_error" not in results_df.columns:
                results_df[f"{prefix}exec_error"] = "N"
        if f"{reasoning_mode}_{action_mode}_{prefix}evaluation" not in results_df.columns:
            results_df[f"{reasoning_mode}_{action_mode}_{prefix}evaluation"] = "N"
        if f"{reasoning_mode}_{action_mode}_{prefix}details" not in results_df.columns:
            results_df[f"{reasoning_mode}_{action_mode}_{prefix}details"] = "{}"
    try_save_csv(results_df, csv_path)
    for agent_name in agent_list:
        prefix = f"{agent_name}_" if agent_name else ""
        results_df[f"{reasoning_mode}_{action_mode}_{prefix}details"] = results_df[
            f"{reasoning_mode}_{action_mode}_{prefix}details"
        ].apply(json.loads)
    return results_df.set_index("task_identifier", drop=False).fillna("")


@with_filelock()
def save_result__completed_execution(
    output_dir: str, task_id: str, agent_name: str, task_completed: bool, exit_code: int, device: str
) -> pd.DataFrame:
    csv_path = get_results_csv_path(output_dir)
    results_df = pd.read_csv(csv_path, encoding="utf-8")
    results_df = results_df.set_index("task_identifier", drop=False).fillna("")
    prefix = f"{agent_name}_" if agent_name else ""
    if task_completed:
        results_df.at[task_id, f"{prefix}completion"] = "Y"
    results_df.at[task_id, f"{prefix}device"] = device
    results_df.at[task_id, f"{prefix}exit_code"] = exit_code

    # parse log.json
    log_path = get_exec_json_path(output_dir, task_id, agent_name, "log")
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as file:
            log_json = json.load(file)[-1]
            results_df.at[task_id, f"{prefix}total_steps"] = log_json["total_steps"]
            results_df.at[task_id, f"{prefix}total_token_cost"] = round(
                5e-06 * log_json["total_prompt_tokens"] + 1.5e-05 * log_json["total_completion_tokens"],
                5,
            )  # based on gpt4o pricing
            results_df.at[task_id, f"{prefix}total_time"] = round(
                log_json["elapsed_time_initial"] + log_json["elapsed_time_exec"], 5
            )
            results_df.at[task_id, f"{prefix}finish_signal"] = log_json["finish_signal"]
            results_df.at[task_id, f"{prefix}step_ratio"] = round(
                log_json["total_steps"] / results_df.at[task_id, "golden_steps"], 5
            )
            results_df.at[task_id, f"{prefix}elapsed_time_initial"] = round(log_json["elapsed_time_initial"], 5)
            results_df.at[task_id, f"{prefix}elapsed_time_exec"] = round(log_json["elapsed_time_exec"], 5)
            results_df.at[task_id, f"{prefix}avg_prompt_tokens"] = round(
                log_json["total_prompt_tokens"] / (log_json["total_steps"] + 1), 5
            )  # +1 because last step had always been discarded in "total_steps"
            results_df.at[task_id, f"{prefix}avg_completion_tokens"] = round(
                log_json["total_completion_tokens"] / (log_json["total_steps"] + 1), 5
            )  # +1 because last step had always been discarded in "total_steps"

    results_df.at[task_id, f"{prefix}exec_error"] = "N"
    # parse error.json
    error_path = get_exec_json_path(output_dir, task_id, agent_name, "error")
    if os.path.exists(error_path):
        with open(error_path, encoding="utf-8") as file:
            error_json = json.load(file)[0]
            results_df.at[task_id, f"{prefix}exec_error"] = error_json["error_message"]

    try_save_csv(results_df, csv_path)


@with_filelock()
def save_result__completed_evaluation(
    output_dir: str,
    task_id: str,
    agent_name: str,
    success: bool,
    evaluation_detail: dict,
    reasoning_mode: str,
    action_mode: str,
) -> pd.DataFrame:
    csv_path = get_results_csv_path(output_dir)
    results_df = pd.read_csv(csv_path, encoding="utf-8")
    results_df = results_df.set_index("task_identifier", drop=False).fillna("")
    prefix = f"{agent_name}_" if agent_name else ""
    if success == 1:
        results_df.at[task_id, f"{reasoning_mode}_{action_mode}_{prefix}evaluation"] = "S"
    elif success == 0:
        results_df.at[task_id, f"{reasoning_mode}_{action_mode}_{prefix}evaluation"] = "F"
    elif success == -1:
        results_df.at[task_id, f"{reasoning_mode}_{action_mode}_{prefix}evaluation"] = "E"
    results_df.at[task_id, f"{reasoning_mode}_{action_mode}_{prefix}details"] = json.dumps(
        evaluation_detail, ensure_ascii=False
    )
    try_save_csv(results_df, csv_path)


def print_execution_summary(output_dir, agent_scope):
    results_df = pd.read_csv(get_results_csv_path(output_dir), encoding="utf-8")
    exit_code_columns = [
        col for col in results_df.columns if "exit_code" in col and "_".join(col.split("_")[:-2]) in agent_scope
    ]
    for exit_code_col in exit_code_columns:
        agent = "_".join(exit_code_col.split("_")[:-2])
        print(f"For <{agent}>:")
        for code, msg in zip(
            [0, 1, 2, 3, 4],
            [
                "Finished (no rerun)",
                "Unexpected error (decision needed)",
                "Expected error (no rerun)",
                "Expected error (rerun)",
                "Max rounds reached (no rerun)",
            ],
        ):
            print(f"# of tasks finished with exit code <{code} {msg}>: {(results_df[exit_code_col] == code).sum()}")

        if (results_df[exit_code_col] == 1).any():
            print(
                f"There's unexpected error for the following task(s). Please decide whether to re-run by modifying result.csv `{agent}_completion`"
            )
            for idx, task in results_df.loc[results_df[exit_code_col] == 1].iterrows():
                print(
                    f"Error message for <{task['task_identifier']}>:",
                    task[agent + "_exec_error"],
                )
    print()
