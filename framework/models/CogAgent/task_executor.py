from gradio_client import Client, handle_file
from PIL import Image
from device import Device
import argparse
import os
import json
import time
import sys


OUTPUT_DIR = "./results"
def print_and_log_error(error_message):
    print(error_message)
    error_log = [{"error_message": error_message}]
    filename = OUTPUT_DIR + "/error.json"
    # Check if the file already exists
    if not os.path.exists(filename):
        # If the file does not exist, create it and write the JSON data
        with open(filename, "w", encoding="utf-8") as logfile:
            json.dump(error_log, logfile, ensure_ascii=False)


class CogAgentModelClient:
    def __init__(self, model_api_url: str):
        self.client = Client(model_api_url, verbose=False)

    def chat_with_image(self, query: str, image_path: str):
        text_response, input_token_len, output_token_len = self.client.predict(
            query=query,
            image_or_path=handle_file(image_path),
            api_name="/predict",
        )
        return text_response, input_token_len, output_token_len


def parse_action(response: str):
    raw_action = response
    try:
        raw_action = raw_action.split("Grounded Operation:")[1]
        action = raw_action.split(" ")[0]
        if action == "tap":
            numbers = raw_action.split("[[")[1].split(",")
            x = int(numbers[0])
            y = int(numbers[1].split("]]")[0])
            touch_point = (x / 1000, y / 1000)  # Relative coordinates of the screen
            return "tap", touch_point
        elif "type" in action:
            text = raw_action.split('"')[1]
            return "type", text
        elif "press home" in raw_action:
            return "press home", None
        elif "press back" in raw_action:
            return "press back", None
        elif "press enter" in raw_action:
            return "press enter", None
        elif "task complete" in raw_action:
            return "task complete", None
        elif "task impossible" in raw_action:
            return "task impossible", None
        elif "swipe up" in raw_action:
            return "swipe up", None
        elif "swipe down" in raw_action:
            return "swipe down", None
        elif "swipe left" in raw_action:
            return "swipe left", None
        elif "swipe right" in raw_action:
            return "swipe right", None
        else:
            print(f"Action {raw_action} not supported yet.")
            return "idle", None
    except Exception as e:
        print(f"Action {raw_action} Parsing Error: {e}")
        return "idle", None


def process_image_without_resize(image_or_path: Image.Image):
    pil_image = image_or_path
    if isinstance(image_or_path, str):
        pil_image = Image.open(image_or_path).convert("RGB")
    return pil_image


