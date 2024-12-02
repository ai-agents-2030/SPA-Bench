import csv
import json
from pydantic import BaseModel
from openai import OpenAI


def call_llm_to_split_task(task_description):
    client = OpenAI()

    class Step(BaseModel):
        app: str
        task: str
        history: bool
        memory: str

    class Subtasks(BaseModel):
        steps: list[Step]

    system_prompt = """
    You are tasked with splitting a smartphone control instruction into a series of subtasks, each corresponding to specific app interactions. For each subtask, you should define:

    1. **app**: The name of the app being used in the subtask.
    2. **task**: A string describing the action to be performed. Do not include the app name in the task description unless necessary (e.g., if the task is to only open the app). Use '{PREVIOUS MEMORY}' if the task depends on information from a previous subtask. This should be exactly the same phrase as the previous subtask's memory (i.e., if history is True).
    3. **history**: A boolean value (`True` or `False`) indicating whether this subtask relies on data from a previous subtask.
    4. **memory**: If applicable, specify a piece of information that the current subtask generates or retrieves, which will be passed to the next subtask. If no memory is needed, set this to `None`.

    **Guidelines**:
    - Use the same language for the split task as the task description.
    - If there are several consecutive subtasks for the same app, combine them into a single subtask (i.e., adjacent subtasks should not have the same app). Subtasks for the same app are acceptable if there is at least one subtask for a different app in between.
    - By default, each subtask should be independent unless explicitly needing data from a prior subtask (in which case, set `"history": True`).
    - Flexibly determine whether any information should be stored as **memory** and passed to subsequent tasks, based on the task's natural requirements.
    - Output the subtasks in a structured format like the following:
    {
        "subtask_1":{
            "app":"APP",
            "task":"TASK",
            "history":"BOOL",
            "memory":"MEMORY"
        },
        "subtask_2":{
            "app":"APP",
            "task":"TASK",
            "history":"BOOL",
            "memory":"MEMORY"
        },
        ...
    }

    ### Example 1
    **Task**: Adjust the notification settings for the YouTube app on your phone using Settings, then proceed to open YouTube.
    **Result**:
    {
        "subtask_1":{
            "app":"Settings",
            "task":"Adjust the notification settings for the YouTube app on your phone",
            "history":false,
            "memory":"None"
        },
        "subtask_2":{
            "app":"YouTube",
            "task":"Open YouTube",
            "history":false,
            "memory":"None"
        }
    }

    ### Example 2
    **Task**: Utilize the X app to research and identify a highly recommended robotic vacuum cleaner, and then go to Amazon to purchase one.
    **Result**:
    {
        "subtask_1":{
            "app":"X",
            "task":"Research and identify a highly recommended robotic vacuum cleaner",
            "history":false,
            "memory":"robotic vacuum cleaner"
        },
        "subtask_2":{
            "app":"Amazon",
            "task":"Go to Amazon to purchase {robotic vacuum cleaner}",
            "history":true,
            "memory":"None"
        }
    }

    Now, for any smartphone control instruction, decompose the task into subtasks using the format above.
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": task_description}],
        response_format=Subtasks,
    )

    split_task = completion.choices[0].message.parsed

    return split_task


# Load tasks from CSV file
def load_tasks_from_csv(csv_filename):
    tasks = []
    with open(csv_filename, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tasks.append({"task_identifier": row["task_identifier"], "task_description": row["task_description"]})
    return tasks


# Process the split task into a dictionary that can be saved as JSON
def process_split_task(task_description, split_task):
    task_dict = {"task_description": task_description}
    for i, step in enumerate(split_task.steps, start=1):
        task_dict[f"subtask_{i}"] = {"app": step.app, "task": step.task, "history": step.history, "memory": step.memory}

    print(task_dict)
    return task_dict


# Save the processed split task to a JSON file
def save_split_task_to_json(task_identifier, split_task, output_dir):
    json_filename = f"{output_dir}/{task_identifier}.json"
    with open(json_filename, "w", encoding="utf-8") as jsonfile:
        json.dump(split_task, jsonfile, ensure_ascii=False, indent=4)


# Main workflow to load tasks, call the API, and save each split task
def process(input_csv):
    output_dir = r"D:\Smartphone-Agent-Benchmark\data\cross-app-split"  # Output directory for the JSON files

    # Load tasks from CSV
    tasks = load_tasks_from_csv(input_csv)

    for idx, task in enumerate(tasks):
        task_identifier = task["task_identifier"]
        task_description = task["task_description"]

        print(f"Processing Task {idx + 1}/{len(tasks)}: {task_description}")

        # Call the API to split the task (API function call would happen here)
        split_task = call_llm_to_split_task(task_description)  # This function already returns split_task

        # Process split_task into a dictionary
        processed_task = process_split_task(task_description, split_task)

        # Save the processed task to a JSON file
        save_split_task_to_json(task_identifier, processed_task, output_dir)

        print(f"Task {task_identifier} processed and saved to {task_identifier}.json")


if __name__ == "__main__":
    input_csvs = [
        r"D:\Smartphone-Agent-Benchmark\data\cross-app-CHN.csv",
        r"D:\Smartphone-Agent-Benchmark\data\cross-app-ENG.csv",
    ]  # Input CSV files
    for input_csv in input_csvs:
        process(input_csv)
