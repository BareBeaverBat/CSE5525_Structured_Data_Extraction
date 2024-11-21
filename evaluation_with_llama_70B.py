from huggingface_hub import login
import transformers
import torch

# Log in using your Hugging Face API token
login(token="your_token")
model_id = "meta-llama/Meta-Llama-3.1-70B"
pipeline = transformers.pipeline("text-generation", model=model_id, model_kwargs={"torch_dtype": torch.bfloat16}, device_map="auto")
pipeline("Hey how are you doing today?")