import json
import os
import statistics
from string import Template
from typing import Any, Optional, Callable
from datetime import datetime as dt

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
    google_api_key_env, max_num_api_calls_for_schema_validation_retry_logic, ModelProvider
from data_loading import load_scenarios, load_objects_for_one_model_and_scenario, \
    load_text_passages_for_one_model_and_scenario
from logging_setup import create_logger
from misc_util_funcs import extract_text_passage_from_output, extract_json_doc_from_output, generate_with_model
from trivial_util_funcs import d
from validate_generated_json_objs_and_texts import validate_generated_objects_texts

logger = create_logger(__name__)


def generate_json_objs(google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic], schema_idx: int,
                       schema: dict[str,Any], scenario_domain: str, scenario_texts_label: str,
                       increment_problem_counter: Callable[[bool], None], target_num_objs: int
                       ) -> (list[Optional[dict[str, Any]]], list[str], dict[int, int]):
    """
    
    :param google_client:
    :param anthropic_client:
    :param schema_idx:
    :param schema:
    :param scenario_domain:
    :param scenario_texts_label:
    :param increment_problem_counter:
    :param target_num_objs:
    :return: list of generated objects, list of analysis strings for each object generations, and mapping from object
    index to analysis string index (since an analysis string goes with a particular API call and a typical API call
    will produce more than 1 schema-compliant object)
    """
    assert (google_client is not None) ^ (anthropic_client is not None)#XOR- exactly one of them should be defined
    should_use_claude: bool = google_client is None
    model_nm = "Claude" if should_use_claude else "Gemini"
    logger.info(f"Generating {target_num_objs} objects with {model_nm} for scenario {scenario_domain} - {scenario_texts_label}")
    
    generated_objects: list[Optional[dict[str,Any]]] = []
    obj_gen_analysis_strs: list[str] = []
    obj_idx_to_analysis_idx: dict[int, int] = {}
    
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
    resp_text: str = ""
    
    for retry_idx in range(max_num_api_calls_for_schema_validation_retry_logic):
        assert len(ai_responses) == len(followup_prompts)
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
                    #this will become a valid analysis string index right after this for loop over current-round objects
                    obj_idx_to_analysis_idx[len(generated_objects)-1] = len(obj_gen_analysis_strs)
                    valid_idxs_in_curr_round.append(obj_idx)
                else:
                    schema_validation_errs = "; ".join([str(err) for err in schema_validator.iter_errors(obj)])
                    logger.warning(f"{model_nm}-generated object {obj_idx} for schema index {schema_idx} failed schema validation\nSchema:{schema}\nObject:{json.dumps(obj, indent=4)}\nErrors:{schema_validation_errs}")
                    schema_validation_feedback_msgs.append(f"The {obj_idx}th object from the most recent round failed schema validation:\nHere is the object:\n{json.dumps(obj)}\nHere are the schema validation errors:\n{schema_validation_errs}")
            if valid_idxs_in_curr_round:
                obj_gen_analysis_strs.append(obj_gen_analysis)
            if schema_validation_feedback_msgs:
                error_feedback += f"Some of the objects just generated failed to follow the schema:\n--------------\n{"\n---------------\n".join(schema_validation_feedback_msgs)}"
            logger.debug(f"Using {model_nm}, generated {len(curr_generated_objects)} objects for scenario {scenario_domain} - {scenario_texts_label}:\nValid indexes within this round were: {valid_idxs_in_curr_round}\n{json.dumps(curr_generated_objects, indent=4)}\n\nAnalysis of object generation:\n{obj_gen_analysis}\n\nGlobal case ids of objects: {", ".join([f"case id {model_nm}-{schema_idx}-{new_obj_idx}" for new_obj_idx in range(num_objs_b4_curr_round, len(generated_objects))])}")
        if len(generated_objects) >= target_num_objs:
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
        obj_gen_analysis_strs.append(resp_text)
        for obj_idx in range(len(generated_objects), target_num_objs):
            generated_objects.append(None)
            obj_idx_to_analysis_idx[obj_idx] = len(obj_gen_analysis_strs)-1
    
    logger.debug(f"Using {model_nm}, generated {len(generated_objects)} objects for scenario {scenario_domain} - {scenario_texts_label}:\n{json.dumps(generated_objects, indent=4)}")
    
    return generated_objects, obj_gen_analysis_strs, obj_idx_to_analysis_idx

