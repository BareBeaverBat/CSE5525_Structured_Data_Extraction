import json
import os
import time
from string import Template
from typing import Any, Optional, Callable

from anthropic import Anthropic
from google.generativeai import GenerativeModel
from jsonschema import Draft202012Validator
import anthropic
import google.generativeai as google_genai
from google.generativeai.types import safety_types

from constants import schemas_path, anthropic_api_key_env, google_model_specifier, anthropic_model_specifier, \
    anthropic_object_generation_sys_prompt, google_object_generation_sys_prompt, \
    google_text_passage_generation_sys_prompt, is_google_api_key_using_free_tier, \
    anthropic_text_passage_generation_sys_prompt, anthropic_obj_gen_group_size, google_obj_gen_group_size, \
    google_generation_temp, anthropic_generation_temp, google_reconstruction_temp, \
    google_object_reconstruction_sys_prompt, claude_objs_path, gemini_objs_path, gemini_texts_path, claude_texts_path
from data_loading import load_scenarios
from logging_setup import create_logger
from misc_util_funcs import d, extract_text_passage_from_output, extract_json_doc_from_output
from validate_generated_json_objs_and_texts import validate_generated_objects_texts

logger = create_logger(__name__)


def generate_json_objs(google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic], schema_idx: int,
                       schema: dict[str,Any], scenario_domain: str, scenario_texts_label: str,
                       increment_problem_counter: Callable[[bool], None]) -> list[dict[str, Any]]:
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined
    should_use_claude: bool = google_client is None
    model_nm = "Claude" if should_use_claude else "Gemini"
    logger.info(f"Generating objects with {model_nm} for scenario {scenario_domain} - {scenario_texts_label}")
    
    user_prompt = d(f"""
    Here is such a JSON schema for the domain {scenario_domain}:
    ```json
    {json.dumps(schema)}
    ```
    This describes the pieces of information that someone might want to extract in a structured way from "{scenario_texts_label}" text passages.
    Please generate a JSON array containing {anthropic_obj_gen_group_size if should_use_claude else google_obj_gen_group_size} diverse JSON objects conforming to that schema, following the above instructions while doing so.
    """)
    
    resp_text: str
    
    if should_use_claude:
        anthropic_resp = anthropic_client.messages.create(
            system=anthropic_object_generation_sys_prompt, max_tokens=4096, temperature=anthropic_generation_temp,
            model= anthropic_model_specifier, messages=[{"role": "user", "content": user_prompt}])
        resp_text = anthropic_resp.content[0].text
    else:
        google_resp = google_client.generate_content(user_prompt)
        resp_text = google_resp.text
        if is_google_api_key_using_free_tier:
            time.sleep(30)#on free tier, gemini api is rate-limited to 2 requests per 60 seconds

    generated_objects: Optional[list[dict[str,Any]]]
    generated_objects, obj_gen_analysis = extract_json_doc_from_output(resp_text, is_obj_vs_arr=False)
    
    if generated_objects is None:
        logger.error(f"Failed to extract JSON objects from {model_nm} output for schema index {schema_idx}")
        increment_problem_counter(should_use_claude)
    else:
        expected_num_objs = (anthropic_obj_gen_group_size if should_use_claude else google_obj_gen_group_size)
        if len(generated_objects) != expected_num_objs:
            logger.error(f"{model_nm} generated {len(generated_objects)} objects instead of the expected {expected_num_objs} for schema index {schema_idx}\nResponse:{resp_text}")
            increment_problem_counter(should_use_claude)
        schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        for obj_idx, obj in enumerate(generated_objects):
            if not schema_validator.is_valid(obj):
                logger.error(f"{model_nm}-generated object {obj_idx} for schema index {schema_idx} failed schema validation\nSchema:{schema}\nObject:{json.dumps(obj, indent=4)}\nErrors:{"; ".join([str(err) for err in schema_validator.iter_errors(obj)])}")
                increment_problem_counter(should_use_claude)
    logger.debug(f"Using {model_nm}, generated {len(generated_objects)} objects for scenario {scenario_domain} - {scenario_texts_label}:\n{json.dumps(generated_objects, indent=4)}\n\nAnalysis of object generation:\n{obj_gen_analysis}")
    
    return generated_objects

