import json
import re
import time
from json import JSONDecodeError
from typing import Optional, Any

import anthropic
from anthropic import Anthropic
import google.generativeai as google_genai
from google.generativeai import GenerativeModel
from jsonschema import Draft202012Validator

from ai_querying.ai_querying_defs import is_google_api_key_using_free_tier, \
    max_num_api_calls_for_anthropic_overloaded_retry_logic, max_num_api_calls_for_google_refusals_retry_logic, \
    ModelProvider, AnthropicClientBundle, OpenAiClientBundle, max_num_api_calls_for_openai_failures_retry_logic, \
    max_num_api_calls_for_schema_validation_retry_logic
from utils_and_defs.logging_setup import create_logger
from utils_and_defs.trivial_util_funcs import find_last_re_match, d
from validate_generated_json_objs_and_texts import logger

logger = create_logger(__name__)


#todo add flag is_cot
def extract_json_doc_from_output(model_output: str, is_obj_vs_arr: bool)-> (list | dict | None, str, str):
    """
    Extracts the single JSON document from the model output (which might also contain other text like CoT analysis)
    :param model_output: the output from the CoT model
    :param is_obj_vs_arr: whether the JSON output document is supposed to be an object or an array (True for object, False for array)
    :return: a tuple of the parsed JSON output document (None if not present or not parseable), the rest of the model
    output, and (if relevant) a string explaining what was wrong with the model's output
    """
    json_output: str
    rest_of_output: str
    problem_explanation: str = ""
    json_start_idx: int
    json_end_idx: int
    
    num_markdown_code_blocks = model_output.count("```")/2
    if num_markdown_code_blocks != 1:
        logger.debug(f"model output contained {num_markdown_code_blocks} markdown code blocks, not the expected 1")
    
    json_doc_start_char = "{" if is_obj_vs_arr else "["
    proper_doc_start_pattern = re.compile(r"```json\s*\{" if is_obj_vs_arr else r"```json\s*\[")
    imperfect_doc_start_pattern = re.compile(r"```\s*\{" if is_obj_vs_arr else r"```\s*\[")
    doc_start_match = find_last_re_match(proper_doc_start_pattern, model_output)
    if doc_start_match:
        json_start_idx = doc_start_match.end()-1
    else:
        logger.debug(f"model output didn't use the ideal disambiguated start pattern for a json document within its output, relying on finding a generic markdown code block in the response")
        doc_start_match = find_last_re_match(imperfect_doc_start_pattern, model_output)
        if doc_start_match:
            json_start_idx = doc_start_match.end()-1
        else:#note that, if the model fails to use a markdown code block, we can only salvage things if there's exactly one JSON document in the output
            logger.debug(f"model output didn't use a clearly disambiguated start pattern for a json document within its output, relying on the current scenario's expected start-of-json-document character {json_doc_start_char}")
            json_start_idx = model_output.find(json_doc_start_char)
    if json_start_idx == -1:
        logger.warning(f"model didn't generate an output containing JSON: {model_output}")
        return None, model_output, f"""Model output didn't contain a JSON document with a properly marked starting point; If there was a JSON document, it should've started with "```json" and then a newline and {json_doc_start_char}"""
    json_output = model_output[json_start_idx:]
    rest_of_output = model_output[:json_start_idx]
    
    json_doc_end_char = "}" if is_obj_vs_arr else "]"
    proper_doc_end_pattern = re.compile(r"}\s*```" if is_obj_vs_arr else r"]\s*```")
    doc_end_match = find_last_re_match(proper_doc_end_pattern, json_output)
    if doc_end_match:
        json_end_idx = doc_end_match.start()+1
    else:
        logger.debug(f"model output didn't use the ideal disambiguated end pattern for a json document within its output (the regex pattern \"{proper_doc_end_pattern}\" failed to match), relying on the current scenario's expected end-of-json-document character {json_doc_end_char}")
        json_end_idx = json_output.rfind(json_doc_end_char)+1
    if json_end_idx == -1:
        logger.warning(f"model output contained opening character for appropriate type of json document ({json_doc_start_char}) but not closing character for that type of json document ({json_doc_end_char}): model_output:\n {model_output}")
        return None, model_output, f"""Model output didn't contain a JSON document with a properly marked ending point; If there was a JSON document, it should've ended with {json_doc_start_char} and a newline and then "```" """
    
    rest_of_output += "\nJSON document was here\n"
    if len(json_output) > json_end_idx:
        rest_of_output += json_output[json_end_idx:]
    json_output = json_output[:json_end_idx]
    
    json_doc_obj = None
    try:
        json_doc_obj = json.loads(json_output)
    except JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON document from model output:\nError: {e}\nModel output(excluding JSON document):\n{rest_of_output}\nJSON document:\n{json_output}")
        json_doc_str_lines = e.doc.splitlines(keepends=True)
        bad_line = json_doc_str_lines[e.lineno-1]
        prior_line = "" if e.lineno == 1 else json_doc_str_lines[e.lineno-2]
        post_line = "" if e.lineno == len(json_doc_str_lines) else json_doc_str_lines[e.lineno]
        problem_explanation = (f"Failed to parse the JSON document that was found in the model output:\nError: {e}\n"
                               f"{"Line before problem line: `"+prior_line+"`\n" if prior_line else ""}"
                               f"Problem line: `{bad_line}`"
                               f"{"\nLine after problem line: `"+post_line+"`" if post_line else ""}")
    if json_doc_obj is not None and not (isinstance(json_doc_obj, dict) if is_obj_vs_arr else isinstance(json_doc_obj, list)):
        logger.warning(f"Model output contained a JSON document that was not an {['object' if is_obj_vs_arr else 'array']};\nJSON document in output: {json_output}\nParsed JSON: {json.dumps(json_doc_obj, indent=4)}")
        problem_explanation = f"Model was asked to produce a JSON document that was an {['object' if is_obj_vs_arr else 'array']}, but instead it produced a JSON document that was a{['n array' if isinstance(json_doc_obj, list) else 'n object' if isinstance(json_doc_obj, dict) else ' JSON primitive type']}"
        json_doc_obj = None
        
    return json_doc_obj, rest_of_output, problem_explanation

