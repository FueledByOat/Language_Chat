import torch
from transformers import AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig
import logging

logger = logging.getLogger(__name__)


class VQAService:
    def __init__(self):
        self.model = None
        self.processor = None
        self.model_id = "microsoft/Phi-3-vision-128k-instruct"

    def load_model(self):
        """Loads the model into VRAM."""
        if self.model is not None:
            logger.info("VQA Model already loaded.")
            return

        logger.info("📦 Loading Phi-3-Vision...")

        try:
            # 1. Quantization Config (Critical for consumer GPUs)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )

            self.processor = AutoProcessor.from_pretrained(
                self.model_id, trust_remote_code=True
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                device_map="audo",
                trust_remote_code=True,
                quantization_config=bnb_config,
                _attn_implementation="eager",
            )

            logger.info("✅ Phi-3-Vision Loaded Successfully")
        except Exception as e:
            logger.critical(f"Failed to load VQA model: {e}")
            raise e

    def analyze_image(self, image, question_en: str) -> str:
        """Runs inference on the loaded model"""
        if not self.model or not self.processor:
            raise RuntimeError("VQA Model is not loaded. Check startup logs.")

        # Format prompt specifically for Phi-3
        # Note: We ask for a short answer to speed up generation
        prompt = f"<|user|>\n<|image_1|>\n{question_en} (Answer concisely)<|end|>\n<|assistant|>\n"

        # Process inputs
        inputs = self.processor(prompt, [image], return_tensors="pt").to(
            self.model.device
        )

        # Generate response parameters
        generate_ids = self.model.generate(
            **inputs,
            max_new_tokens=100,  # Cap tokens for speed
            temperature=0.7,
            do_sample=True,
            eos_token_id=self.processor.tokenizer.eos_token_id,
        )

        # Decode and clean up
        # Strip the input tokens to only return the new generated text
        generate_ids = generate_ids[:, inputs["input_ids"].shape[1] :]
        response = self.processor.batch_decode(
            generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        return response.strip()