def generate_text_passages(google_client: Optional[GenerativeModel], anthropic_client: Optional[Anthropic],
                           schema_idx: int, schema: dict[str,Any], scenario_domain: str, scenario_texts_label: str,
                           json_objs: list[Optional[dict[str,Any]]], increment_problem_counter: Callable[[bool], None]
                           ) -> (list[Optional[str]], list[str]):
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
    
    text_passages: list[Optional[str]] = []
    text_creation_analyses: list[str] = []
    
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
        text_creation_analyses.append(text_gen_analysis)
    
    return text_passages, text_creation_analyses


def main():
    run_start_ts = dt.now()
    
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
    
    #teammates- you can temporarily edit these 2 numbers if you only want to work on certain schemas
    first_scenario_idx = 0
    schema_idx_excl_bound = len(schemas)
    validation_report_filenm = f"validation_failures_report_{run_start_ts.isoformat()
                                    .replace(":", "_").replace(".", "_")}.md"
    with open(validation_report_filenm, "w") as validation_failures_file:
        validation_failures_file.write(f"Validation failures report for data generation run starting at {run_start_ts.isoformat()}  \n"
                                       f"Going from scenario {first_scenario_idx} ({scenario_domains[first_scenario_idx]} - {scenario_text_passage_descriptions[first_scenario_idx]})  \n"
                                       f"through scenario {schema_idx_excl_bound-1} ({scenario_domains[schema_idx_excl_bound-1]} - {scenario_text_passage_descriptions[schema_idx_excl_bound-1]})  \n"
                                       f"Google model specifier: {google_model_specifier}  \nAnthropic model specifier: {anthropic_model_specifier}\n\n")
    
    
    target_num_objs_for_gemini_by_scenario: dict[int,int] = {}
    target_num_objs_for_claude_by_scenario: dict[int,int] = {}
    num_objs_generated_with_gemini_by_scenario: dict[int,int] = {}
    num_objs_generated_with_claude_by_scenario: dict[int,int] = {}
    num_valid_objs_generated_with_gemini_by_scenario: dict[int,int] = {}
    num_valid_objs_generated_with_claude_by_scenario: dict[int,int] = {}
    
    for should_generate_with_claude in [True, False]:
        src_model_nm = "Claude" if should_generate_with_claude else "Gemini"
        for scenario_idx in range(first_scenario_idx, schema_idx_excl_bound):
            schema = schemas[scenario_idx]
            scenario_domain = scenario_domains[scenario_idx]
            scenario_texts_label = scenario_text_passage_descriptions[scenario_idx]
            
            curr_objs_folder = claude_objs_path if should_generate_with_claude else gemini_objs_path
            curr_case_objs_path = curr_objs_folder / (f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__objs.json".replace(" ", "_"))
            curr_texts_folder = claude_texts_path if should_generate_with_claude else gemini_texts_path
            curr_case_texts_path = curr_texts_folder / (f"{scenario_idx}_{scenario_domain}__{scenario_texts_label}__texts.json".replace(" ", "_"))
            
            json_objs: list[dict[str,Any]] = load_objects_for_one_model_and_scenario(curr_objs_folder, schema,
                                                                                     scenario_idx) or []
            text_passages: list[str] = load_text_passages_for_one_model_and_scenario(curr_texts_folder, scenario_idx
                                                                                     ) or []
            assert len(json_objs) == len(text_passages)
            num_objs_needed_for_case = (anthropic_obj_gen_group_size if should_generate_with_claude
                                        else google_obj_gen_group_size) - len(json_objs)
            if num_objs_needed_for_case <= 0:
                logger.info(f"Skipping generation of objects and text passages for scenario {scenario_idx} \"{scenario_domain}\" - \"{scenario_texts_label}\" because the needed number of objects has already been generated")
                continue
            
            if should_generate_with_claude:
                target_num_objs_for_claude_by_scenario[scenario_idx] = num_objs_needed_for_case
            else:
                target_num_objs_for_gemini_by_scenario[scenario_idx] = num_objs_needed_for_case
            
            google_client_to_use_for_obj_gen = None if should_generate_with_claude else google_client_for_obj_gen
            google_client_to_use_for_text_gen = None if should_generate_with_claude else google_client_for_text_gen
            google_client_to_use_for_reconstruction = google_client_for_reconstruction if should_generate_with_claude else None
            anthropic_client_to_use_for_gen = anthropic_client if should_generate_with_claude else None
            anthropic_client_to_use_for_reconstruction = None if should_generate_with_claude else anthropic_client
            new_json_objs, obj_gen_analyses, new_obj_to_analysis_map = generate_json_objs(
                google_client_to_use_for_obj_gen, anthropic_client_to_use_for_gen, scenario_idx, schema, scenario_domain,
                scenario_texts_label, increment_obj_gen_problem_count, num_objs_needed_for_case)
            new_text_passages, text_gen_analyses = generate_text_passages(
                google_client_to_use_for_text_gen, anthropic_client_to_use_for_gen, scenario_idx, schema,
                scenario_domain, scenario_texts_label, new_json_objs, increment_text_gen_problem_count)
            
            num_objs_and_texts_generated = sum([1 for text in new_text_passages if text is not None])
            if should_generate_with_claude:
                num_objs_generated_with_claude_by_scenario[scenario_idx] = num_objs_and_texts_generated
            else:
                num_objs_generated_with_gemini_by_scenario[scenario_idx] = num_objs_and_texts_generated
            
            logger.info(f"Starting auto-validation of {num_objs_needed_for_case} {src_model_nm}-generated objects and text passages for scenario {scenario_idx} \"{scenario_domain}\" - \"{scenario_texts_label}\"")
            (avg_extraction_quality_for_case, val_failed_objs, val_failed_extraction_analyses,
             val_failed_extraction_qualities, val_failed_fact_recalls, val_failed_hallucination_counts,
             val_failed_extraction_differences) = validate_generated_objects_texts(
                google_client_to_use_for_reconstruction, anthropic_client_to_use_for_reconstruction, scenario_idx,
                schema, scenario_domain, scenario_texts_label, new_json_objs, new_text_passages,
                increment_reconstruction_problem_count)
            
            logger.info(f"Extraction quality for {scenario_idx} {scenario_domain} - {scenario_texts_label} was {avg_extraction_quality_for_case} when original object and text passage were generated by {src_model_nm}")
            if should_generate_with_claude:
                extraction_qualities_for_claude_generated_texts[scenario_idx] = avg_extraction_quality_for_case
            else:
                extraction_qualities_for_gemini_generated_texts[scenario_idx] = avg_extraction_quality_for_case

            validation_passed_new_json_objs = [new_json_objs[obj_idx] for obj_idx in range(len(new_json_objs))
                                               if obj_idx not in val_failed_objs]
            validation_passed_new_text_passages = [new_text_passages[obj_idx] for obj_idx in range(len(new_text_passages))
                                                   if obj_idx not in val_failed_objs]
            json_objs.extend(validation_passed_new_json_objs)
            text_passages.extend(validation_passed_new_text_passages)
            
            with open(curr_case_objs_path, "w") as objs_file:
                json.dump(json_objs, objs_file, indent=4)
            with open(curr_case_texts_path, "w") as texts_file:
                json.dump(text_passages, texts_file, indent=4)
            
            if should_generate_with_claude:
                num_valid_objs_generated_with_claude_by_scenario[scenario_idx] = len(validation_passed_new_json_objs)
            else:
                num_valid_objs_generated_with_gemini_by_scenario[scenario_idx] = len(validation_passed_new_json_objs)
            
            with open(validation_report_filenm, "a", encoding="utf-8") as validation_failures_file:
                for failed_obj_idx in val_failed_objs:
                    validation_failures_file.write("\n----------------------------\n----------------------------\n\n"
                        f"# Object {failed_obj_idx} for scenario {scenario_idx} \"{scenario_domain}\" - \"{scenario_texts_label}\" failed validation:\n"
                        f"case id {src_model_nm}-{scenario_idx}-{failed_obj_idx}  \nNote that object index is within current run\n"
                        f"## New object:\n```json\n{json.dumps(new_json_objs[failed_obj_idx], indent=4)}\n```\n"
                        f"## Extracted object:\n```json\n{json.dumps(val_failed_objs[failed_obj_idx], indent=4)}\n```\n"
                        f"## Extraction Evaluation\n"
                        f"Extraction quality: {val_failed_extraction_qualities[failed_obj_idx]:.4f} ;"
                        f"Fact recall: {val_failed_fact_recalls[failed_obj_idx]:.4f}; "
                        f"Hallucination count: {val_failed_hallucination_counts[failed_obj_idx]}  \n"
                        f"Extraction differences: {val_failed_extraction_differences[failed_obj_idx]}\n"
                        f"## Text passage:\n{new_text_passages[failed_obj_idx]}\n"
                        f"## Analysis of object generation:\n{obj_gen_analyses[new_obj_to_analysis_map[failed_obj_idx]]}\n"
                        f"## Analysis of text generation:\n{text_gen_analyses[failed_obj_idx]}\n"
                        f"## Analysis of extraction:\n{val_failed_extraction_analyses[failed_obj_idx]}"
                    )
    target_num_objs_for_gemini = sum(target_num_objs_for_gemini_by_scenario.values())
    target_num_objs_for_claude = sum(target_num_objs_for_claude_by_scenario.values())
    num_objs_generated_with_gemini =sum(num_objs_generated_with_gemini_by_scenario.values())
    num_objs_generated_with_claude = sum(num_objs_generated_with_claude_by_scenario.values())
    num_valid_objs_generated_with_gemini =sum(num_valid_objs_generated_with_gemini_by_scenario.values())
    num_valid_objs_generated_with_claude = sum(num_valid_objs_generated_with_claude_by_scenario.values())
    logger.info(f"\nProblems encountered with Gemini (out of {num_objs_generated_with_gemini} actually-generated objects & as many passages, where the goal had been {target_num_objs_for_gemini}):\n"
                f"object generation: {gemini_obj_gen_problem_count}; text passage generation: {gemini_text_gen_problem_count}\n"
                f"Problems encountered with Claude (out of {num_objs_generated_with_claude} actually-generated objects & as many passages, where the goal had been {target_num_objs_for_claude}):\n"
                f"object generation: {claude_obj_gen_problem_count}; text passage generation: {claude_text_gen_problem_count}\n"
                f"Problems encountered with object reconstruction from text passages:\n"
                f"When Claude was extracting from Gemini-generated text passages: {reconstruction_from_gemini_texts_problem_count};\n"
                f"When Gemini was extracting from Claude-generated text passages: {reconstruction_from_claude_texts_problem_count}\n"
                f"Extraction qualities averaged across scenarios for texts made by Gemini: {statistics.mean(list(extraction_qualities_for_gemini_generated_texts.values()))};\n"
                f"Extraction qualities averaged across scenarios for texts made by Claude: {statistics.mean(list(extraction_qualities_for_claude_generated_texts.values()))}\n"
                f"Number of valid objects generated by Gemini: {num_valid_objs_generated_with_gemini}; "
                f"Number of valid objects generated by Claude: {num_valid_objs_generated_with_claude}")
    for scenario_idx in range(first_scenario_idx, schema_idx_excl_bound):
        logger.info(f"Extraction quality for scenario {scenario_domains[scenario_idx]} - {scenario_text_passage_descriptions[scenario_idx]}:\n"
                    f"from texts generated by Claude: {extraction_qualities_for_claude_generated_texts[scenario_idx]};\n"
                    f"from texts generated by Gemini: {extraction_qualities_for_gemini_generated_texts[scenario_idx]}\n"
                    f"Number of valid objects generated by Gemini: {num_valid_objs_generated_with_gemini_by_scenario[scenario_idx]} out of {num_objs_generated_with_gemini_by_scenario[scenario_idx]} total objects generated by Gemini for that scenario (and where the target number of objects was {target_num_objs_for_gemini_by_scenario[scenario_idx]})\n"
                    f"Number of valid objects generated by Claude: {num_valid_objs_generated_with_claude_by_scenario[scenario_idx]} out of {num_objs_generated_with_claude_by_scenario[scenario_idx]} total objects generated by Claude for that scenario (and where the target number of objects was {target_num_objs_for_claude_by_scenario[scenario_idx]})")

if __name__ == "__main__":
    main()