def generate_text_passages(google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic],
                           schema_idx: int, schema: dict[str,Any], scenario_domain: str, scenario_texts_label: str,
                           json_objs: list[Optional[dict[str,Any]]], increment_problem_counter: Callable[[bool], None]
                           ) -> list[Optional[str]]:
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined
    should_use_claude: bool = google_client is None
    model_nm = "Claude" if should_use_claude else "Gemini"
    logger.info(f"Generating text passages with {model_nm} for scenario {scenario_domain} - {scenario_texts_label}")
    
    user_prompt_template = Template(d(f"""
    Here is a JSON schema for the domain {scenario_domain}:
    ```json
    {json.dumps(schema)}
    ```
    
    This describes the pieces of information that someone might want to extract in a structured way from "{scenario_texts_label}" text passages.
    Here is a JSON object that follows that schema:
    ```json
    ${{schema_generated_json_instance}}
    ```
    
    Please generate a “{scenario_texts_label}” free-text document that includes the JSON object's details, following the above instructions while doing so.
    """))
    
    text_passages = []
    
    for obj_idx, obj in enumerate(json_objs):
        if obj is None:
            text_passages.append(None)
            logger.debug(f"With {model_nm}, skipping text passage generation for {obj_idx}th of {len(json_objs)} objects for schema index {schema_idx} because that object's generation seems to have gone awry")
            continue
        
        user_prompt = user_prompt_template.safe_substitute(schema_generated_json_instance=(json.dumps(obj)))
        resp_text: str
        
        if should_use_claude:
            anthropic_resp = anthropic_client.messages.create(
                system=anthropic_text_passage_generation_sys_prompt, max_tokens=4096, temperature=anthropic_generation_temp,
                model= anthropic_model_specifier, messages=[{"role": "user", "content": user_prompt}])
            resp_text = anthropic_resp.content[0].text
        else:
            google_resp = google_client.generate_content(user_prompt)
            resp_text = google_resp.text
            if is_google_api_key_using_free_tier:
                time.sleep(30)#on free tier, gemini api is rate-limited to 2 requests per 60 seconds
        
        text_passage, text_gen_analysis = extract_text_passage_from_output(resp_text)
        if text_passage is None:
            logger.error(f"Failed to extract text passage from {model_nm} output for {obj_idx}th of {len(json_objs)} objects for schema index {schema_idx}\nResponse:{resp_text}")
            increment_problem_counter(should_use_claude)
        else:
            logger.debug(f"Using {model_nm}, generated a text passage from the {obj_idx}'th object for scenario {scenario_domain} - {scenario_texts_label}:\n{text_passage}\n\nAnalysis of text generation:\n{text_gen_analysis}")
        text_passages.append(text_passage)
    
    return text_passages


