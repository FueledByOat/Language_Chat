# services/vqa_service.py
import torch
from transformers import AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig


class VQAService:
    def __init__(self):
        self.model = None
        self.processor = None

    def load_model(self):
        """Loads the model into VRAM (only run this once at startup)"""
        print("📦 Loading Phi-3-Vision...")

        # 1. Quantization Config
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )

        model_id = "microsoft/Phi-3-vision-128k-instruct"

        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

        # 2. Load Model with "eager" attention to bypass FlashAttention error
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="cuda",
            trust_remote_code=True,
            quantization_config=bnb_config,
            _attn_implementation="eager",  # <--- THIS LINE FIXES YOUR ERROR
        )

        print("✅ Phi-3-Vision Loaded Successfully")

    def analyze_image(self, image, question_en: str) -> str:
        """Runs inference on the loaded model"""
        # Format prompt specifically for Phi-3
        prompt = f"<|user|>\n<|image_1|>\n{question_en}<|end|>\n<|assistant|>\n"

        # Process inputs
        inputs = self.processor(prompt, [image], return_tensors="pt").to("cuda")

        # Generate response
        generate_ids = self.model.generate(
            **inputs,
            max_new_tokens=120,
            temperature=0.7,
            do_sample=True,
            eos_token_id=self.processor.tokenizer.eos_token_id,
        )

        # Decode and clean up
        generate_ids = generate_ids[:, inputs["input_ids"].shape[1] :]
        return self.processor.batch_decode(generate_ids, skip_special_tokens=True)[0]
