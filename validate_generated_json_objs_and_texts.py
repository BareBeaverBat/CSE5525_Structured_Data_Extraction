import json
import os
import statistics
import time
from typing import Any, Optional, Callable

import anthropic
import google.generativeai as google_genai
from anthropic import Anthropic
from google.generativeai.generative_models import safety_types, GenerativeModel
from jsonschema.validators import Draft202012Validator

from constants import schemas_path, claude_objs_path, gemini_objs_path, claude_texts_path, gemini_texts_path, \
    google_api_key_env, anthropic_api_key_env, google_model_specifier, anthropic_model_specifier, \
    google_object_reconstruction_sys_prompt, anthropic_object_reconstruction_sys_prompt, \
    is_google_api_key_using_free_tier, anthropic_reconstruction_temp, google_reconstruction_temp, \
    max_num_api_calls_for_retry_logic, ModelProvider
from data_loading import load_scenarios, load_one_models_objects, load_one_models_text_passages
from json_obj_comparison import evaluate_extraction
from logging_setup import create_logger
from misc_util_funcs import d, extract_json_doc_from_output, assemble_chat_msgs

logger = create_logger(__name__)

def validate_generated_objects_texts(
        google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic], schema_idx: int, schema: dict[str,Any], scenario_domain: str,
        scenario_texts_label: str, ground_truth_objects: list[Optional[dict[str, Any]]], text_passages: list[Optional[str]],
        increment_problem_counter: Callable[[bool], None]) -> float:
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined0
    was_claude_generated: bool = anthropic_client is None
    src_model_nm = "Claude" if was_claude_generated else "Gemini"
    reconstructor_model = google_model_specifier if was_claude_generated else anthropic_model_specifier
    logger.info(f"Validating {src_model_nm}-generated objects and text passages for scenario {scenario_domain} - {scenario_texts_label} with the model {reconstructor_model}")
    assert len(ground_truth_objects) == len(text_passages)
    
    extracted_objects: list[Optional[dict[str, Any]]] = []
    
    for passage_idx, passage in enumerate(text_passages):
        if passage is None:
            extracted_objects.append(None)
            continue
        user_prompt = d(f"""
        Here is a JSON schema for the domain {scenario_domain}:
        ```json
        {json.dumps(schema)}
        ```
        Here is the {scenario_texts_label} text passage.
        ```
        {passage}
        ```
        Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in  or that is definitely implied by the text passage, following the above instructions while doing so.
        """)
        
        
        #TODO next commit, extract this inner for loop to helper method
        ai_responses: list[str] = []
        followup_prompts: list[str] = []
        
        extracted_object: Optional[dict[str, Any]] = None
        for retry_idx in range(max_num_api_calls_for_retry_logic):
            assert len(ai_responses) == len(followup_prompts)
            resp_text: str
            
            chat_msgs = assemble_chat_msgs(ModelProvider.GOOGLE_DEEPMIND if was_claude_generated else ModelProvider.ANTHROPIC,
                                           user_prompt, ai_responses, followup_prompts)
            if was_claude_generated:
                google_resp = google_client.generate_content(chat_msgs)
                resp_text = google_resp.text
                if is_google_api_key_using_free_tier:
                    time.sleep(30)#on free tier, gemini api is rate-limited to 2 requests per 60 seconds
            else:
                anthropic_resp = anthropic_client.messages.create(
                    system=anthropic_object_reconstruction_sys_prompt, max_tokens=4096, temperature=anthropic_reconstruction_temp,
                    model= anthropic_model_specifier, messages=chat_msgs)
                resp_text = anthropic_resp.content[0].text
        
            curr_extracted_obj, obj_gen_analysis, json_doc_problem_explanation = \
                extract_json_doc_from_output(resp_text, is_obj_vs_arr=True)
            
            error_feedback: str
            
            if curr_extracted_obj is None:
                logger.warning(f"Failed to extract an object of structured data from the {passage_idx}'th {src_model_nm}-generated text passage for scenario {schema_idx} {scenario_domain} - {scenario_texts_label}\nPassage:\n{passage}\nResponse:\n{resp_text}")
                error_feedback = f"The response was not formatted as instructed, and so the JSON document could not be extracted from it. Details:\n{json_doc_problem_explanation}"
            else:
                schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
                if schema_validator.is_valid(curr_extracted_obj):
                    logger.debug(f"Using {reconstructor_model}, extracted an object of structured data from the {passage_idx}'th {src_model_nm}-generated text passage for scenario {scenario_domain} - {scenario_texts_label}:\n{json.dumps(curr_extracted_obj, indent=4)}\nAnalysis:\n{obj_gen_analysis}")
                    extracted_object = curr_extracted_obj
                    break
                else:
                    schema_validation_errs = "; ".join([str(err) for err in schema_validator.iter_errors(curr_extracted_obj)])
                    logger.warning(f"The object reconstructed with {reconstructor_model} from {src_model_nm}'s {passage_idx}th passage for schema index {schema_idx} failed schema validation\nSchema:{json.dumps(schema, indent=4)}\nObject:{json.dumps(curr_extracted_obj, indent=4)}\nErrors:{schema_validation_errs};\nAnalysis:\n{obj_gen_analysis}")
                    error_feedback = f"The created object did not conform to the schema. Details:\n{schema_validation_errs}"
            
            ai_responses.append(resp_text)
            followup_prompts.append(f"There were problems with that output:\n{error_feedback}\nPlease try again, following the system-prompt and original-user-prompt instructions.")
        else:
            logger.error(f"Failed to extract a schema-compliant object of structured data from the {passage_idx}'th {src_model_nm}-generated text passage for scenario {schema_idx} {scenario_domain} - {scenario_texts_label}, even after {max_num_api_calls_for_retry_logic} tries\nPassage:\n{passage}")
            increment_problem_counter(was_claude_generated)
        
        extracted_objects.append(extracted_object)

    assert len(extracted_objects) == len(ground_truth_objects)
    logger.info(f"Successfully extracted objects from {src_model_nm}-generated text passages for scenario {scenario_domain} - {scenario_texts_label}")
    
    extraction_qualities = []
    
    for obj_idx, (extracted_obj, ground_truth_obj) in enumerate(zip(extracted_objects, ground_truth_objects)):
        if ground_truth_obj is not None:
            extraction_quality=0.0            
            if extracted_obj is not None:
                extraction_quality, expected_fact_recall, hallucination_count, differences = evaluate_extraction(extracted_obj, ground_truth_obj)
                if (1.0-extraction_quality) > 1e-8:#floating point effective-equality comparison
                    logger.error(f"Extraction quality for {src_model_nm}'s {obj_idx}th object for scenario "
                                 f"{schema_idx} {scenario_domain} - {scenario_texts_label} is {extraction_quality}, "
                                 f"expected fact recall is {expected_fact_recall}, hallucination count is {hallucination_count}, "
                                 f"and differences are {differences}\n"
                                 f"Original object:\n{json.dumps(ground_truth_obj, indent=4)}\n"
                                 f"Extracted object:\n{json.dumps(extracted_obj, indent=4)}\n"
                                 f"Text passage:\n{text_passages[obj_idx]}")
                    increment_problem_counter(was_claude_generated)
            extraction_qualities.append(extraction_quality)
    
    return statistics.mean(extraction_qualities)


