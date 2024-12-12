import sys
import os
import json
import re
import time
import requests

sys.path.append(os.getcwd())
from pipeline.helper.cross_app.identify_app import prompt_to_identify_app
from pipeline.helper.data import get_dataset
from pipeline.helper.gpt4o import ask_gpt4o_base
from pipeline.helper.screenshot_with_action import process_images
from pipeline.helper.image_wrapper import generate_image_list
from framework import utils


def stage_1_cross_evaluator(
    apps_order, task_identifier, result_dir, mode="eval", agent=None, max_retry: int = 3, retry_interval: int = 3
):
    """Stage 1 of cross-app task evaluation."""

    # print(task_identifier)

    dataset = get_dataset(utils.get_results_csv_path(result_dir))
    task_description = dataset.loc[task_identifier]["task_description"]
    # print(task_description)

    if mode == "full":
        target_dir = os.path.join(result_dir, task_identifier, agent)
    elif mode == "eval":
        target_dir = os.path.join(result_dir, task_identifier)

    try:
        process_images(target_dir)
    except Exception as err:
        print(err)
        print(f"NOT WORKING! {target_dir}")

    if os.path.exists(os.path.join(target_dir, "tap_and_text")):
        target_dir = os.path.join(target_dir, "tap_and_text")

    counter = 0
    while counter < max_retry:
        try:
            print(apps_order)
            screenshot_app, screenshots_num = prompt_to_identify_app(target_dir, apps_order)
            response = screenshot_app["choices"][0]["message"]["content"]
            parsed_response = stage_1_parser(response)
            print(parsed_response)
            break
        except Exception as err:
            print("Retry [stage1_evaluator]")
            print(str(err))
            if counter < max_retry:
                counter += 1
                print(f"Retry in {retry_interval} seconds; {counter}/{max_retry}")
                time.sleep(retry_interval)
                continue
            else:
                return False

    return stage_1_checker(parsed_response, screenshots_num), parsed_response


def stage_1_parser(screenshot_app):
    """Parse model response from stage 1 of cross-app task evaluation."""

    # Regex to match the app name and start/end screens
    pattern = r'"([\w\s]+_?\d?)": {\s+"start screen": (-?\d+),\s+"end screen": (-?\d+)'

    # Find all matches
    matches = re.findall(pattern, screenshot_app)

    # Convert matches to a dictionary
    app_dict = {app: (int(start), int(end)) for app, start, end in matches}

    # Return the parsed dictionary
    return app_dict


def stage_1_checker(app_dict, length):
    # Loop through the dictionary elements
    app_list = list(app_dict.items())  # Convert dictionary items into a list of tuples

    for name, (start, end) in app_list:
        # Case 1: if either start or end is -1
        if start == -1 or end == -1:
            return False

        # Case 2: if start is bigger than end
        if start > end:
            return False

        # Case 3: if start or end is bigger than length
        if start > length or end > length:
            return False

    # Loop through the dictionary elements again to check the order condition
    for i in range(len(app_list) - 1):
        current_name, (current_start, current_end) = app_list[i]
        next_name, (next_start, next_end) = app_list[i + 1]

        # Case 4: if the current app's end time is greater or equal to the next app's start time
        if current_end >= next_start:
            return False

    # If none of the cases return False, return True
    return True


def stage_2_cross_evaluator(
    task_data, task_identifier, result_dir, parsed_response, evaluation_detail, mode="eval", agent=None
):
    evaluation_detail["parsed_response"] = parsed_response
    print(parsed_response)

    if mode == "full":
        target_dir = os.path.join(result_dir, task_identifier, agent)
    elif mode == "eval":
        target_dir = os.path.join(result_dir, task_identifier)

    reasoning_mode = "result_only"
    if os.path.exists(os.path.join(target_dir, "tap_and_text")):
        action_mode = "with_action"
        screenshot_dir = os.path.join(target_dir, "tap_and_text")
    else:
        action_mode = "no_action"
        screenshot_dir = target_dir

    subtasks = stage_2_data(task_data)
    evaluation_detail["subtasks"] = subtasks

    # loop through each subtask
    memory_dict = {}
    for i in parsed_response.keys():
        print(">>>")
        print(i)
        subtask_description = subtasks[i]["task"]
        slices = parsed_response[i]
        evaluation_detail["slices" + "_" + i] = slices

        history = []
        if subtasks[i]["history"]:
            # Regular expression to find content inside {}
            pattern = r"\{(.*?)\}"
            # Find all matches
            matches = re.findall(pattern, subtask_description)
            for j in matches:
                history.append((j, memory_dict[j]))

        response = ask_gpt4o_base(target_dir, subtask_description, reasoning_mode, action_mode, slices, history)

        content = response["choices"][0]["message"]["content"]
        # token_taken = response["usage"]["total_tokens"]
        # api_cost = 5e-06 * response["usage"]["prompt_tokens"] + 1.5e-05 * response["usage"]["completion_tokens"]
        evaluation_detail["content" + "_" + i] = content
        # Define regex pattern to capture text
        pattern = r"Result[:：]\s*(\d)"
        # Use re.search to find matches
        match = re.search(pattern, content, re.DOTALL)
        result = int(match.group(1).strip())
        # reason = ""

        if result == 0:
            return False

        if subtasks[i]["memory"] != "None":
            print(subtasks[i]["memory"])
            screenshots = generate_image_list(screenshot_dir, slices)
            stage_2_memory(screenshots, subtasks[i]["memory"], memory_dict)
            print(memory_dict)

    evaluation_detail["memory_dict"] = memory_dict

    return True
    #
    # {'YouTube_1': (21, 23), 'Clock': (-1, -1), 'YouTube_2': (-1, -1)}


