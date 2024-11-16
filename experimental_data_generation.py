import json
import os
import statistics
from string import Template
from typing import Any, Optional, Callable

import anthropic
import google.generativeai as google_genai
from anthropic import Anthropic
from google.generativeai import GenerativeModel
from google.generativeai.types import safety_types
from jsonschema import Draft202012Validator

from constants import schemas_path, anthropic_api_key_env, google_model_specifier, anthropic_model_specifier, \
    anthropic_object_generation_sys_prompt, google_object_generation_sys_prompt, \
    google_text_passage_generation_sys_prompt, \
    anthropic_text_passage_generation_sys_prompt, anthropic_obj_gen_group_size, google_obj_gen_group_size, \
    google_generation_temp, anthropic_generation_temp, google_reconstruction_temp, \
    google_object_reconstruction_sys_prompt, claude_objs_path, gemini_objs_path, gemini_texts_path, claude_texts_path, \
    google_api_key_env, max_num_api_calls_for_retry_logic, ModelProvider
from data_loading import load_scenarios, load_objects_for_one_model_and_scenario, \
    load_text_passages_for_one_model_and_scenario
from logging_setup import create_logger
from misc_util_funcs import extract_text_passage_from_output, extract_json_doc_from_output, generate_with_model
from trivial_util_funcs import d
from validate_generated_json_objs_and_texts import validate_generated_objects_texts

logger = create_logger(__name__)