class CogAgent:
    prompt_template = 'What steps do I need to take to "{}"? (note: {} ) (with grounding)'
    def __init__(
        self,
        model_api_url: str,
        max_rounds: int = 20,
        device: str = None,
    ):
        self.model_api_url = model_api_url
        self.max_rounds = max_rounds
        self.android_device_serial = device

        self.__inited = False

    def __init(self):
        if self.__inited:
            return

        self.android_device = Device(self.android_device_serial)
        self.android_device.connect()
        self.screen_width, self.screen_height = self.android_device.get_screen_size()

        self.model_client = CogAgentModelClient(self.model_api_url)

        self.__inited = True

    def __del__(self):
        if self.__inited:
            self.android_device.disconnect()

    def chat_with_image(self, text: str, image_path: str):
        out = self.model_client.chat_with_image(text, image_path)
        return out

    def execute_task(self, task: str, log_dir: str = "results"):
        start_time_initial = time.time()
        self.__init()
        os.makedirs(log_dir, exist_ok=True)
        action_cnt = 0
        benchmark_log = []
        error_code = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        end_time_initial = time.time()
        elapsed_time_initial = end_time_initial - start_time_initial
        task_complete = False
        start_time_exec = time.time()
        try:
            while action_cnt < self.max_rounds:
                time.sleep(5) # sleep between steps
                action_cnt += 1
                print(f"\naction {action_cnt}")

                screenshot = self.android_device.get_screenshot()
                screenshot_path = os.path.join(log_dir, f"{action_cnt-1}.png")
                screenshot.save(screenshot_path)
                is_keyboard_shown = self.android_device.is_keyboard_shown()
                prompt = self.prompt_template.format(
                    task,
                    f'{"keyboard is activated" if is_keyboard_shown else "keyboard is not activated, if you want to type text, please tap the text input box first."}',
                )

                print(f"prompt: {prompt}")
                response, input_token_len, output_token_len = self.chat_with_image(
                    prompt, screenshot_path
                )

                total_prompt_tokens += input_token_len
                total_completion_tokens += output_token_len
                print(f"response: {response}")
                print(
                    f"prompt tokens: {input_token_len}, completion tokens: {output_token_len}"
                )

                action_type, action_content = parse_action(response)
                action_log = [
                    action_type,  # action type
                    {
                        "detail_type": "string",  # "string" or "coordinates"
                        "detail": "",  # "Task completed." or [x, y] or f"The text \"{input_str}\" has been inputted."
                        # or f"The coordinates ({x},{y}) have been swiped to the {swipe_direction}."
                        # or f"The swipe action has been performed starting from coordinates ({start_x},{start_y}) to ({end_x},{end_y})."
                    },
                ]  # second element for action details based action_type

                if action_type == "idle":
                    continue
                elif action_type == "tap":
                    device_x, device_y = int(
                        action_content[0] * self.screen_width
                    ), int(action_content[1] * self.screen_height)
                    print(f"tap: {device_x}, {device_y}")
                    action_log[1]["detail_type"] = "coordinates"
                    action_log[1]["detail"] = [device_x, device_y]
                    self.android_device.click(device_x, device_y)
                elif action_type == "type":
                    print(f"type: {action_content}")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = action_content
                    if not is_keyboard_shown:
                        benchmark_log.append(
                            {
                                "step": action_cnt,
                                "response": response,
                                "prompt_tokens": input_token_len,
                                "completion_tokens": output_token_len,
                                "action": action_log,
                            }
                        )
                        print_and_log_error(
                            "ERROR: You need to tap the text input box before typing text."
                        )
                        error_code = 2
                        break
                    self.android_device.input_text(action_content)
                elif action_type == "press home":
                    print("press home")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Return to home page."
                    self.android_device.home()
                elif action_type == "press back":
                    print("press back")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Back to the previous page."
                    self.android_device.back()
                elif action_type == "press enter":
                    print("press enter")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Press the enter key."
                    self.android_device.enter()
                elif action_type == "task complete":
                    print("task complete")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Task completed."
                    task_complete = True
                    benchmark_log.append(
                        {
                            "step": action_cnt,
                            "response": response,
                            "prompt_tokens": input_token_len,
                            "completion_tokens": output_token_len,
                            "action": action_log,
                        }
                    )
                    break
                elif action_type == "task impossible":
                    print("task impossible")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Task impossible."
                    benchmark_log.append(
                        {
                            "step": action_cnt,
                            "response": response,
                            "prompt_tokens": input_token_len,
                            "completion_tokens": output_token_len,
                            "action": action_log,
                        }
                    )
                    print_and_log_error("ERROR: The task is impossible to complete.")
                    error_code = 5
                    break
                elif action_type == "swipe up":
                    print("swipe up")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Swipe up."
                    x1, y1, x2, y2 = 0.5, 0.5, 0.5, 0.2
                    x1, y1, x2, y2 = (
                        int(x1 * self.screen_width),
                        int(y1 * self.screen_height),
                        int(x2 * self.screen_width),
                        int(y2 * self.screen_height),
                    )
                    self.android_device.swipe(x1, y1, x2, y2)
                elif action_type == "swipe down":
                    print("swipe down")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Swipe down."
                    x1, y1, x2, y2 = 0.5, 0.2, 0.5, 0.5
                    x1, y1, x2, y2 = (
                        int(x1 * self.screen_width),
                        int(y1 * self.screen_height),
                        int(x2 * self.screen_width),
                        int(y2 * self.screen_height),
                    )
                    self.android_device.swipe(x1, y1, x2, y2)
                elif action_type == "swipe left":
                    print("swipe left")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Swipe left."
                    x1, y1, x2, y2 = 0.8, 0.5, 0.2, 0.5
                    x1, y1, x2, y2 = (
                        int(x1 * self.screen_width),
                        int(y1 * self.screen_height),
                        int(x2 * self.screen_width),
                        int(y2 * self.screen_height),
                    )
                    self.android_device.swipe(x1, y1, x2, y2)
                elif action_type == "swipe right":
                    print("swipe right")
                    action_log[1]["detail_type"] = "string"
                    action_log[1]["detail"] = "Swipe right."
                    x1, y1, x2, y2 = 0.2, 0.5, 0.8, 0.5
                    x1, y1, x2, y2 = (
                        int(x1 * self.screen_width),
                        int(y1 * self.screen_height),
                        int(x2 * self.screen_width),
                        int(y2 * self.screen_height),
                    )
                    self.android_device.swipe(x1, y1, x2, y2)
                # NOTE: step id starts from 1, Consistent with the Mobile-Agent-V2 of this benchmark.
                benchmark_log.append(
                    {
                        "step": action_cnt,
                        "response": response,
                        "prompt_tokens": input_token_len,
                        "completion_tokens": output_token_len,
                        "action": action_log,
                    }
                )
        except Exception as e:
            print("Task finished unexpectedly")
            print_and_log_error(str(e))
            error_code = 1
        end_time_exec = time.time()
        elapsed_time_exec = end_time_exec - start_time_exec
        benchmark_log.append(
            {
                "total_steps": action_cnt - 1,
                "finish_signal": int(task_complete),
                "elapsed_time_initial": elapsed_time_initial,
                "elapsed_time_exec": elapsed_time_exec,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
            }
        )
        with open(os.path.join(log_dir, "log.json"), "w", encoding="utf-8") as logfile:
            json.dump(benchmark_log, logfile, ensure_ascii=False, indent=4)

        if action_cnt == self.max_rounds:
            error_code = 4

        print(error_code)
        sys.exit(error_code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-task", type=str, required=True)
    parser.add_argument("-benchmark_output_dir", type=str)
    parser.add_argument("-max_rounds", type=int, default=5)
    parser.add_argument("-model_api_url", type=str, default="http://127.0.0.1:7863")
    parser.add_argument("-device", type=str, default="None")
    args = parser.parse_args()
    OUTPUT_DIR = args.benchmark_output_dir

    agent = CogAgent(
        args.model_api_url,
        args.max_rounds,
        device=args.device if args.device != "None" else None,
    )
    agent.execute_task(args.task, args.benchmark_output_dir)
