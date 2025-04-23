import sys
sys.path.append("./OdysseyAgent-random")
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)
from transformers.generation import GenerationConfig

import torch
from PIL import Image
import argparse
import os
import gradio as gr
import numpy as np
import json
from qwen_generation_utils import make_context, decode_tokens
from typing import List
import time
import shutil
import base64
import io


class GUIOdysseyModel:
    def __init__(self, model_name_or_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.torch_type = torch.float16
        if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8:
            self.torch_type = torch.bfloat16
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            load_in_4bit=False,
            trust_remote_code=True,
            torch_dtype=self.torch_type,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path, trust_remote_code=True
        )

        # Specify hyperparameters for generation
        self.model.generation_config = GenerationConfig.from_pretrained(
            model_name_or_path, trust_remote_code=True
        )

        self.model.eval()

    def chat_with_image(
        self,
        query: str,
        current_screenshot: Image.Image | np.ndarray,
        history_screenshots: str,  # base64 encoded images
        history_actions: str,
    ):
        if isinstance(current_screenshot, Image.Image):
            pass
        elif isinstance(current_screenshot, np.ndarray):
            current_screenshot = Image.fromarray(current_screenshot).convert("RGB")
        else:
            raise ValueError(f"Unsupported image type: {type(current_screenshot)}")

        if "<sep>" in history_screenshots:
            history_screenshots_arr = []
            for i in history_screenshots.split("<sep>"):
                img = Image.open(io.BytesIO(base64.b64decode(i)))
                history_screenshots_arr.append(img)
            history_screenshots = history_screenshots_arr
        else:
            history_screenshots = []
        if "<sep>" in history_actions:
            history_actions = history_actions.split("<sep>")
        else:
            history_actions = []
        tmp_dir = f"tmp_{time.time()}"
        os.makedirs(tmp_dir)
        image_path = os.path.join(tmp_dir, "current_screenshot.png")
        current_screenshot.save(image_path)
        history_image = []
        for idx, img in enumerate(history_screenshots):
            fp = os.path.join(tmp_dir, f"{idx}.png")
            img.save(fp)
            history_image.append(fp)
        assert len(history_image) == len(history_actions), f"History image and action length mismatch: {len(history_image)} != {len(history_actions)}"
        if len(history_actions) >= 2:
            his_img = history_image[-2:]
            question = f"Picture 1: <img>{image_path}</img>\nI'm looking for guidance on how to {query}\n nPrevious screenshots: <img>image-history: {his_img}</img>\n nPrevious Actions: 1.{history_actions[-1]}, 2.{history_actions[-2]}"
            print(question)
        elif len(history_actions) == 0:
            question = f"Picture 1: <img>{image_path}</img>\nI'm looking for guidance on how to {query}"
            print(question)
        else:
            his_img = history_image
            question = f"Picture 1: <img>{image_path}</img>\nI'm looking for guidance on how to {query}\n nPrevious screenshots: <img>image-history: {his_img}</img>\n nPrevious Actions: 1.{history_actions[-1]}"
            print(question)
        input_token_len = -1
        output_token_len = -1
        with torch.no_grad():
            raw_text, _ = make_context(
                self.tokenizer,
                question,
                system="You are a helpful assistant.",
                chat_format="chatml",
            )
            input_ids = self.tokenizer(raw_text, return_tensors="pt", padding="longest")
            # Calculate the number of input tokens
            input_token_len = len(input_ids["input_ids"][0])
            print(f"Input token count: {input_token_len}")
            batch_out_ids = self.model.generate(
                input_ids=input_ids.input_ids.to(self.model.device),
                attention_mask=input_ids.attention_mask.to(self.model.device),
                do_sample=False,
                num_beams=1,
                length_penalty=1,
                num_return_sequences=1,
                use_cache=True,
                pad_token_id=self.tokenizer.eod_id,
                eos_token_id=self.tokenizer.eod_id,
                min_new_tokens=1,
                max_new_tokens=30,
            )

            padding_lens = (
                input_ids.input_ids.eq(self.tokenizer.pad_token_id).sum().item()
            )
            # Calculate the number of output tokens
            output_token_len = len(batch_out_ids[0]) - padding_lens
            print(f"Output token count: {output_token_len}")
            response = decode_tokens(
                batch_out_ids[0][padding_lens:],
                self.tokenizer,
                raw_text_len=len(raw_text),
                context_length=(input_ids.input_ids.size(1) - padding_lens),
                chat_format="chatml",
                verbose=False,
                errors="replace",
            )

            shutil.rmtree(tmp_dir, ignore_errors=True)

            return response, input_token_len, output_token_len


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-model_name_or_path", type=str, default="hflqf88888/OdysseyAgent-random"
    )
    args = parser.parse_args()

    model = GUIOdysseyModel(args.model_name_or_path)

    # Define input components
    inputs = [
        gr.Textbox(label="Query"),  # for the `query` parameter
        gr.Image(label="Current Screenshot", type="pil"),  # for `current_screenshot`
        gr.Textbox(label="History Screenshots"),  # to handle list of past screenshots
        gr.Textbox(label="History Action"),  # to handle list of past actions
    ]

    demo = gr.Interface(
        fn=model.chat_with_image,
        inputs=inputs,
        outputs=["text", "number", "number"],
    )

    demo.launch(share=False, server_name="0.0.0.0", server_port=7860, show_error=True)
