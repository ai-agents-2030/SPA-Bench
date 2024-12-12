import os
from .helper.paddle_ocr import text_extraction


def get_screenshot_file_names(target_dir):
    try:
        files = os.listdir(target_dir)
    except FileNotFoundError:
        return []
    # Filter out only image files (assuming the extension can be png or jpg)
    screenshots = [f for f in files if f.endswith(".png") or f.endswith(".jpg")]
    # Sort files numerically by the filename before the extension
    screenshots.sort(key=lambda x: int(os.path.splitext(x)[0]))
    return screenshots


def key_component_match(task_identifier, target_dir, dataset, case_sensitive=False):
    screenshot_file_names = get_screenshot_file_names(target_dir)
    language = dataset.loc[task_identifier, "task_language"]
    key_components = dataset.loc[task_identifier, "key_component_final"]
    if not case_sensitive:
        key_components = [component.lower() for component in key_components]
    if len(screenshot_file_names) > 0:
        # start from the last screenshot
        for file_name in reversed(screenshot_file_names):
            screen_info = text_extraction(target_dir + "/" + file_name, language)
            if not case_sensitive:
                screen_info = screen_info.lower()
            # check whether all key component exist in the final screenshot
            success = all([component in screen_info for component in key_components])
            # print(f"OCR <{task_identifier}/{file_name}>:")
            # print(screen_info)
            # print("Matched:", "YES" if success else "NO")
            if success:
                return file_name, len(screenshot_file_names)
        # doesn't match any screenshots
        return "", len(screenshot_file_names)
    else:
        return "", 0
