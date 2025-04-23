from transformers import AutoTokenizer
from model import T5ForMultimodalGeneration
from transformers import AutoProcessor, Blip2Model
import torch
from PIL import Image
import gradio as gr
import numpy as np
import os

class AutoUIModel:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.torch_type = torch.float16
        if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8:
            self.torch_type = torch.bfloat16

        self.img_model = Blip2Model.from_pretrained(
            "Salesforce/blip2-opt-2.7b",
            torch_dtype=self.torch_type,
            ).to(self.device)
        self.img_processor = AutoProcessor.from_pretrained(
            "Salesforce/blip2-opt-2.7b",
            trust_remote_code=True
        )
        self.model = T5ForMultimodalGeneration.from_pretrained(
            os.path.dirname(os.path.abspath(__file__)) + '/Auto-UI-Base',
            1408,
            torch_dtype=self.torch_type
        ).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            os.path.dirname(os.path.abspath(__file__)) + '/Auto-UI-Base',
            trust_remote_code=True
        )
        self.img_model.eval()
        self.model.eval()

    def chat_with_image(self, query: str, image_or_path: Image.Image):
        image = image_or_path
        if isinstance(image_or_path, str):
            image = Image.open(image_or_path).convert("RGB")
        elif isinstance(image_or_path, np.ndarray):
            image = Image.fromarray(image_or_path).convert("RGB")
        with torch.no_grad():
            inputs = self.img_processor(images=image, return_tensors="pt").to(self.device)
            image_features = self.img_model.get_image_features(**inputs).pooler_output[0]
            image_features = image_features.detach().to(self.device)
            image_features = image_features[..., -1408:]

            obs_ids = self.tokenizer(
                query, return_tensors='pt', padding=True, max_length=512,
                truncation=True
            ).to(self.device)
            outputs = self.model.generate(
                input_ids=obs_ids['input_ids'], attention_mask=obs_ids['attention_mask'],
                image_ids=image_features.unsqueeze(0),
                max_new_tokens=128,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                temperature=0.1
            ).to(self.device)

        raw_action = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

        input_token_len = len(obs_ids['input_ids'][0]) + len(image_features)
        print(f"Input token count: {input_token_len}")
        output_token_len = len(outputs[0])
        print(f"Output token count: {output_token_len}")

        return raw_action, input_token_len, output_token_len


if __name__ == "__main__":
    model = AutoUIModel()

    # model.chat_with_image("Search @Tesla on Youtube", r"C:\Users\User\Downloads\Smartphone-Agent-Benchmark\results\session-experiment-ENG-31072024\youtube_0\MobileAgentV2\0.png")

    demo = gr.Interface(
        fn=model.chat_with_image,
        inputs=["text", "image"],
        outputs=["text", "number", "number"],
    )
    server_port = 7861
    demo.launch(share=False, server_name="0.0.0.0", server_port=server_port)