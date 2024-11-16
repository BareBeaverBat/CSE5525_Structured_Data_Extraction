import json
import re
from json import JSONDecodeError

from constants import ModelProvider
from logging_setup import create_logger
from trivial_util_funcs import find_last_re_match

logger = create_logger(__name__)


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
    proper_doc_end_pattern = re.compile(r"\}\s*```" if is_obj_vs_arr else r"\]\s*```")
    doc_end_match = find_last_re_match(proper_doc_end_pattern, json_output, json_start_idx)
    if doc_end_match:
        json_end_idx = doc_end_match.start()+1
    else:#TODO this branch is being hit when, from logs, it seems like that doesn't make sense; remove printout of model response on next line once this is figured out
        logger.debug(f"model output didn't use the ideal disambiguated end pattern for a json document within its output (the regex pattern \"{proper_doc_end_pattern}\" failed to match), relying on the current scenario's expected end-of-json-document character {json_doc_end_char}; full model response:\n{model_output}")
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


def assemble_chat_msgs(model_choice: ModelProvider, initial_prompt: str, ai_responses: list[str],
                       followup_prompts: list[str]) -> list[dict[str, str]]:
    ai_role = "assistant" if model_choice == ModelProvider.ANTHROPIC else \
        "model" if model_choice == ModelProvider.GOOGLE_DEEPMIND else "PLACEHOLDER_AI_ROLE"
    msg_body_key = "content" if model_choice == ModelProvider.ANTHROPIC else \
        "parts" if model_choice == ModelProvider.GOOGLE_DEEPMIND else "PLACEHOLDER_MSG_BODY_KEY"
    chat_msgs = [{"role": "user", msg_body_key: initial_prompt}]
    for ai_resp, followup_prompt in zip(ai_responses, followup_prompts):
        chat_msgs.append({"role": ai_role, msg_body_key: ai_resp})
        chat_msgs.append({"role": "user", msg_body_key: followup_prompt})
        
    return chat_msgs