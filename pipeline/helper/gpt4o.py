import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from dotenv import load_dotenv
from helper.image_wrapper import generate_image_list
from helper.prompts import sys_prompt_template, base_prompt_template
from helper.screenshot_with_action import process_images
from helper.text_with_action import extract_action

# Load environment variables from .env file
load_dotenv(verbose=True, override=True)
# OpenAI API Key
api_key = os.getenv("OPENAI_API_KEY")
api_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"

headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}


def ask_gpt4o_base(target_dir, task_description, reasoning_mode, action_mode, slices=None, history=None):
    sys_prompt = sys_prompt_template(action_mode)

    extra_action = extract_action(target_dir) if action_mode == "text_action" else ""
    ask_prompt = base_prompt_template(task_description, reasoning_mode, action_mode, extra_action, history)
    ask_content = [{"type": "text", "text": ask_prompt}]
    if action_mode == "with_action":  # add action info to original screenshots
        process_images(target_dir, text_info=True)
        screenshot_dir = os.path.join(target_dir, "tap_and_text")
    elif action_mode == "text_action":
        process_images(target_dir, text_info=False)
        screenshot_dir = os.path.join(target_dir, "tap_only")
    else:
        screenshot_dir = target_dir
    ask_content.extend(generate_image_list(screenshot_dir, slices))

    # print(sys_prompt)
    # print("=====")
    # print(ask_prompt)

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": ask_content}],
        "temperature": 0,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    return response.json()
