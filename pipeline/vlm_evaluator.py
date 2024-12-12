import re
from .helper.gpt4o import ask_gpt4o_base
import time


def gpt4o_evaluator(
    task_identifier,
    target_dir,
    dataset,
    reasoning_mode,
    action_mode,
    max_retry: int = 5,
    retry_interval: int = 5,
):
    task_description = dataset.loc[task_identifier]["task_description"]

    counter = 0
    result = None
    reason = None
    token_taken = None
    while counter < max_retry:
        try:
            response = ask_gpt4o_base(target_dir, task_description, reasoning_mode, action_mode)
            content = response["choices"][0]["message"]["content"]
            token_taken = response["usage"]["total_tokens"]
            api_cost = 5e-06 * response["usage"]["prompt_tokens"] + 1.5e-05 * response["usage"]["completion_tokens"]
            # print(content)
            if reasoning_mode == "result_only":
                # Define regex pattern to capture text
                pattern = r"Result[:：]\s*(\d)"
                # Use re.search to find matches
                match = re.search(pattern, content, re.DOTALL)
                result = int(match.group(1).strip())
                reason = ""
            else:
                # Define regex pattern to capture text after a: and b:
                pattern = r"Reason[:：]\s*(.*?)\s*Result[:：]\s*(\d)"
                # Use re.search to find matches
                match = re.search(pattern, content, re.DOTALL)
                if match is None:
                    pattern = r"(?:Reason[:：])?\s*(.*?)\s*Result[:：]\s*(\d)"
                    match = re.search(pattern, content, re.DOTALL)
                result = int(match.group(2).strip())
                reason = match.group(1).strip().replace("\n", "")
        except Exception as err:
            print("Retry [gpt4o_evaluator]")
            print(str(err))
            print(response)
            if counter < max_retry:
                counter += 1
                print(f"Retry in {retry_interval} seconds; {counter}/{max_retry}")
                time.sleep(retry_interval)
                continue
            else:
                return 0, ""
        break

    return result, reason, token_taken, api_cost
