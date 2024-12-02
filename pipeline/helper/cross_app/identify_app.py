import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from image_wrapper import generate_image_list


def prompt_to_identify_app(screenshot_dir, task_app):
    system_prompt = """You are provided with a sequence of screenshots representing an agent performing tasks across multiple apps on a smartphone. Each screenshot corresponds to a specific action. You are also given a list of apps that should be used in the task.

**Your task is to:**
1. Split the screenshots into segments based on transitions between apps in the given list. Do not change the order of apps, even if they do not match the screenshot order. Output the results based on the provided app list order.
2. For each app, identify where the agent opens and operates within the app. Each app interaction requires at least two screenshots: one for opening the app and one for quitting or switching to another, except for the final app, which may not require a quit action.
3. **Ensure that the start and end indices you provide are within the range of screenshots sent to you.** You will receive a certain number of screenshots, and you must repeat how many screenshots you received before processing. Any indices provided should not exceed the total number of screenshots.
4. If an app from the list is missing in the screenshots, return `-1` for both the start and end screenshot indices for that app.
5. Ignore screenshots that show irrelevant actions (e.g., the home screen or unrelated apps). You may mention them in the analysis but do not include them in the final result.
6. An app may appear more than once in the list (e.g., `["AppA", "AppB", "AppA"]`), but there must be another app between repeated instances of the same app.
7. There might be distractors (e.g., advertisements and popups) in the screenshots; you should not interpret them as transitions between apps.

### Example Input:

**App list:** `["AppA", "AppB", "AppA"]`

**Screenshots:** A sequence of numbered screenshots.

### Example Reasoning:
1. **Screenshots 1-3:** The agent opens AppA, and operates within it.
2. **Screenshots 4-5:** The agent opens AppB and operates within it.
3. **Screenshot 6:** The agent interacts with the home screen, which is irrelevant.
4. **Screenshots 7-9:** The agent opens AppA again and operates within it.

### Final Output:
{
  "AppA_1": {
    "start screen": 1,
    "end screen": 3
  },
  "AppB": {
    "start screen": 4,
    "end screen": 5
  },
  "AppA_2": {
    "start screen": 7,
    "end screen": 9
  }
}
"""

    ask_content = [
        {
            "type": "text",
            "text": f"Here is the app list: {task_app}\nEnsure the order of apps in your final output is exactly the same as the order provided in my app list.",
        }
    ]
    screenshots = generate_image_list(screenshot_dir, detail="low")
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

    return response.json(), len(screenshots)
