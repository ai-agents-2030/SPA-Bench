from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)
import torch
from PIL import Image
import argparse
import gradio as gr
import numpy as np


class CogAgentModel:
    def __init__(self, model_name_or_path: str, tokenizer_name_or_path: str):
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
            tokenizer_name_or_path, trust_remote_code=True
        )
        self.model.eval()

    def chat_with_image(self, query: str, image_or_path: Image.Image):
        image = image_or_path
        if isinstance(image, str):
            image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert("RGB")

        input_by_model = self.model.build_conversation_input_ids(
            self.tokenizer, query=query, images=[image]
        )

        inputs = {
            "input_ids": input_by_model["input_ids"].unsqueeze(0).to(self.device),
            "token_type_ids": input_by_model["token_type_ids"]
            .unsqueeze(0)
            .to(self.device),
            "attention_mask": input_by_model["attention_mask"]
            .unsqueeze(0)
            .to(self.device),
            "images": [
                [input_by_model["images"][0].to(self.device).to(self.torch_type)]
            ],
        }
        if "cross_images" in input_by_model and input_by_model["cross_images"]:
            inputs["cross_images"] = [
                [input_by_model["cross_images"][0].to(self.device).to(self.torch_type)]
            ]

        # Calculate the number of input tokens
        input_token_len = len(inputs["input_ids"][0])
        print(f"Input token count: {input_token_len}")

        with torch.no_grad():
            ans = self.model.generate(**inputs, max_new_tokens=2048)
        res = self.tokenizer.decode(ans[0][input_token_len:], skip_special_tokens=True)
        # Calculate the number of output tokens
        output_token_len = len(ans[0]) - input_token_len
        print(f"Output token count: {output_token_len}")

        return res, input_token_len, output_token_len


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-model_name_or_path", type=str, default="THUDM/cogagent-chat-hf"
    )
    parser.add_argument(
        "-tokenizer_name_or_path", type=str, default="lmsys/vicuna-7b-v1.5"
    )
    args = parser.parse_args()

    model = CogAgentModel(
        args.model_name_or_path,
        args.tokenizer_name_or_path,
    )

    demo = gr.Interface(
        fn=model.chat_with_image,
        inputs=["text", "image"],
        outputs=["text", "number", "number"],
    )

    demo.launch(share=False, server_name="0.0.0.0", server_port=7863)
