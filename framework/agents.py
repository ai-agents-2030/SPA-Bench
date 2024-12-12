import subprocess
import os
from . import utils
import shutil
from collections import namedtuple


class BaseAgent:
    """This is an abstract class for base agent.

    Attributes:
    agent_name (str): The name of the agent.
    default_adb_keyboard (bool): Whether the agent should use ADBKeyboard by default.
    config (dict): The configuration loaded from config.yaml.
    agent_config (dict): The specific configuration for this agent.
    repo_abs_path (str): The absolute path to the repository of this agent.
    """

    agent_name = ""
    default_adb_keyboard = False

    def __init__(self, config):
        # config loaded from config.yaml
        self.config = config
        self.agent_config = utils.get_agent_config(self.config, self.agent_name)
        self.repo_abs_path = os.path.join(os.getcwd(), self.agent_config["REPO_PATH"])
        super().__init__()

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        """Abstract method to construct and return a command string to execute the agent's Python
        code.

        Parameters:
        - task (namedtuple): A named tuple containing task information.
        - full_task_description (str): The modified task description to be sent to agents.
        - output_dir (str): The directory where the output should be saved.
        - device (dict) : The android device.

        Returns:
        - tuple[str, str]: A command string and its arguments to run the agent's Python code.

        Note: This method should be overridden in subclasses to provide the specific command required
        for executing the agent's code.
        """
        raise Exception("NOT IMPLEMENTED")

    def setup_keyboard(self, device_serial, task_lang):
        if task_lang == "CHN" or self.default_adb_keyboard:
            utils.set_adb_keyboard(device_serial)
        else:
            utils.set_default_keyboard(device_serial, self.config["DEFAULT_KEYBOARD_PACKAGE"])

    def execute_task(self, task: namedtuple, device: dict, capture_stdout=True) -> tuple[bool, int]:
        """Executes the task by constructing the command and running it in a subprocess.

        Parameters:
        - task (namedtuple): A named tuple with the following fields:
            - task_identifier (str)
            - task_app (str)
            - adb_app (str)
            - adb_home_page (str)
            - task_language (str)
            - task_description (str)
            - task_difficulty  (int)
            - golden_steps (int)
            - key_component_final (List[str])
            - is_cross_app (str)
        - device (dict) : The android device:
            - serial (str)
            - console_port (int): is None if the device is not an emulator set up by this framework
            - grpc_port (int): is None if the device is not an emulator set up by this framework
        - capture_stdout (bool): Whether to capture stdout and stderr from subprocess using subprocess.PIPE

        Returns:
        - tuple[bool, int]:
            - boolean indicates whether task is completed
            - exit_code:
                0 - Finished, no rerun (Task completed)
                1 - Unexpected error, rerun decision needed (Task incomplete)
                2 - Expected error, no rerun (Task completed)
                3 - Expected error, rerun required (Task incomplete)
                4 - Max rounds reached, no rerun (Task completed)
        """
        self.setup_keyboard(device["serial"], task.task_language)

        is_linux = os.name == "posix"
        if is_linux:
            env = f"""source activate && conda deactivate && conda activate {self.agent_config['ENV_NAME']}"""
        else:
            env = f"""conda activate {self.agent_config['ENV_NAME']}"""
        output_dir = self.setup_task_output_directory(task.task_identifier)
        full_task_description = task.task_description
        if task.is_cross_app == "N":
            if task.task_language == "ENG":
                full_task_description = f'This is the opened app "{task.task_app}". {task.task_description}'
            elif task.task_language == "CHN":
                full_task_description = f'这是已打开的"{task.task_app_CHN}"应用程序，{task.task_description}'
        script, args = self.construct_command(task, full_task_description, output_dir, device)
        command = f"{env} && python {script} {args}"

        print(command)
        if is_linux:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.repo_abs_path,
                executable="/bin/bash",
                stdout=subprocess.PIPE if capture_stdout else None,
                stderr=subprocess.PIPE if capture_stdout else None,
            )
        else:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.repo_abs_path,
                stdout=subprocess.PIPE if capture_stdout else None,
                stderr=subprocess.PIPE if capture_stdout else None,
            )

        stdout, stderr = process.communicate()

        if stdout:
            stdout = safe_decode(stdout).replace("\r\n", "\n")  # CRLF to LF

        if stderr:
            stderr = safe_decode(stderr).replace("\r\n", "\n")  # CRLF to LF

        if stdout:
            with open(output_dir + "/stdout.txt", "w", encoding="utf-8") as file:
                file.write(f"<{self.agent_name}>\n")
                file.write(stdout)
        if stderr:
            with open(output_dir + "/stderr.txt", "w", encoding="utf-8") as file:
                file.write(f"<{self.agent_name}>\n")
                file.write(stderr)

        return (process.returncode in [0, 2, 4], process.returncode)

    def setup_task_output_directory(self, task_id: str) -> str:
        """Sets up the output directory for the agent's task.

        Parameters:
        - task_id (str): The unique identifier for the task.

        Returns:
        - str: The path to the output directory.

        This method ensures the output directory is cleaned before creating a new one if needed.
        """
        task_output_dir = os.path.join(self.config["output_dir"], task_id)
        if not os.path.exists(task_output_dir):
            os.mkdir(task_output_dir)
        output_dir = os.path.join(task_output_dir, self.agent_name)
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        else:
            shutil.rmtree(output_dir)
            os.mkdir(output_dir)
        return output_dir


