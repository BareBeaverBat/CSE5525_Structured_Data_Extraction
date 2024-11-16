import json
import os
import re
from pathlib import Path
from re import Pattern
from typing import Tuple, List, Any

from jsonschema.validators import Draft202012Validator

from logging_setup import create_logger

logger = create_logger(__name__)

scenario_details_regex = r"^(\d+)_([a-zA-Z0-9]+(_[a-zA-Z0-9]+)*)__(\w+).json"
scenario_idx_regex = r"^(\d+)"


def load_scenarios(scenarios_schemas_path: Path, scenario_dtls_regex: Pattern = scenario_details_regex) -> Tuple[List[str], List[str], List[dict[str, Any]]]:
    scenario_domains: list[str] = []
    scenario_text_passage_descriptions: list[str] = []

    schemas: list[dict[str, Any]] = []
    
    for schema_filenm in sorted(os.listdir(scenarios_schemas_path)):
        scenario_dtls_match = re.match(scenario_dtls_regex, schema_filenm)
        if scenario_dtls_match is None:
            logger.warning(f"schema file {schema_filenm} doesn't match the expected naming convention, skipping it")
            continue
        scenario_idx = int(scenario_dtls_match.group(1))
        assert scenario_idx == len(scenario_domains)
        scenario_domain_nm = scenario_dtls_match.group(2)
        scenario_domain_nm = scenario_domain_nm.replace("_", " ")
        scenario_domains.append(scenario_domain_nm)
        assert scenario_idx == len(scenario_text_passage_descriptions)
        scenario_text_passage_desc = scenario_dtls_match.group(4)
        scenario_text_passage_desc = scenario_text_passage_desc.replace("_", " ")
        scenario_text_passage_descriptions.append(scenario_text_passage_desc)

        assert scenario_idx == len(schemas)
        with open(scenarios_schemas_path / schema_filenm) as schema_file:
            curr_schema = json.load(schema_file)
        Draft202012Validator.check_schema(curr_schema)
        schemas.append(curr_schema)
    
    logger.info(f"Loaded {len(schemas)} scenarios")
    return scenario_domains, scenario_text_passage_descriptions, schemas


def load_one_models_objects(path_of_one_models_objects: Path, schemas: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    curr_model_objects: list[list[dict[str, Any]]] = []

    for obj_filenm in sorted(os.listdir(path_of_one_models_objects)):
        scenario_idx_match = re.match(scenario_idx_regex, obj_filenm)
        if scenario_idx_match is None:
            logger.warning(f"in folder {path_of_one_models_objects}, generated objects file {obj_filenm} doesn't match the expected naming convention, skipping it")
            continue
        scenario_idx = int(scenario_idx_match.group(1))
        assert scenario_idx == len(curr_model_objects)
        assert scenario_idx < len(schemas)
        with open(path_of_one_models_objects / obj_filenm) as file_of_one_model_objs_for_one_schema:
            curr_schema_curr_model_objs = json.load(file_of_one_model_objs_for_one_schema)
        assert isinstance(curr_schema_curr_model_objs, list)
        schema_validator = Draft202012Validator(schemas[scenario_idx], format_checker=Draft202012Validator.FORMAT_CHECKER)
        for obj in curr_schema_curr_model_objs:
            assert isinstance(obj, dict)
            schema_validator.validate(obj)
        curr_model_objects.append(curr_schema_curr_model_objs)
    
    logger.info(f"Loaded {len(curr_model_objects)} scenarios' json objects from the model-specific folder {path_of_one_models_objects}")
    return curr_model_objects


def load_one_models_text_passages(path_of_one_models_texts: Path) -> list[list[str]]:
    curr_model_text_passages: list[list[str]] = []

    for texts_filenm in sorted(os.listdir(path_of_one_models_texts)):
        scenario_idx_match = re.match(scenario_idx_regex, texts_filenm)
        if scenario_idx_match is None:
            logger.warning(f"in folder {path_of_one_models_texts}, generated texts file {texts_filenm} doesn't match the expected naming convention, skipping it")
            continue
        scenario_idx = int(scenario_idx_match.group(1))
        assert scenario_idx == len(curr_model_text_passages)
        with open(path_of_one_models_texts / texts_filenm) as file_of_one_model_texts_for_one_schema:
            curr_schema_texts = json.load(file_of_one_model_texts_for_one_schema)
        assert isinstance(curr_schema_texts, list)
        if not all(isinstance(text, str) or text is None for text in curr_schema_texts):
            logger.warning(f"all text passages in {texts_filenm} should be strings or null!")
        if None in curr_schema_texts:
            logger.warning(f"there are null text passages in {path_of_one_models_texts}/{texts_filenm}, skipping it")
        curr_model_text_passages.append(curr_schema_texts)
    
    logger.info(f"Loaded {len(curr_model_text_passages)} scenarios' text passages from the model-specific folder {path_of_one_models_texts}")
    return curr_model_text_passages