def generate_json_objs(google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic], schema_idx: int,
                       schema: dict[str,Any], scenario_domain: str, scenario_texts_label: str,
                       increment_problem_counter: Callable[[bool], None], target_num_objs: int) -> list[Optional[dict[str, Any]]]:
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined
    should_use_claude: bool = google_client is None
    model_nm = "Claude" if should_use_claude else "Gemini"
    logger.info(f"Generating {target_num_objs} objects with {model_nm} for scenario {scenario_domain} - {scenario_texts_label}")
    
    generated_objects: list[Optional[dict[str,Any]]] = []
    
    user_prompt = d(f"""
    Here is such a JSON schema for the domain "{scenario_domain}":
    ```json
    {json.dumps(schema)}
    ```
    This describes the pieces of information that someone might want to extract in a structured way from "{scenario_texts_label}" text passages.
    Please generate a JSON array containing {target_num_objs} diverse JSON objects conforming to that schema, following the above instructions while doing so.
    """)
    
    ai_responses: list[str] = []
    followup_prompts: list[str] = []
    
    for retry_idx in range(max_num_api_calls_for_retry_logic):
        assert len(ai_responses) == len(followup_prompts)
        resp_text: str
        obj_gen_analysis: str
        
        if retry_idx > 0:
            logger.debug(f"Retrying generation of JSON objects for scenario {schema_idx} {scenario_domain} - {scenario_texts_label} ({retry_idx} prior attempts)")
        
        resp_text = generate_with_model(
            ModelProvider.ANTHROPIC if should_use_claude else ModelProvider.GOOGLE_DEEPMIND, user_prompt, ai_responses,
            followup_prompts, google_client, anthropic_client, anthropic_object_generation_sys_prompt, 4096,
            anthropic_generation_temp, anthropic_model_specifier)
        
        curr_generated_objects, obj_gen_analysis, json_doc_problem_explanation = \
            extract_json_doc_from_output(resp_text, is_obj_vs_arr=False)
        valid_idxs_in_curr_round: list[int] = []
        
        error_feedback: str = ""
        schema_validation_feedback_msgs: list[str] = []
    
        if curr_generated_objects is None:
            logger.warning(f"Failed to extract JSON objects from {model_nm} output for schema index {schema_idx}")#model response will've been printed out already by the find-json-doc-substring-of-model-output method
            error_feedback = f"The response was not formatted as instructed, and so the JSON document could not be extracted from it. Details:\n{json_doc_problem_explanation}"
        else:
            num_objs_b4_curr_round = len(generated_objects)
            expected_num_objs_for_curr_round = target_num_objs-num_objs_b4_curr_round
            if len(curr_generated_objects) != expected_num_objs_for_curr_round:
                logger.warning(f"{model_nm} generated {len(curr_generated_objects)} objects instead of the expected {expected_num_objs_for_curr_round} for schema index {schema_idx}\nResponse:{resp_text}")
                error_feedback = f"There were not enough objects generated; only {len(curr_generated_objects)} were found when {target_num_objs-len(generated_objects)} were asked for.\n"
            schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            for obj_idx, obj in enumerate(curr_generated_objects):
                if schema_validator.is_valid(obj):
                    generated_objects.append(obj)
                    valid_idxs_in_curr_round.append(obj_idx)
                else:
                    schema_validation_errs = "; ".join([str(err) for err in schema_validator.iter_errors(obj)])
                    logger.warning(f"{model_nm}-generated object {obj_idx} for schema index {schema_idx} failed schema validation\nSchema:{schema}\nObject:{json.dumps(obj, indent=4)}\nErrors:{schema_validation_errs}")
                    schema_validation_feedback_msgs.append(f"The {obj_idx}th object from the most recent round failed schema validation:\nHere is the object:\n{json.dumps(obj)}\nHere are the schema validation errors:\n{schema_validation_errs}")
            if schema_validation_feedback_msgs:
                error_feedback += f"Some of the objects just generated failed to follow the schema:\n--------------\n{"\n---------------\n".join(schema_validation_feedback_msgs)}"
            logger.debug(f"Using {model_nm}, generated {len(curr_generated_objects)} objects for scenario {scenario_domain} - {scenario_texts_label}:\nValid indexes within this round were: {valid_idxs_in_curr_round}\n{json.dumps(curr_generated_objects, indent=4)}\n\nAnalysis of object generation:\n{obj_gen_analysis}\n\nGlobal case ids of objects: {", ".join([f"case id {model_nm}-{schema_idx}-{new_obj_idx}" for new_obj_idx in range(num_objs_b4_curr_round, len(generated_objects))])}")
        if len(generated_objects) == target_num_objs:
            break
        
        remaining_obj_quota = target_num_objs - len(generated_objects)
        ai_responses.append(resp_text)
        next_prompt = f"There were problems with that output:\n{error_feedback}\nPlease generate a JSON array containing {remaining_obj_quota} additional diverse JSON objects conforming to that schema, following the system prompt instructions."
        if len(generated_objects) > 0:
            next_prompt += f"\nDo not repeat any of the previously-generated objects that conformed to the schema."
            if len(schema_validation_feedback_msgs) > 0:
                next_prompt += f"You may, however, create schema-compliant versions of any of the objects from this past round that were flagged as failing schema validation."
        followup_prompts.append(next_prompt)
    else:
        num_none_fillers = target_num_objs - len(generated_objects)
        logger.error(f"Exceeded retry limit when generating json objects with {model_nm} for schema index {schema_idx}; only successfully created {len(generated_objects)} objects that conformed to the schema, so adding {num_none_fillers} None objects to fill the gap")
        increment_problem_counter(should_use_claude)
        generated_objects.extend([None] * num_none_fillers)
    
    logger.debug(f"Using {model_nm}, generated {len(generated_objects)} objects for scenario {scenario_domain} - {scenario_texts_label}:\n{json.dumps(generated_objects, indent=4)}")
    
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
    Here is a JSON schema for the domain "{scenario_domain}":
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
        resp_text: str = generate_with_model(
            ModelProvider.ANTHROPIC if should_use_claude else ModelProvider.GOOGLE_DEEPMIND, user_prompt, [], [],
            google_client, anthropic_client, anthropic_text_passage_generation_sys_prompt, 4096,
            anthropic_generation_temp, anthropic_model_specifier)
        
        text_passage, text_gen_analysis = extract_text_passage_from_output(resp_text)
        if text_passage is None:
            logger.error(f"Failed to extract text passage from {model_nm} output for {obj_idx}th of {len(json_objs)} objects for schema index {schema_idx}\nResponse:{resp_text}")
            increment_problem_counter(should_use_claude)
        else:
            logger.debug(f"Using {model_nm}, generated a text passage from the {obj_idx}'th object for scenario {scenario_domain} - {scenario_texts_label} (case id {model_nm}-{schema_idx}-{obj_idx}):\n{text_passage}\n\nAnalysis of text generation:\n{text_gen_analysis}")
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
    
    google_genai.configure(api_key=os.environ[google_api_key_env])
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
    
    extraction_qualities_for_gemini_generated_texts: dict[int, float] = {}
    extraction_qualities_for_claude_generated_texts: dict[int, float] = {}
    
    #TODO declare list for reports on validation failure cases for different model/scenario pairs
    
    #teammates- you can temporarily edit these 2 numbers if you only want to work on certain schemas
    first_scenario_idx = 0
    schema_idx_excl_bound = len(schemas)#TODO try running with this set to just 5
    for should_generate_with_claude in [True, False]:
        for scenario_idx in range(first_scenario_idx, schema_idx_excl_bound):
            schema = schemas[scenario_idx]
            scenario_domain = scenario_domains[scenario_idx]
            scenario_texts_label = scenario_text_passage_descriptions[scenario_idx]
            
            curr_objs_folder = claude_objs_path if should_generate_with_claude else gemini_objs_path
            curr_case_objs_path = curr_objs_folder / f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__objs.json"
            curr_texts_folder = claude_texts_path if should_generate_with_claude else gemini_texts_path
            curr_case_texts_path = curr_texts_folder / f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__texts.json"
            
            json_objs: list[dict[str,Any]] = load_objects_for_one_model_and_scenario(curr_objs_folder, schema,
                                                                                     scenario_idx) or []
            
            text_passages: list[str] = load_text_passages_for_one_model_and_scenario(curr_texts_folder, scenario_idx
                                                                                     ) or []
            assert len(json_objs) == len(text_passages)
            num_objs_needed_for_case = (anthropic_obj_gen_group_size if should_generate_with_claude
                                        else google_obj_gen_group_size) - len(json_objs)
        
            google_client_to_use_for_obj_gen = None if should_generate_with_claude else google_client_for_obj_gen
            google_client_to_use_for_text_gen = None if should_generate_with_claude else google_client_for_text_gen
            google_client_to_use_for_reconstruction = google_client_for_reconstruction if should_generate_with_claude else None
            anthropic_client_to_use_for_gen = anthropic_client if should_generate_with_claude else None
            anthropic_client_to_use_for_reconstruction = None if should_generate_with_claude else anthropic_client
            #TODO this returns list of analysis strings and mapping from obj idx to analysis string idx
            new_json_objs = generate_json_objs(google_client_to_use_for_obj_gen, anthropic_client_to_use_for_gen,
                                               scenario_idx, schema, scenario_domain, scenario_texts_label,
                                               increment_obj_gen_problem_count, num_objs_needed_for_case)
            #TODO this returns list of analysis strings
            new_text_passages = generate_text_passages(google_client_to_use_for_text_gen, anthropic_client_to_use_for_gen,
                                                   scenario_idx, schema, scenario_domain, scenario_texts_label,
                                                   new_json_objs, increment_text_gen_problem_count)
            logger.info(f"Starting auto-validation of {num_objs_needed_for_case} {"Claude" if should_generate_with_claude else "Gemini"}-generated objects and text passages for scenario {scenario_idx} \"{scenario_domain}\" - \"{scenario_texts_label}\"")
            #TODO this returns extraction analysis strings and full details for extraction evaluations
            avg_extraction_quality_for_one_models_scenario_data = validate_generated_objects_texts(
                google_client_to_use_for_reconstruction, anthropic_client_to_use_for_reconstruction, scenario_idx, schema, scenario_domain,
                scenario_texts_label, new_json_objs, new_text_passages, increment_reconstruction_problem_count)
            
            logger.info(f"Extraction quality for {scenario_domain} - {scenario_texts_label} when original object and text passage were generated by {"Claude" if should_generate_with_claude else "Gemini"}:\n{avg_extraction_quality_for_one_models_scenario_data}")
            if should_generate_with_claude:
                extraction_qualities_for_claude_generated_texts[scenario_idx] = avg_extraction_quality_for_one_models_scenario_data
            else:
                extraction_qualities_for_gemini_generated_texts[scenario_idx] = avg_extraction_quality_for_one_models_scenario_data
            
            #TODO add to json_objs and text_passages _only_ the ones that passed validation
            json_objs.extend(new_json_objs)
            text_passages.extend(new_text_passages)
            
            with open(curr_case_objs_path, "w") as objs_file:
                json.dump(json_objs, objs_file, indent=4)
            with open(curr_case_texts_path, "w") as texts_file:
                json.dump(text_passages, texts_file, indent=4)
            
            #TODO create (and add to list) a unified report on each case that didn't pass validation, with the original
            # object (and associated analysis string), text passage (and its analysis string), and reconstruction (with
            # its analysis string and the extraction evaluation)
            
            
    num_objs_generated_with_gemini = (schema_idx_excl_bound-first_scenario_idx) * google_obj_gen_group_size
    num_objs_generated_with_claude = (schema_idx_excl_bound-first_scenario_idx) * anthropic_obj_gen_group_size
    logger.info(f"\nProblems encountered with Gemini (out of {num_objs_generated_with_gemini} objects & as many passages):\n"
                f"object generation: {gemini_obj_gen_problem_count}; text passage generation: {gemini_text_gen_problem_count}\n"
                f"Problems encountered with Claude (out of {num_objs_generated_with_claude} objects & as many passages):\n"
                f"object generation: {claude_obj_gen_problem_count}; text passage generation: {claude_text_gen_problem_count}\n"
                f"Problems encountered with object reconstruction from text passages:\n"
                f"When Claude was extracting from Gemini-generated text passages: {reconstruction_from_gemini_texts_problem_count};\n"
                f"When Gemini was extracting from Claude-generated text passages: {reconstruction_from_claude_texts_problem_count}\n"
                f"Extraction qualities averaged across scenarios for texts made by Gemini: {statistics.mean(list(extraction_qualities_for_gemini_generated_texts.values()))};\n"
                f"Extraction qualities averaged across scenarios for texts made by Claude: {statistics.mean(list(extraction_qualities_for_claude_generated_texts.values()))}")
    for scenario_idx in range(first_scenario_idx, schema_idx_excl_bound):
        logger.info(f"Extraction quality for scenario {scenario_domains[scenario_idx]} - {scenario_text_passage_descriptions[scenario_idx]}:\n"
                    f"from texts generated by Claude: {extraction_qualities_for_claude_generated_texts[scenario_idx]};\n"
                    f"from texts generated by Gemini: {extraction_qualities_for_gemini_generated_texts[scenario_idx]}")
    #TODO write to a separate file the list of reports on validation failures for different model/scenario pairs

if __name__ == "__main__":
    main()


