import os
import json


def extract_action(folder_path):
    # Load the log.json
    with open(os.path.join(folder_path, "log.json"), encoding="utf-8") as file:
        log = json.load(file)

    text_action = ""
    total_steps = log[-1]["total_steps"]
    for j in range(total_steps):
        i = log[j]
        if "step" in i.keys():
            if i["action"][1]["detail_type"] == "string":
                step = i["step"]
                text_action += f'The action that changes from screenshot No.{step} to screenshot No.{step+1} is *{i["action"][0]}*, with details: *{i["action"][1]["detail"]}*\n'
    return text_action[:-1]