def extract_text_passage_from_output(model_output: str) -> (str|None, str):
    """
    Extracts a text passage (separated from the rest by markdown triple backticks) from the model output (which might also contain other text like CoT analysis)
    :param model_output: the output from the CoT model
    :return: a tuple of the isolated text document (None if not present) and the rest of the model output
    """
    text_passage: str
    rest_of_output: str
    passage_start_idx: int
    passage_end_idx: int
    
    num_markdown_code_blocks = model_output.count("```")/2
    if num_markdown_code_blocks != 1:
        logger.warning(f"model output contained {num_markdown_code_blocks} markdown code blocks, not the expected 1")
    
    proper_doc_start_pattern = re.compile(r"```(markdown)?[\t ]*\n?[\t ]*")
    doc_start_match = proper_doc_start_pattern.search(model_output)
    if doc_start_match:
        passage_start_idx = doc_start_match.end()
    else:
        logger.warning(f"model didn't generate an output containing a markdown-triple-backtick-separated passage: {model_output}")
        return None, model_output
    text_passage = model_output[passage_start_idx:]
    rest_of_output = model_output[:passage_start_idx]
    
    proper_doc_end_pattern = re.compile(r"[\t ]*\n?[\t ]*```")
    doc_end_match = proper_doc_end_pattern.search(text_passage)
    if doc_end_match:
        passage_end_idx = doc_end_match.start()
    else:
        logger.warning(f"model output contained opening triple-backtick-separator but not the closing triple-backtick-separator: model_output:\n {model_output}")
        return None, model_output
    
    rest_of_output += "\nText passage was here\n"
    if len(text_passage) > passage_end_idx:
        rest_of_output += text_passage[passage_end_idx:]
    text_passage = text_passage[:passage_end_idx]
    
    return text_passage, rest_of_output

