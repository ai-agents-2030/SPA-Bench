from gradio_client import Client, handle_file
from device import Device
import argparse
import os
import json
import time
import sys

def print_and_log_error(error_message, output_dir):
    print(error_message)
    error_log = [{"error_message": error_message}]
    filename = output_dir + "/error.json"
    # Check if the file already exists
    if not os.path.exists(filename):
        # If the file does not exist, create it and write the JSON data
        with open(filename, "w", encoding="utf-8") as logfile:
            json.dump(error_log, logfile, ensure_ascii=False)


class DigiRLModelClient:
    def __init__(self, model_api_url: str):
        self.client = Client(model_api_url, verbose=False)

    def chat_with_image(self, query: str, image_path: str):
        text_response, input_token_len, output_token_len = self.client.predict(
            query=query,
            image_or_path=handle_file(image_path),
            api_name="/predict",
        )
        return text_response, input_token_len, output_token_len


class DigiRLAgent:
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

        self.model_client = DigiRLModelClient(self.model_api_url)

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
        history = []
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

                screenshot = self.android_device.get_screenshot()
                screenshot_path = os.path.join(log_dir, f"{action_cnt-1}.png")
                screenshot.save(screenshot_path)

                prev_actions = '\n'.join(history)
                prompt = f"Previous Actions: {prev_actions}\nGoal: {task}"
                print(f"prompt: {prompt}")

                response, input_token_len, output_token_len = self.chat_with_image(
                    prompt, screenshot_path
                )
                print(f"response: {response}")
                print(f"prompt tokens: {input_token_len}, completion tokens: {output_token_len}")
                total_prompt_tokens += input_token_len
                total_completion_tokens += output_token_len

                action_log = [
                    "",  # action type
                    {
                        "detail_type": "string",  # "string" or "coordinates"
                        "detail": "",  # "Task completed." or [x, y] or f"The text \"{input_str}\" has been inputted."
                        # or f"The coordinates ({x},{y}) have been swiped to the {swipe_direction}."
                        # or f"The swipe action has been performed starting from coordinates ({start_x},{start_y}) to ({end_x},{end_y})."
                    },
                ]  # second element for action details based action_type

                
                try:
                    action_str = response.split("Action Decision: ")[1]
                    action_type, touch_point_1, touch_point_2, lift_point_1, lift_point_2, typed_text = action_str.split(", ")
                    touch_point = touch_point_1 + ", " + touch_point_2
                    lift_point = lift_point_1 + ", " + lift_point_2
                    action_type = action_type.split(": ")[1].strip('"')
                    action_log[0] = action_type
                    if action_type == 'DUAL_POINT':
                        touch_point_yx = touch_point.split(": ")[1].strip('[]"')
                        touch_point_yx = [float(num) for num in touch_point_yx.split(", ")]
                        lift_point_yx = lift_point.split(": ")[1].strip('[]"')
                        lift_point_yx = [float(num) for num in lift_point_yx.split(", ")]
                        y1, x1 = touch_point_yx[0] * self.screen_height, touch_point_yx[1] * self.screen_width
                        y2, x2 = lift_point_yx[0] * self.screen_height, lift_point_yx[1] * self.screen_width
                        if (x1 - x2)**2 + (y1 - y2)**2 < 10:
                            self.android_device.click(x1, y1)
                            print(f"tap: {x1}, {y1}")
                            action_log[0] = 'TAP'
                            action_log[1]["detail_type"] = "coordinates"
                            action_log[1]["detail"] = [x1, y1]
                        else:
                            self.android_device.swipe(x1, y1, x2, y2)
                            action_log[0] = 'SWIPE'
                            action_log[1]["detail_type"] = "string"
                            action_log[1]["detail"] = f"The swipe action has been performed starting from coordinates ({x1},{y1}) to ({x2},{y2})."
                    elif action_type == 'TYPE':
                        text = typed_text.split(": ")[1].strip('"')
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = text
                        self.android_device.input_text(text)
                    elif action_type == 'PRESS_HOME':
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = "Return to home page."
                        self.android_device.home()
                    elif action_type == 'PRESS_BACK':
                        print("press back")
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = "Back to the previous page."
                        self.android_device.back()
                    elif action_type == 'PRESS_ENTER':
                        print("press enter")
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = "Press the enter key."
                        self.android_device.enter()
                    elif action_type == 'STATUS_TASK_COMPLETE':
                        print("task complete")
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = "Task completed."
                        task_complete = True
                    elif action_type == 'TASK_IMPOSSIBLE':
                        print("task impossible")
                        action_log[1]["detail_type"] = "string"
                        action_log[1]["detail"] = "Task impossible."
                        print_and_log_error("ERROR: The task is impossible to complete.", log_dir)
                        error_code = 5
                    else:
                        print_and_log_error(f"Action not supported yet.", log_dir)
                        error_code = 2
                        break
                except Exception as e:
                    print_and_log_error(f"Error parsing action: {str(e)}", log_dir)
                    error_code = 2
                    break

                history.append(action_str)
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
                if action_type in ['STATUS_TASK_COMPLETE', 'TASK_IMPOSSIBLE']:
                    break
        except Exception as e:
            print(e)
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
    parser.add_argument("-task", type=str)
    parser.add_argument("-benchmark_output_dir", type=str)
    parser.add_argument("-max_rounds", type=int, default=5)
    parser.add_argument("-model_api_url", type=str, default="http://127.0.0.1:7862")
    parser.add_argument("-device", type=str)
    args = parser.parse_args()

    agent = DigiRLAgent(
        args.model_api_url,
        args.max_rounds,
        device=args.device if args.device != "None" else None,
    )
    agent.execute_task(args.task, args.benchmark_output_dir)
