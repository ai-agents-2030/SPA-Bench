from paddleocr import PaddleOCR
import logging
import re

# Set logging level to INFO to suppress DEBUG messages
logging.getLogger("ppocr").setLevel(logging.INFO)


def text_extraction(screen_path, language="CHN"):
    if language == "CHN":
        ocr = PaddleOCR(use_angle_cls=False, lang="ch")
    elif language == "ENG":
        ocr = PaddleOCR(use_angle_cls=False, lang="en")
    else:
        print("Language not supported")
        return ""
    result = ocr.ocr(screen_path, cls=False)
    result_string = "".join([i[1][0] for i in result[0]]) if result and result[0] else ""
    return re.sub(r"\s+", "", result_string)
