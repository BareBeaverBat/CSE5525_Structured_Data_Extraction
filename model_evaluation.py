import re
from dataclasses import dataclass

from data_processing.data_loading import load_scenarios, load_data_split, load_evaluation_model_outputs
from data_processing.data_mngmt_defs import schemas_path, fewshot_examples_path, validation_set_path, test_set_path, \
    EvaluationModelOutputRecord, evaluation_models_output_path, evaluation_config_regex
from utils_and_defs.logging_setup import create_logger

logger = create_logger(__name__)


@dataclass
class ResultsForModelEvaluationConfig:
    model_spec: str
    fewshot_count: int
    is_cot_enabled: bool
    eval_model_outputs: list[EvaluationModelOutputRecord]


#TODO function that takes a given folder of evaluation output/result records and analyzes it, accumulating statistics
# about the model's performance overall and also its performance broken down by either scenario or by source/generator model
# and also writing a comprehensive report for human review of any model output that the auto-grader marked wrong (as with the report generated for auto-validation failures in experimental_data_generation.py)

#todo main function that loads schemas, fewshot dataset split, and evaluation dataset split, and then calls the above functions
# for each model in a list, storing the results somewhere?

def main():
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)
    
    fewshot_examples = load_data_split(fewshot_examples_path, schemas)
    validation_set = load_data_split(validation_set_path, schemas)
    test_set = load_data_split(test_set_path, schemas)
    
    evaluation_configs_results: list[ResultsForModelEvaluationConfig] = []
    
    for eval_config_outputs_path in evaluation_models_output_path.iterdir():
        if eval_config_outputs_path.is_dir():
            logger.warning(f"Skipping directory {eval_config_outputs_path} in {evaluation_models_output_path}")
            continue
        if eval_config_outputs_path.suffix != ".json":
            logger.warning(f"Skipping non-JSON file {eval_config_outputs_path} in {evaluation_models_output_path}")
            continue
        eval_config_details_match = re.match(evaluation_config_regex, eval_config_outputs_path.name)
        if not eval_config_details_match:
            logger.warning(f"Skipping evaluation output file {eval_config_outputs_path} that doesn't match the expected naming convention")
            continue
        eval_config_model_spec = eval_config_details_match.group(1)
        eval_config_fewshot_count = int(eval_config_details_match.group(3))
        eval_config_cot_enabled = eval_config_details_match.group(4) == "True"
        
        eval_config_model_outputs = load_evaluation_model_outputs(eval_config_outputs_path)
        evaluation_configs_results.append(ResultsForModelEvaluationConfig(
            eval_config_model_spec, eval_config_fewshot_count, eval_config_cot_enabled, eval_config_model_outputs
        ))
    
    
    pass

if __name__ == "__main__":
    main()