def stage_2_data(task_data):
    # Dictionary to keep track of occurrences of each app
    app_count = {}

    # First pass to count occurrences of each app
    for key, subtask in task_data.items():
        if key.startswith("subtask"):
            app_name = subtask["app"]
            app_count[app_name] = app_count.get(app_name, 0) + 1

    # Dictionary to store the final result
    result = {}

    # Second pass to build the final dictionary with suffixes where needed
    suffix_count = {}
    for key, subtask in task_data.items():
        if key.startswith("subtask"):
            app_name = subtask["app"]

            if app_count[app_name] == 1:
                # No suffix if the app appears only once
                new_app_name = app_name
            else:
                # Increment the suffix count for each app occurrence
                suffix_count[app_name] = suffix_count.get(app_name, 0) + 1
                new_app_name = f"{app_name}_{suffix_count[app_name]}"

            # Add the subtask to the result under the new app name
            result[new_app_name] = {"task": subtask["task"], "history": subtask["history"], "memory": subtask["memory"]}

    return result


def stage_2_memory(screenshots, memory_text, memory_dict):
    system_prompt = """You are an MLLM tasked with analyzing screenshots and summarizing the relevant information based on a description provided by the user. Only summarize information from screenshots that relate to the description, ignoring any that are unrelated. If the screenshots show a list of results (e.g., a search page), summarize or list all the relevant results. The summary should be clear and concise, without bullet points, step-by-step details, or line breaks."""

    user_prompt = f"""Here is the description: {memory_text}"""

    ask_content = [{"type": "text", "text": user_prompt}]
    ask_content.extend(screenshots)

    # OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": ask_content}],
        "temperature": 0,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response = response.json()

    print(response["choices"][0]["message"]["content"])
    memory_dict[memory_text] = response["choices"][0]["message"]["content"]


def cross_evaluator(task_identifier, result_dir, mode="eval", agent=None):
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Go up to the parent folder and then down to the target subfolder
    split_task_path = os.path.join(script_dir, os.pardir, "data", "cross-app-split", task_identifier + ".json")

    # Open and load the JSON file
    with open(split_task_path, encoding="utf-8") as json_file:
        task_data = json.load(json_file)
        # Extract the apps from each subtask
        apps_order = []
        for key, value in task_data.items():
            if key.startswith("subtask_"):
                apps_order.append(value["app"])

    evaluation_detail = {}
    stage_1_result, parsed_response = stage_1_cross_evaluator(apps_order, task_identifier, result_dir, mode, agent)
    if not stage_1_result:
        result = False
    else:
        result = stage_2_cross_evaluator(
            task_data, task_identifier, result_dir, parsed_response, evaluation_detail, mode, agent
        )

    if result == 1:
        print(f"{task_identifier} is successful")
    elif result == 0:
        print(f"{task_identifier} is failed")
    else:
        print(f"{task_identifier} has errors")
    utils.save_result__completed_evaluation(
        result_dir, task_identifier, agent, int(result), evaluation_detail, "result_only", "semi_action"
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task_identifier", type=str, required=True)
    parser.add_argument("--result_dir", type=str, required=True)
    parser.add_argument("--mode", type=str, default="full", choices=["full", "exec", "eval"])
    parser.add_argument("--agent", type=str, default="")

    args = parser.parse_args()

    cross_evaluator(
        args.task_identifier,
        args.result_dir,
        args.mode,
        args.agent,
    )