#if the user prompts get much bigger, can break initial prompt into "initial_prompt_cacheable" and "initial_prompt_noncacheable"
def generate_with_model(
        model_choice: ModelProvider, initial_prompt: str, ai_responses: list[str], followup_prompts: list[str],
        google_client: GenerativeModel = None, anthropic_client_bundle: AnthropicClientBundle= None,
        openai_client_bundle: OpenAiClientBundle = None) -> str:
    resp_text: str = "Model failed to generate a response"
    
    if model_choice == ModelProvider.ANTHROPIC:
        assert anthropic_client_bundle is not None
        chat_msgs = [{"role": "user", "content": initial_prompt}]
        for ai_resp, followup_prompt in zip(ai_responses, followup_prompts):
            chat_msgs.append({"role": "assistant", "content": ai_resp})
            chat_msgs.append({"role": "user", "content": followup_prompt})
        
        reason_for_latest_attempt_failure = ""
        for attempt_idx in range(max_num_api_calls_for_anthropic_overloaded_retry_logic):
            try:
                anthropic_resp = anthropic_client_bundle.client.beta.prompt_caching.messages.create(
                    system=[
                        {
                            "type": "text",
                            "text": anthropic_client_bundle.sys_prompt,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ], max_tokens=anthropic_client_bundle.max_tokens, temperature=anthropic_client_bundle.temp,
                    model= anthropic_client_bundle.model_spec, messages=chat_msgs)
                resp_text = anthropic_resp.content[0].text
                logger.debug(f"Anthropic API call cache stats: {anthropic_resp.usage.cache_creation_input_tokens} "
                             f"tokens written, {anthropic_resp.usage.cache_read_input_tokens} tokens read")
                break
            except anthropic.InternalServerError as e:
                if e.status_code == 529:
                    num_min_delay = 2**attempt_idx
                    logger.info(f"Anthropic API call failed with an internal server error (saying that they're overloaded); retrying in {num_min_delay} minutes (attempt {attempt_idx+1}/{max_num_api_calls_for_anthropic_overloaded_retry_logic})")
                    time.sleep(60*num_min_delay)
                    reason_for_latest_attempt_failure = "server overloaded"
                else:
                    logger.error(f"Anthropic API call failed with an internal server error; status code: {e.status_code}; error message: {e.message}; prompts used in this call: {json.dumps(chat_msgs)}")
                    raise
        else:
            resp_text += " because " + reason_for_latest_attempt_failure
        
    elif model_choice == ModelProvider.GOOGLE_DEEPMIND:
        chat_msgs = [{"role": "user", "parts": initial_prompt}]
        for ai_resp, followup_prompt in zip(ai_responses, followup_prompts):
            chat_msgs.append({"role": "model", "parts": ai_resp})
            chat_msgs.append({"role": "user", "parts": followup_prompt})
        
        temp_to_use: Optional[float] = None
        
        reason_for_latest_attempt_failure = ""
        for attempt_idx in range(max_num_api_calls_for_google_refusals_retry_logic):
            google_resp = google_client.generate_content(
                chat_msgs, generation_config=None if temp_to_use is None else google_genai.GenerationConfig(temperature=temp_to_use))
            if google_resp.candidates and google_resp.parts:
                resp_text = google_resp.text
                break
            else:
                finish_reason = google_resp.candidates[0].finish_reason if google_resp.candidates else "not provided because no candidate completion"
                safety_ratings_str = "; ".join([
                                     f"(categ={safety_rating.category}, harm_prob={safety_rating.probability}, caused_block={safety_rating.blocked})"
                                     for safety_rating in google_resp.prompt_feedback.safety_ratings])
                logger.warning(f"Google API call failed to return any parts; finish reason was {finish_reason}; "
                               f"prompt was rejected for reason {google_resp.prompt_feedback.block_reason}; "
                               f"safety ratings: {safety_ratings_str}; "
                               f"retrying (attempt {attempt_idx+1}/{max_num_api_calls_for_google_refusals_retry_logic})")
                reason_for_latest_attempt_failure = (f"prompt rejected for reason {google_resp.prompt_feedback.block_reason}"
                                                     f" and finish reason was {finish_reason}; safety ratings: {safety_ratings_str}")
                
                if temp_to_use is None:
                    temp_to_use = 0.3
                else:
                    temp_to_use+=0.2
            if is_google_api_key_using_free_tier:
                time.sleep(30)#on free tier, gemini api is rate-limited to 2 requests per 60 seconds
        else:
            resp_text += " because " + reason_for_latest_attempt_failure
    elif model_choice == ModelProvider.OPENAI or model_choice == ModelProvider.DEEPINFRA:
        assert openai_client_bundle is not None
        chat_msgs = [
            {"role": "system", "content": openai_client_bundle.sys_prompt},
            {"role": "user", "content": initial_prompt}
        ]
        for ai_resp, followup_prompt in zip(ai_responses, followup_prompts):
            chat_msgs.append({"role": "assistant", "content": ai_resp})
            chat_msgs.append({"role": "user", "content": followup_prompt})
        
        reason_for_latest_attempt_failure = ""
        
        temp_to_use = openai_client_bundle.temp
        for attempt_idx in range(max_num_api_calls_for_openai_failures_retry_logic):
            openai_client_resp = openai_client_bundle.client.chat.completions.create(
                model=openai_client_bundle.model_spec, messages=chat_msgs, temperature=temp_to_use,
                max_completion_tokens=openai_client_bundle.max_tokens,
                response_format={ "type": "json_object" } if openai_client_bundle.is_response_forced_json
                else { "type": "text" }
            )
            actual_resp = openai_client_resp.choices[0]
            msg = actual_resp.message
            finish_reason = actual_resp.finish_reason
            if finish_reason == "stop":
                resp_text = msg.content
                assert resp_text is not None
                break
            elif finish_reason == "length":
                logger.warning(f"{model_choice} API call failed to return a completion because it reached the max tokens limit; retrying (attempt {attempt_idx+1}/{max_num_api_calls_for_openai_failures_retry_logic})")
                reason_for_latest_attempt_failure = "max tokens limit reached"
            elif finish_reason == "content_filter":
                logger.warning(f"{model_choice} API call failed to return a completion because of content filtering complaint \"{msg.refusal}\"; retrying (attempt {attempt_idx + 1}/{max_num_api_calls_for_openai_failures_retry_logic})")
                reason_for_latest_attempt_failure = f"content filtering, reason: {msg.refusal}"
                temp_to_use += 0.2
            else:
                logger.error(f"{model_choice} API call failed to return a completion; finish reason was {finish_reason}")
                raise RuntimeError(f"{model_choice} API call failed to return a completion; finish reason was unexpected value {finish_reason}")
        else:
            resp_text += " because " + reason_for_latest_attempt_failure
        
    else:
        raise ValueError(f"model_choice must be a value from the ModelProvider enum, but it was {model_choice}")
    
    return resp_text


def create_query_prompt_for_model_evaluation(
        scenario_domain: str, scenario_texts_label: str, schema: dict[str, Any], passage: str) -> str:
    user_prompt = d(f"""
        Here is a JSON schema for the domain "{scenario_domain}":
        ```json
        {json.dumps(schema, indent=2)}
        ```
        
        Here is the "{scenario_texts_label}" text passage.
        ```
        {passage}
        ```
        
        Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage, following the above instructions while doing so.
        """)
    return user_prompt


def extract_obj_from_passage_with_retry(
        model_choice: ModelProvider, extractor_model: str, passage: str, scenario_domain: str,
        scenario_texts_label: str, schema: dict[str, Any], passage_description: str, case_id: str,
        google_client: GenerativeModel = None, anthropic_client_bundle: AnthropicClientBundle= None,
        openai_client_bundle: OpenAiClientBundle = None) -> tuple[Optional[dict[str, Any]], str]:
    #todo flag for disabling the automatic validation/retry logic
    #todo flag for disabling cot (i.e. just interpret the response text as a json string)
    user_prompt = create_query_prompt_for_model_evaluation(scenario_domain, scenario_texts_label, schema, passage)
    ai_responses: list[str] = []
    followup_prompts: list[str] = []
    
    for retry_idx in range(max_num_api_calls_for_schema_validation_retry_logic):
        assert len(ai_responses) == len(followup_prompts)
        
        if retry_idx > 0:
            logger.debug(f"Retrying extraction of JSON object from {passage_description} ({retry_idx} prior attempts)")
        
        resp_text = generate_with_model(model_choice, user_prompt, ai_responses, followup_prompts, google_client,
                                        anthropic_client_bundle, openai_client_bundle)
        
        curr_extracted_obj, obj_gen_analysis, json_doc_problem_explanation = \
            extract_json_doc_from_output(resp_text, is_obj_vs_arr=True)
        error_feedback: str
        
        if curr_extracted_obj is None:
            logger.warning(f"Failed to extract an object of structured data from {passage_description}\nPassage:\n{passage}\nResponse:\n{resp_text}")
            error_feedback = f"The response was not formatted as instructed, and so the JSON document could not be extracted from it. Details:\n{json_doc_problem_explanation}"
        else:
            schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            if schema_validator.is_valid(curr_extracted_obj):
                logger.debug(f"Using {extractor_model}, extracted an object of structured data from {passage_description} (case id {case_id}):\n{json.dumps(curr_extracted_obj, indent=4)}\nAnalysis:\n{obj_gen_analysis}")
                all_attempts_analysis = ("\n".join([f"AI:\n{prior_ai_resp}\n\nFeedback:\n{prior_followup_prompt}" for prior_ai_resp, prior_followup_prompt in zip(ai_responses, followup_prompts)])
                                          + ("\nAI final turn:" if ai_responses else "") + obj_gen_analysis)
                return curr_extracted_obj, all_attempts_analysis
            else:
                schema_validation_errs = "; ".join(
                    [str(err) for err in schema_validator.iter_errors(curr_extracted_obj)])
                logger.warning(f"The object reconstructed with {extractor_model} from {passage_description} failed schema validation\nSchema:{json.dumps(schema, indent=4)}\nObject:{json.dumps(curr_extracted_obj, indent=4)}\nErrors:{schema_validation_errs};\nAnalysis:\n{obj_gen_analysis}")
                error_feedback = f"The created object did not conform to the schema. Details:\n{schema_validation_errs}"
        
        ai_responses.append(resp_text)
        followup_prompts.append(f"There were problems with that output:\n{error_feedback}\nPlease try again, following the system-prompt and original-user-prompt instructions.")
    
    logger.error(f"Failed to extract a schema-compliant object of structured data from {passage_description}, even after {max_num_api_calls_for_schema_validation_retry_logic} tries\nPassage:\n{passage}")
    all_attempts_analysis = ("\n".join([f"AI:\n{ai_resp}\n\nFeedback:\n{followup_prompt}" for
                                        ai_resp, followup_prompt in zip(ai_responses, followup_prompts)]))
    return None, all_attempts_analysis