def safe_decode(byte_data, encoding_list=["utf-8", "gbk"]):
    for encoding in encoding_list:
        try:
            return byte_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"Unable to decode with encodings: {encoding_list}")


class AppAgent(BaseAgent):
    agent_name = "AppAgent"

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "scripts/task_executor.py"
        # TODO: Escaping double quotes works for Windows Only, use '\' as escape characters otherwise

        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f"""--openai_api_key {self.config['OPENAI_API_KEY']} """
            f"""--task "{full_task_description.replace('"', '""')}" """
            f'--app "{task.task_app}" '
            f'--lang "{task.task_language}" '
            f'--output_dir "{output_dir}" '
            f"--root_dir ./ "
            f"--max_rounds {max_rounds} "
            f"""--device {device['serial']} """
        )
        if self.config["OPENAI_API_MODEL"]:
            args += f"""--openai_api_model "{self.config['OPENAI_API_MODEL']}" """
        return script, args


class AutoDroid(BaseAgent):
    agent_name = "AutoDroid"

    def execute_task(self, task: namedtuple, device: dict, capture_stdout=False) -> tuple[bool, int]:
        return super().execute_task(task, device, capture_stdout)

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "start.py"
        tmp_dir = "./tmp"  # TODO: 通过重载 def execute_task(self, task: namedtuple): 在执行完之后删除tmp文件夹
        os.makedirs(tmp_dir, exist_ok=True)
        # to absolute path
        tmp_dir = os.path.abspath(tmp_dir)
        task_apk_path = os.path.join(tmp_dir, task.adb_app + ".apk")
        autodroid_tmp_dir = os.path.join(
            tmp_dir, f"autodroid_tmp_{device['serial'].replace(':', '_')}"
        )  # support multiple devices
        if os.path.exists(autodroid_tmp_dir):
            shutil.rmtree(autodroid_tmp_dir)
        os.makedirs(autodroid_tmp_dir, exist_ok=True)

        if not os.path.exists(task_apk_path):
            print(f"Extracting apk to: {task_apk_path}, this may take a while...")
            res = utils.get_apk(device["serial"], task.adb_app, task_apk_path)
            if os.path.exists(task_apk_path):
                print(f"APK extracted to: {task_apk_path}")
            assert res != "ERROR"

        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f""" -task "{full_task_description.replace('"', '""')}" """
            f' -a "{task_apk_path}" '
            f' -benchmark_output_dir "{output_dir}" '
            f' -o "{autodroid_tmp_dir}" '
            f" -max_rounds {max_rounds} "
            f" -keep_app "
            f""" -d {device['serial']} """
        )
        if "emulator" in device["serial"]:
            args += " -is_emulator "
        if self.config["OPENAI_API_MODEL"]:
            args += f""" -openai_api_model "{self.config['OPENAI_API_MODEL']}" """
        return script, args


class CogAgent(BaseAgent):
    agent_name = "CogAgent"

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "main.py"
        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f""" -task "{full_task_description.replace('"', '""')}" """
            f' -benchmark_output_dir "{output_dir}" '
            f" -max_rounds {max_rounds} "
            f""" -device {device['serial']} """
            f" -model_api_url {self.agent_config['API_URL']} "
        )
        return script, args