def main():
    reconstruction_from_gemini_texts_problem_count = 0
    reconstruction_from_claude_texts_problem_count = 0
    def increment_reconstruction_problem_count(was_claude_generated_text_passage: bool):
        if was_claude_generated_text_passage:
            nonlocal reconstruction_from_claude_texts_problem_count
            reconstruction_from_claude_texts_problem_count += 1
        else:
            nonlocal reconstruction_from_gemini_texts_problem_count
            reconstruction_from_gemini_texts_problem_count += 1
    
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)

    claude_objects = load_one_models_objects(claude_objs_path, schemas)
    claude_text_passages = load_one_models_text_passages(claude_texts_path)
    
    gemini_objects = load_one_models_objects(gemini_objs_path, schemas)
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
    
    extraction_qualities_for_gemini_generated_texts: dict[int, float] = {}
    extraction_qualities_for_claude_generated_texts: dict[int, float] = {}
    for was_claude_generated in [True, False]:
        for scenario_idx in range(start_schema_idx, schema_idx_excl_bound):
            ground_truth_objects: list[dict[str, Any]] = gemini_objects[scenario_idx] if was_claude_generated else claude_objects[scenario_idx]
            text_passages: list[str] = gemini_text_passages[scenario_idx] if was_claude_generated else claude_text_passages[scenario_idx]
            schema = schemas[scenario_idx]
            scenario_domain = scenario_domains[scenario_idx]
            scenario_texts_label = scenario_text_passage_descriptions[scenario_idx]
            
            google_client_to_use = google_client if was_claude_generated else None
            anthropic_client_to_use = None if was_claude_generated else anthropic_client
            avg_extraction_quality_for_one_models_scenario_data = validate_generated_objects_texts(
                google_client_to_use, anthropic_client_to_use, scenario_idx, schema, scenario_domain,
                scenario_texts_label, ground_truth_objects, text_passages, increment_reconstruction_problem_count)
            if was_claude_generated:
                extraction_qualities_for_claude_generated_texts[scenario_idx] = avg_extraction_quality_for_one_models_scenario_data
            else:
                extraction_qualities_for_gemini_generated_texts[scenario_idx] = avg_extraction_quality_for_one_models_scenario_data
    logger.info(f"Problems encountered with object reconstruction from text passages:\n"
                f"When Claude was extracting from Gemini-generated text passages: {reconstruction_from_gemini_texts_problem_count};\n"
                f"When Gemini was extracting from Claude-generated text passages: {reconstruction_from_claude_texts_problem_count}")
    for scenario_idx in range(start_schema_idx, schema_idx_excl_bound):
        logger.info(f"Extraction quality for scenario {scenario_domains[scenario_idx]} - {scenario_text_passage_descriptions[scenario_idx]}:\n"
                    f"from texts generated by Claude: {extraction_qualities_for_claude_generated_texts[scenario_idx]};\n"
                    f"from texts generated by Gemini: {extraction_qualities_for_gemini_generated_texts[scenario_idx]}")

if __name__ == "__main__":
    main()
