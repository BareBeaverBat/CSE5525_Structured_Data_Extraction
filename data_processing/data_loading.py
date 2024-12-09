import json
import os
import re
from pathlib import Path
from re import Pattern
from typing import Tuple, List, Any, Optional

from jsonschema.validators import Draft202012Validator

from data_processing.data_mngmt_defs import DataSplitRecord, scenario_details_regex, scenario_idx_regex, \
    EvaluationModelOutputRecord
from utils_and_defs.logging_setup import create_logger

logger = create_logger(__name__)


def load_scenarios(scenarios_schemas_path: Path, scenario_dtls_regex: Pattern = scenario_details_regex) -> Tuple[List[str], List[str], List[dict[str, Any]]]:
    scenario_domains: list[str] = []
    scenario_text_passage_descriptions: list[str] = []

    schemas: list[dict[str, Any]] = []
    
    def schema_file_name_sorting_key(file_nm: str) -> int:
        match = re.match(scenario_dtls_regex, file_nm)
        return int(match.group(1)) if match else 0
    
    for schema_filenm in sorted(os.listdir(scenarios_schemas_path), key=schema_file_name_sorting_key):
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

def is_not_target_scenario(folder_path: Path, file_nm: str, target_scenario_idx: int) -> bool:
    scenario_idx_match = re.match(scenario_idx_regex, file_nm)
    if scenario_idx_match is None:
        logger.warning(f"in folder {folder_path}, generated file {file_nm} doesn't match the expected naming convention, skipping it")
        return True
    scenario_idx = int(scenario_idx_match.group(1))
    return scenario_idx != target_scenario_idx

def load_objects_for_one_model_and_scenario(path_of_one_models_objects: Path, schema: dict[str, Any],
                                            target_scenario_idx) -> Optional[list[dict[str, Any]]]:
    for obj_filenm in sorted(os.listdir(path_of_one_models_objects)):
        if is_not_target_scenario(path_of_one_models_objects, obj_filenm, target_scenario_idx):
            continue
        with open(path_of_one_models_objects / obj_filenm) as file_of_one_model_objs_for_one_schema:
            curr_model_objs = json.load(file_of_one_model_objs_for_one_schema)
        assert isinstance(curr_model_objs, list)
        schema_validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        for obj in curr_model_objs:
            assert isinstance(obj, dict)
            schema_validator.validate(obj)
        return curr_model_objs
    
    logger.info(f"Failed to find a file of json objects for scenario {target_scenario_idx} from the model-specific folder {path_of_one_models_objects}")
    return None


def load_text_passages_for_one_model_and_scenario(path_of_one_models_texts: Path, target_scenario_idx: int
                                                  ) -> Optional[list[str]]:
    for texts_filenm in sorted(os.listdir(path_of_one_models_texts)):
        if is_not_target_scenario(path_of_one_models_texts, texts_filenm, target_scenario_idx):
            continue
        with open(path_of_one_models_texts / texts_filenm) as file_of_one_model_texts_for_one_schema:
            curr_schema_texts = json.load(file_of_one_model_texts_for_one_schema)
        assert isinstance(curr_schema_texts, list)
        if any(not isinstance(text, str) and text is not None for text in curr_schema_texts):
            logger.warning(f"all text passages in {texts_filenm} should be strings or null in the path {path_of_one_models_texts}!")
        if None in curr_schema_texts:
            logger.warning(f"there are null text passages in {path_of_one_models_texts}/{texts_filenm}")
        return curr_schema_texts
    
    logger.info(f"Failed to find a file of text passages for scenario {target_scenario_idx} from the model-specific folder {path_of_one_models_texts}")
    return None


def load_data_split(split_path: Path, schemas: List[dict[str, Any]]) -> List[DataSplitRecord]:
    assert split_path.exists()
    assert split_path.is_file()
    assert split_path.suffix == ".json"
    with open(split_path) as split_file:
        split_data = json.load(split_file)
    assert isinstance(split_data, list)
    validators: list[Draft202012Validator] = [Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER) for schema in schemas]
    
    validated_records: list[DataSplitRecord] = []
    for record in split_data:
        data_record = DataSplitRecord(**record)
        validators[data_record.scenario_id].validate(data_record.object)
        validated_records.append(data_record)
    
    return validated_records

def load_evaluation_model_outputs(model_outputs_path: Path) -> list[EvaluationModelOutputRecord]:
    assert model_outputs_path.exists()
    assert model_outputs_path.is_file()
    assert model_outputs_path.suffix == ".json"
    with open(model_outputs_path) as model_outputs_file:
        model_outputs = json.load(model_outputs_file)
    assert isinstance(model_outputs, list)
    evaluation_model_output_records: list[EvaluationModelOutputRecord] = []
    for model_output in model_outputs:
        evaluation_model_output_records.append(EvaluationModelOutputRecord(**model_output))
    
    return evaluation_model_output_records
