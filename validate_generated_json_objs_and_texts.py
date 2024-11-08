import json
import os
import re
import time
from typing import Any

import anthropic
import google.generativeai as google_genai
from google.generativeai.generative_models import safety_types

from constants import schemas_path, claude_objs_path, gemini_objs_path, claude_texts_path, gemini_texts_path, \
    google_api_key_env, anthropic_api_key_env, google_model_specifier, anthropic_model_specifier
from logging_setup import create_logger
from misc_util_funcs import d

logger = create_logger(__name__)

scenario_domains: list[str] = []
scenario_text_passage_descriptions: list[str] = []

scenario_details_regex = r"(\d+)_([a-zA-Z0-9]+(_[a-zA-Z0-9]+)*)__(\w+).json"
# todo schema_index_regex so each loading script can double check that it's adding the things to their respective list in the correct order


schemas: list[dict[str, Any]] = []

claude_objects: list[list[dict[str, Any]]] = []
claude_text_passages: list[list[str]] = []

gemini_objects: list[list[dict[str, Any]]] = []
gemini_text_passages: list[list[str]] = []

for schema_filenm in sorted(os.listdir(schemas_path)):
    scenario_dtls_match = re.match(scenario_details_regex, schema_filenm)
    assert scenario_dtls_match is not None
    scenario_domains.append(scenario_dtls_match.group(2))
    scenario_text_passage_descriptions.append(scenario_dtls_match.group(4))
    
    with open(schemas_path / schema_filenm) as schema_file:
        curr_schema = json.load(schema_file)
        schemas.append(curr_schema)

for claude_obj_filenm in sorted(os.listdir(claude_objs_path)):
    with open(claude_objs_path / claude_obj_filenm) as claude_objs_file:
        curr_schema_claude_objs = json.load(claude_objs_file)
        assert isinstance(curr_schema_claude_objs, list)
        claude_objects.append(curr_schema_claude_objs)

for gemini_obj_filenm in sorted(os.listdir(gemini_objs_path)):
    with open(gemini_objs_path / gemini_obj_filenm) as gemini_objs_file:
        curr_schema_gemini_objs = json.load(gemini_objs_file)
        assert isinstance(curr_schema_gemini_objs, list)
        gemini_objects.append(curr_schema_gemini_objs)

for claude_texts_filenm in sorted(os.listdir(claude_texts_path)):
    with open(claude_texts_path / claude_texts_filenm) as claude_texts_file:
        curr_schema_claude_texts = json.load(claude_texts_file)
        assert isinstance(curr_schema_claude_texts, list)
        claude_text_passages.append(curr_schema_claude_texts)

for gemini_texts_filenm in sorted(os.listdir(gemini_texts_path)):
    with open(gemini_texts_path / gemini_texts_filenm) as gemini_texts_file:
        curr_schema_gemini_texts = json.load(gemini_texts_file)
        assert isinstance(curr_schema_gemini_texts, list)
        gemini_text_passages.append(curr_schema_gemini_texts)

assert len(scenario_domains) == len(scenario_text_passage_descriptions) == len(schemas) == len(claude_objects) == len(claude_text_passages) == len(gemini_objects) == len(gemini_text_passages)

google_genai.configure(api_key=os.environ[google_api_key_env])
google_generation_config={"response_mime_type": "application/json", "temperature": 0, "max_output_tokens": 4096}

anthropic_client = anthropic.Anthropic(api_key=os.environ[anthropic_api_key_env])

def validate_generated_objects_texts(was_claude_generated: bool, schema_idx: int):
    ground_truth_objects: list[dict[str, Any]] = gemini_objects[schema_idx] if was_claude_generated else claude_objects[schema_idx]
    text_passages: list[str] = gemini_text_passages[schema_idx] if was_claude_generated else claude_text_passages[schema_idx]
    schema = schemas[schema_idx]
    scenario_domain = scenario_domains[schema_idx]
    scenario_texts_label = scenario_text_passage_descriptions[schema_idx]
    logger.debug(f"Validating {"Claude" if was_claude_generated else "Gemini"}-generated objects and text passages for scenario {scenario_domain} - {scenario_texts_label} with the model {google_model_specifier if was_claude_generated else anthropic_model_specifier}")
    assert len(ground_truth_objects) == len(text_passages)
    
    structured_extraction_sys_prompt = d(f"""
    Here is a JSON schema:
    ```json
    {schema}
    ```
    
    This describes the pieces of information that someone might want to extract in a structured way from text passages in the scenario "{scenario_domain}- {scenario_texts_label}".
    
    Below, there will be a {scenario_texts_label} text passage. You must create a JSON object that follows the given schema and captures all schema-relevant information that is actually present in the text passage.
    If there is no mention of anything related to a given schema key in the text, don't include that schema key in the JSON object. For example, if the schema has an array-type key and the text actually indicates that the correct number of entries for that array-type field is 0, then include that key, but simply omit that key if the text says nothing at all that's related to that array-type key.
    
    Please only output the JSON object with no explanations, json-wrapping markdown syntax, etc.
    """)
    
    google_client = google_genai.GenerativeModel(
        google_model_specifier, safety_settings=safety_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        system_instruction=structured_extraction_sys_prompt, generation_config=google_generation_config)
    
    
    extracted_objects: list[dict[str, Any]] = []
    
    for passage_idx, passage in enumerate(text_passages):
        user_prompt = d(f"""
        Here is the {scenario_texts_label} text passage.
        ```
        {passage}
        ```
        """)
        
        json_output_text: str
        
        if was_claude_generated:
            google_resp = google_client.generate_content(user_prompt)
            json_output_text = google_resp.text
        else:
            anthropic_resp = anthropic_client.messages.create(
                system=structured_extraction_sys_prompt, max_tokens=4096, temperature=0, model= anthropic_model_specifier,
                messages=[{"role": "user", "content": user_prompt}]
            )
            json_output_text = anthropic_resp.content[0].text
        
        extracted_obj = json.loads(json_output_text)
        extracted_objects.append(extracted_obj)
        logger.debug(f"Using {"Gemini" if was_claude_generated else "Claude"}, extracted {passage_idx}'th object from text passage for scenario {scenario_domain} - {scenario_texts_label}:"
                     f"\n {json.dumps(extracted_obj, indent=4)}")
        if was_claude_generated:
            time.sleep(30)

    assert len(extracted_objects) == len(ground_truth_objects)
    logger.info(f"Successfully extracted objects from text passages for scenario {scenario_domain} - {scenario_texts_label}:"
                f"\n {json.dumps(extracted_objects, indent=4)}")
    #TODO use validation function to compare extracted_objects and ground_truth_objects
    


def main():
    start_schema_idx = 0
    schema_idx_excl_bound = len(schemas)
    for i in range(start_schema_idx, schema_idx_excl_bound):
        validate_generated_objects_texts(was_claude_generated=False, schema_idx=i)
        validate_generated_objects_texts(was_claude_generated=True, schema_idx=i)

if __name__ == "__main__":
    main()