class GUI_Odyssey(BaseAgent):
    agent_name = "GUI_Odyssey"

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "main.py"
        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f""" -task "{full_task_description.replace('"', '""')}" """
            f' -benchmark_output_dir "{output_dir}" '
            f" -max_rounds {max_rounds} "
            f""" -device {device['serial']} """
            f" -model_api_url {self.agent_config['API_URL']} "
        )
        return script, args


class MobileAgent(BaseAgent):
    agent_name = "MobileAgent"
    default_adb_keyboard = True

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "run.py"
        # TODO: Escaping double quotes works for Windows Only, use '\' as escape characters otherwise

        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f"""--api {self.config['OPENAI_API_KEY']} """
            f"""--instruction "{full_task_description.replace('"', '""')}" """
            f'--lang "{task.task_language}" '
            f'--output_dir "{output_dir}" '
            f"""--adb_path "{self.config['ADB_PATH']}" """
            f"--max_rounds {max_rounds} "
            f"""--device {device['serial']} """
        )
        if self.config["OPENAI_API_MODEL"]:
            args += f"""--openai_api_model "{self.config['OPENAI_API_MODEL']}" """
        return script, args


class MobileAgentV2(BaseAgent):
    agent_name = "MobileAgentV2"
    default_adb_keyboard = True

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "run.py"
        # TODO: Escaping double quotes works for Windows Only, use '\' as escape characters otherwise

        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f"""--openai_api_key {self.config['OPENAI_API_KEY']} """
            f"""--qwen_api_key {self.config['QWEN_API_KEY']} """
            f"""--instruction "{full_task_description.replace('"', '""')}" """
            f'--lang "{task.task_language}" '
            f'--output_dir "{output_dir}" '
            f"""--adb_path "{self.config['ADB_PATH']}" """
            f"--max_rounds {max_rounds} "
            f"""--device {device['serial']} """
        )
        if self.config["OPENAI_API_MODEL"]:
            args += f"""--openai_api_model "{self.config['OPENAI_API_MODEL']}" """
        return script, args


class AndroidWorldAgent(BaseAgent):
    agent_name = ""

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "benchmark_run.py"

        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1

        # TODO: Escaping double quotes works for Windows Only, use '\' as escape characters otherwise
        args = (
            f"""--openai_api_key {self.config['OPENAI_API_KEY']} """
            f"""--task "{full_task_description.replace('"', '""')}" """
            f'--lang "{task.task_language}" '
            f'--output_dir "{output_dir}" '
            f"""--adb_path "{self.config['ADB_PATH']}" """
            f"--max_rounds {max_rounds} "
            f'--agent "{self.agent_name}" '
            f"""--device_console_port {device['console_port']} """
            f"""--device_grpc_port {device['grpc_port']} """
        )
        if self.config["OPENAI_API_MODEL"]:
            args += f"""--openai_api_model "{self.config['OPENAI_API_MODEL']}" """
        return script, args


class M3A(AndroidWorldAgent):
    agent_name = "M3A"


class T3A(AndroidWorldAgent):
    agent_name = "T3A"


class SeeAct(AndroidWorldAgent):
    agent_name = "SeeAct"


class AutoUI(BaseAgent):
    agent_name = "AutoUI"

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "task_executor.py"
        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f""" -task "{full_task_description.replace('"', '""')}" """
            f' -benchmark_output_dir "{output_dir}" '
            f" -max_rounds {max_rounds} "
            f""" -device {device['serial']} """
            f" -model_api_url {self.agent_config['API_URL']} "
        )
        return script, args


class DigirlAgent(BaseAgent):
    agent_name = "DigirlAgent"

    def construct_command(
        self, task: namedtuple, full_task_description: str, output_dir: str, device: dict
    ) -> tuple[str, str]:
        script = "task_executor.py"
        max_rounds = self.config["MAX_ROUNDS"]
        if not max_rounds:
            max_rounds = task.golden_steps * 2 + 1
        args = (
            f""" -task "{full_task_description.replace('"', '""')}" """
            f' -benchmark_output_dir "{output_dir}" '
            f" -max_rounds {max_rounds} "
            f""" -device {device['serial']} """
            f" -model_api_url {self.agent_config['API_URL']} "
        )
        return script, args
