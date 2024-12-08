import os
from dataclasses import dataclass
from enum import Enum

from anthropic import Anthropic

google_api_key_env = "GOOGLE_DEEPMIND_API_KEY"
is_google_api_key_using_free_tier = os.environ.get("GOOGLE_DEEPMIND_API_KEY_IS_FREE_TIER") == "True"
anthropic_api_key_env = "ANTHROPIC_API_KEY"
openai_api_key_env = "OPENAI_API_KEY"
deepinfra_api_key_env = "DEEPINFRA_API_KEY"
google_model_specifier = "gemini-1.5-pro-002"
anthropic_model_specifier = "claude-3-5-sonnet-20241022"
anthropic_generation_temp = 1.0
google_generation_temp = anthropic_generation_temp
anthropic_reconstruction_temp = 0.0
google_reconstruction_temp = anthropic_reconstruction_temp
anthropic_obj_gen_group_size = 20
google_obj_gen_group_size = anthropic_obj_gen_group_size
max_num_api_calls_for_schema_validation_retry_logic = 3
max_num_api_calls_for_anthropic_overloaded_retry_logic = 5
max_num_api_calls_for_google_refusals_retry_logic = 5


class ModelProvider(Enum):
    ANTHROPIC = "claude"
    GOOGLE_DEEPMIND = "gemini"

@dataclass
class AnthropicClientBundle:
    client: Anthropic
    sys_prompt: str
    max_tokens: int
    temp: float
    model_spec: str