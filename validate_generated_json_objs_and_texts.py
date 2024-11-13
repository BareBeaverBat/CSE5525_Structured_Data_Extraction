import json
import os
import time
from typing import Any, Optional

import anthropic
import google.generativeai as google_genai
from anthropic import Anthropic
from google.generativeai.generative_models import safety_types, GenerativeModel
from jsonschema.validators import Draft202012Validator

from constants import schemas_path, claude_objs_path, gemini_objs_path, claude_texts_path, gemini_texts_path, \
    google_api_key_env, anthropic_api_key_env, google_model_specifier, anthropic_model_specifier, \
    google_object_reconstruction_sys_prompt, anthropic_object_reconstruction_sys_prompt, \
    is_google_api_key_using_free_tier, anthropic_reconstruction_temp, google_reconstruction_temp
from data_loading import load_scenarios, load_one_models_objects, load_one_models_text_passages
from logging_setup import create_logger
from misc_util_funcs import d, extract_json_doc_from_output

logger = create_logger(__name__)

def validate_generated_objects_texts(
        google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic], schema_idx: int, schema: dict[str,Any], scenario_domain: str,
        scenario_texts_label: str, ground_truth_objects: list[dict[str, Any]], text_passages: list[str]):
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined0
    was_claude_generated: bool = anthropic_client is None
    src_model_nm = "Claude" if was_claude_generated else "Gemini"
    reconstructor_model = google_model_specifier if was_claude_generated else anthropic_model_specifier
    logger.info(f"Validating {src_model_nm}-generated objects and text passages for scenario {scenario_domain} - {scenario_texts_label} with the model {reconstructor_model}")
    assert len(ground_truth_objects) == len(text_passages)
    
    extracted_objects: list[dict[str, Any]] = []
    
    for passage_idx, passage in enumerate(text_passages):
        user_prompt = d(f"""
        Here is a JSON schema for the domain {scenario_domain}:
        ```json
        {schema}
        ```
        Here is the {scenario_texts_label} text passage.
        ```
        {passage}
        ```
        Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in  or that is definitely implied by the text passage, following the above instructions while doing so.
        """)
        
        resp_text: str
        
        if was_claude_generated:
            google_resp = google_client.generate_content(user_prompt)
            resp_text = google_resp.text
            if is_google_api_key_using_free_tier:
                time.sleep(30)#on free tier, gemini api is rate-limited to 2 requests per 60 seconds
        else:
            anthropic_resp = anthropic_client.messages.create(
                system=anthropic_object_reconstruction_sys_prompt, max_tokens=4096, temperature=anthropic_reconstruction_temp,
                model= anthropic_model_specifier, messages=[{"role": "user", "content": user_prompt}])
            resp_text = anthropic_resp.content[0].text
        
        extracted_obj, obj_gen_analysis = extract_json_doc_from_output(resp_text, is_obj_vs_arr=True)
        if extracted_obj is None:
            logger.error(f"Failed to extract an object of structured data from the {passage_idx}'th {src_model_nm}-generated text passage for scenario {schema_idx} {scenario_domain} - {scenario_texts_label}\nPassage:\n{passage}\nResponse:\n{resp_text}")
        else:
            schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            if schema_validator.is_valid(extracted_obj):
                logger.debug(f"Using {reconstructor_model}, extracted an object of structured data from the {passage_idx}'th {src_model_nm}-generated text passage for scenario {scenario_domain} - {scenario_texts_label}:\n"
                             f"{json.dumps(extracted_obj, indent=4)}")
            else:
                logger.error(f"The object reconstructed with {reconstructor_model} from {src_model_nm}'s {passage_idx}th passage for schema index {schema_idx} failed schema validation\nSchema:{schema}\nObject:{extracted_obj}\nErrors:{"; ".join([str(err) for err in schema_validator.iter_errors(extracted_obj)])}")
        extracted_objects.append(extracted_obj)

    assert len(extracted_objects) == len(ground_truth_objects)
    logger.info(f"Successfully extracted objects from {src_model_nm}-generated text passages for scenario {scenario_domain} - {scenario_texts_label}")
    #TODO use validation function to compare extracted_objects and ground_truth_objects
    


def main():
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)

    claude_objects = load_one_models_objects(claude_objs_path)
    claude_text_passages = load_one_models_text_passages(claude_texts_path)
    
    gemini_objects = load_one_models_objects(gemini_objs_path)
    gemini_text_passages = load_one_models_text_passages(gemini_texts_path)
    
    assert (len(scenario_domains) == len(scenario_text_passage_descriptions) == len(schemas) == len(claude_objects)
            == len(claude_text_passages) == len(gemini_objects) == len(gemini_text_passages))
    
    google_genai.configure(api_key=os.environ[google_api_key_env])
    google_generation_config={"temperature": google_reconstruction_temp, "max_output_tokens": 4096}
    
    google_client = google_genai.GenerativeModel(
        google_model_specifier, safety_settings=safety_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        system_instruction=google_object_reconstruction_sys_prompt, generation_config=google_generation_config)
    
    anthropic_client = anthropic.Anthropic(api_key=os.environ[anthropic_api_key_env])

    start_schema_idx = 0
    schema_idx_excl_bound = len(schemas)
    logger.debug(f"Validating generated objects and text passages for scenarios {scenario_domains[start_schema_idx]} - {scenario_text_passage_descriptions[start_schema_idx]} to {scenario_domains[schema_idx_excl_bound - 1]} - {scenario_text_passage_descriptions[schema_idx_excl_bound - 1]}")
    for was_claude_generated in [True, False]:
        for scenario_idx in range(start_schema_idx, schema_idx_excl_bound):
            ground_truth_objects: list[dict[str, Any]] = gemini_objects[scenario_idx] if was_claude_generated else claude_objects[scenario_idx]
            text_passages: list[str] = gemini_text_passages[scenario_idx] if was_claude_generated else claude_text_passages[scenario_idx]
            schema = schemas[scenario_idx]
            scenario_domain = scenario_domains[scenario_idx]
            scenario_texts_label = scenario_text_passage_descriptions[scenario_idx]
            
            google_client_to_use = google_client if was_claude_generated else None
            anthropic_client_to_use = None if was_claude_generated else anthropic_client
            validate_generated_objects_texts(google_client_to_use, anthropic_client_to_use, scenario_idx, schema,
                                             scenario_domain, scenario_texts_label, ground_truth_objects, text_passages)

if __name__ == "__main__":
    main()
