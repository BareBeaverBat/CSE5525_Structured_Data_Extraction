import json
import re
from re import Pattern, Match
import textwrap
from json import JSONDecodeError
from typing import Optional

from logging_setup import create_logger

logger = create_logger(__name__)


def d(multi_line_str: str) -> str:
    """
    abbreviation for removing superfluous start-of-line indenting from multi-line strings
    :param multi_line_str: a string value from a multi-line string expression
    :return: the multi-line string with any start-of-line whitespace that all lines have removed,
                plus any starting and ending newlines removed
    """
    return textwrap.dedent(multi_line_str).strip()


def find_last_re_match(regex: Pattern, text: str, start_pos: int = 0) -> Optional[Match]:
    """
    Finds the last match of the given regex in the given text
    :param regex: the compiled regex pattern to search for
    :param text: the text to search in
    :param start_pos: the starting position in the text to search from
    :return: the last match of the regex in the text, or None if no matches
    """
    matches = list(regex.finditer(text, start_pos))
    return matches[-1] if matches else None


def extract_json_doc_from_output(model_output: str, is_obj_vs_arr: bool)-> (list | dict | None, str):
    """
    Extracts the single JSON document from the model output (which might also contain other text like CoT analysis)
    :param model_output: the output from the CoT model
    :param is_obj_vs_arr: whether the JSON output document is supposed to be an object or an array (True for object, False for array)
    :return: a tuple of the parsed JSON output document (None if not present or not parseable) and the rest of the model output
    """
    json_output: str
    rest_of_output: str
    json_start_idx: int
    json_end_idx: int
    
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
        return None, model_output
    json_output = model_output[json_start_idx:]
    rest_of_output = model_output[:json_start_idx]
    
    json_doc_end_char = "}" if is_obj_vs_arr else "]"
    proper_doc_end_pattern = re.compile(f"{json_doc_end_char}\\s*```")
    doc_end_match = find_last_re_match(proper_doc_end_pattern, json_output, json_start_idx)
    if doc_end_match:
        json_end_idx = doc_end_match.start()+1
    else:
        logger.debug(f"model output didn't use the ideal disambiguated end pattern for a json document within its output, relying on the current scenario's expected end-of-json-document character {json_doc_end_char}")
        json_end_idx = json_output.rfind(json_doc_end_char)+1
    if json_end_idx == -1:
        logger.warning(f"model output contained opening character for appropriate type of json document ({json_doc_start_char}) but not closing character for that type of json document ({json_doc_end_char}): model_output:\n {model_output}")
        return None, model_output
    
    rest_of_output += "\nJSON document was here\n"
    if len(json_output) > json_end_idx:
        rest_of_output += json_output[json_end_idx:]
    json_output = json_output[:json_end_idx]
    
    json_doc_obj = None
    try:
        json_doc_obj = json.loads(json_output)
        assert isinstance(json_doc_obj, dict) if is_obj_vs_arr else isinstance(json_doc_obj, list)
    except JSONDecodeError as e:
        logger.error(f"Failed to parse JSON document from model output:\nError: {e}\nModel output(excluding JSON document):\n{rest_of_output}\nJSON document:\n{json_output}")
        
    return json_doc_obj, rest_of_output

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
    
    proper_doc_start_pattern = re.compile(r"```[\t ]*\n?[\t ]*")
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