def main():
    
    gemini_obj_gen_problem_count = 0
    gemini_text_gen_problem_count = 0
    claude_obj_gen_problem_count = 0
    claude_text_gen_problem_count = 0
    reconstruction_from_gemini_texts_problem_count = 0
    reconstruction_from_claude_texts_problem_count = 0
    def increment_obj_gen_problem_count(was_claude_gen: bool):
        if was_claude_gen:
            nonlocal claude_obj_gen_problem_count
            claude_obj_gen_problem_count += 1
        else:
            nonlocal gemini_obj_gen_problem_count
            gemini_obj_gen_problem_count += 1
    
    def increment_text_gen_problem_count(was_claude_gen: bool):
        if was_claude_gen:
            nonlocal claude_text_gen_problem_count
            claude_text_gen_problem_count += 1
        else:
            nonlocal gemini_text_gen_problem_count
            gemini_text_gen_problem_count += 1
    
    def increment_reconstruction_problem_count(was_claude_generated_text_passage: bool):
        if was_claude_generated_text_passage:
            nonlocal reconstruction_from_claude_texts_problem_count
            reconstruction_from_claude_texts_problem_count += 1
        else:
            nonlocal reconstruction_from_gemini_texts_problem_count
            reconstruction_from_gemini_texts_problem_count += 1
    
    
    
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)

    google_generation_config_for_data_gen={"temperature": google_generation_temp, "max_output_tokens": 8192}
    google_generation_config_for_reconstruction={"temperature": google_reconstruction_temp, "max_output_tokens": 4096}
    
    google_client_for_obj_gen = google_genai.GenerativeModel(
        google_model_specifier, generation_config=google_generation_config_for_data_gen,
        safety_settings=safety_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        system_instruction=google_object_generation_sys_prompt)
    google_client_for_text_gen = google_genai.GenerativeModel(
        google_model_specifier, generation_config=google_generation_config_for_data_gen,
        safety_settings=safety_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        system_instruction=google_text_passage_generation_sys_prompt)
    google_client_for_reconstruction = google_genai.GenerativeModel(
        google_model_specifier, safety_settings=safety_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        system_instruction=google_object_reconstruction_sys_prompt, generation_config=google_generation_config_for_reconstruction)
    
    anthropic_client = anthropic.Anthropic(api_key=os.environ[anthropic_api_key_env])
    
    #teammates- you can temporarily edit these 2 numbers if you only want to work on certain schemas
    first_scenario_idx = 0
    last_scenario_idx = len(schemas)-1 if schemas else 0
    for should_use_claude in [True, False]:
        for scenario_idx in range(first_scenario_idx, last_scenario_idx):
            schema = schemas[scenario_idx]
            scenario_domain = scenario_domains[scenario_idx]
            scenario_texts_label = scenario_text_passage_descriptions[scenario_idx]
            
            google_client_to_use_for_obj_gen = None if should_use_claude else google_client_for_obj_gen
            google_client_to_use_for_text_gen = None if should_use_claude else google_client_for_text_gen
            google_client_to_use_for_reconstruction = None if should_use_claude else google_client_for_reconstruction
            anthropic_client_to_use = anthropic_client if should_use_claude else None
            json_objs = generate_json_objs(google_client_to_use_for_obj_gen, anthropic_client_to_use, scenario_idx,
                                           schema, scenario_domain, scenario_texts_label, increment_obj_gen_problem_count)
            text_passages = generate_text_passages(google_client_to_use_for_text_gen, anthropic_client_to_use,
                                                   scenario_idx, schema, scenario_domain, scenario_texts_label,
                                                   json_objs, increment_text_gen_problem_count)
            validate_generated_objects_texts(google_client_to_use_for_reconstruction, anthropic_client_to_use,
                                             scenario_idx, schema, scenario_domain, scenario_texts_label, json_objs,
                                             text_passages, increment_reconstruction_problem_count)
            
            with open((claude_objs_path if should_use_claude else gemini_objs_path)
                      / f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__objs.json", "w") as objs_file:
                json.dump(json_objs, objs_file, indent=4)
            with open((claude_texts_path if should_use_claude else gemini_texts_path)
                      / f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__texts.json", "w") as texts_file:
                json.dump(text_passages, texts_file, indent=4)
            
            
    num_objs_generated_with_gemini = (last_scenario_idx-first_scenario_idx+1) * google_obj_gen_group_size
    num_objs_generated_with_claude = (last_scenario_idx-first_scenario_idx+1) * anthropic_obj_gen_group_size
    logger.info(f"\nProblems encountered with Gemini (out of {num_objs_generated_with_gemini} objects & as many passages):\n"
                f"object generation: {gemini_obj_gen_problem_count}; text passage generation: {gemini_text_gen_problem_count}\n"
                f"Problems encountered with Claude (out of {num_objs_generated_with_claude} objects & as many passages):\n"
                f"object generation: {claude_obj_gen_problem_count}; text passage generation: {claude_text_gen_problem_count}\n"
                f"Problems encountered with object reconstruction from text passages:\n"
                f"When Claude was extracting from Gemini-generated text passages: {reconstruction_from_gemini_texts_problem_count};\n"
                f"When Gemini was extracting from Claude-generated text passages: {reconstruction_from_claude_texts_problem_count}")

if __name__ == "__main__":
    main()


