import sys
import os

sys.path.append(os.getcwd())
from pipeline.key_component_matcher import key_component_match, get_screenshot_file_names
from pipeline.vlm_evaluator import gpt4o_evaluator
from pipeline.helper.data import get_dataset
from framework import utils
from datetime import datetime


def evaluator(
    task_identifier,
    result_dir,
    skip_key_components,
    reasoning_mode,
    action_mode,
    mode="eval",
    agent=None,
):
    """Evaluation."""

    dataset = get_dataset(utils.get_results_csv_path(result_dir))

    if mode == "full":
        target_dir = os.path.join(result_dir, task_identifier, agent)
    elif mode == "eval":
        target_dir = os.path.join(result_dir, task_identifier)
    else:
        target_dir = "benchmark/" + task_identifier

    if not skip_key_components:
        matched_screenshot, total_num_screenshot = key_component_match(task_identifier, target_dir, dataset)
    else:
        matched_screenshot, total_num_screenshot = -1, len(get_screenshot_file_names(target_dir))

    if total_num_screenshot == 0:
        evaluation_detail = {}
        result = -1
    else:
        evaluation_detail = {
            "coarse_detect": 1 if matched_screenshot else 0,
        }
        fine_detect_result = 0
        fine_detect_reason = ""
        result = 0
        api_cost = 0
        if skip_key_components or matched_screenshot:
            start_time = datetime.now()
            fine_detect_result, fine_detect_reason, token_taken, api_cost = gpt4o_evaluator(
                task_identifier, target_dir, dataset, reasoning_mode, action_mode
            )
            time_taken = (datetime.now() - start_time).seconds
            if fine_detect_result:
                result = 1
            evaluation_detail["matched"] = matched_screenshot
            evaluation_detail["total_num"] = total_num_screenshot
            evaluation_detail["gpt_token_taken"] = token_taken
            evaluation_detail["time_taken"] = time_taken
            evaluation_detail["fine_detect"] = int(fine_detect_result)
            evaluation_detail["fine_detect_reason"] = (
                fine_detect_reason.replace("\n", "").replace('"', "").replace("'", "")
            )
            evaluation_detail["api_cost"] = api_cost

    if result == 1:
        print(f"{task_identifier} is successful")
    elif result == 0:
        print(f"{task_identifier} is failed")
    elif result == -1:
        print(f"{task_identifier} does not have any screenshots")
    utils.save_result__completed_evaluation(
        result_dir, task_identifier, agent, int(result), evaluation_detail, reasoning_mode, action_mode
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task_identifier", type=str, required=True)
    parser.add_argument("--result_dir", type=str, required=True)
    parser.add_argument("--skip_key_components", action="store_true")
    parser.add_argument(
        "--reasoning_mode",
        type=str,
        required=True,
        default="direct",
        choices=["result_only", "direct"],
    )
    parser.add_argument(
        "--action_mode",
        type=str,
        required=True,
        default="no_action",
        choices=["no_action", "with_action", "text_action"],
    )
    parser.add_argument("--mode", type=str, default="full", choices=["full", "exec", "eval"])
    parser.add_argument("--agent", type=str, default="")

    args = parser.parse_args()

    evaluator(
        args.task_identifier,
        args.result_dir,
        args.skip_key_components,
        args.reasoning_mode,
        args.action_mode,
        args.mode,
        args.agent,
    )
