import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Literal

import numpy as np
from openai import OpenAI

from ai_querying.ai_querying_util_funcs import create_query_prompt_for_model_evaluation, \
    extract_obj_from_passage_with_retry
from ai_querying.system_prompts import model_evaluation_with_cot_system_prompt_prefix, \
    model_evaluation_without_cot_system_prompt_prefix
from data_processing.data_loading import load_scenarios, load_data_split
from data_processing.data_mngmt_defs import DataSplitRecord, EvaluationModelOutputRecord, schemas_path, \
    fewshot_examples_path, validation_set_path, evaluation_models_output_path, test_set_path
from ai_querying.ai_querying_defs import openai_api_key_env, deepinfra_api_key_env, OpenAiClientBundle, ModelProvider
from utils_and_defs.logging_setup import create_logger

logger = create_logger(__name__)


@dataclass
class ModelEvaluationConfig:
    client: OpenAI
    provider: ModelProvider
    model_spec: str
    fewshot_count: int
    is_cot_enabled: bool
    
    def label(self) -> str:
        return f"Model__{self.model_spec.replace("/", "_").replace(".", "_")
        }__Fewshot__{self.fewshot_count}__CoT__{self.is_cot_enabled}"
    
    def output_path(self) -> Path:
        return evaluation_models_output_path / f"{self.label()}.json"


def create_sys_prompt_for_model_evaluation(
        eval_config: ModelEvaluationConfig, chosen_fewshot_examples: list[DataSplitRecord], scenario_domains: list[str],
        scenario_text_passage_descriptions: list[str], schemas: list[dict[str, Any]]) -> str:
    cot = eval_config.is_cot_enabled
    system_prompt = model_evaluation_with_cot_system_prompt_prefix if cot \
        else model_evaluation_without_cot_system_prompt_prefix
    
    if eval_config.fewshot_count > 0:
        system_prompt += '\n\nPartial examples of good responses (omitting CoT analysis for brevity):' \
            if cot else '\n\nExamples of good responses:'
        
        for example_idx_in_prompt, fewshot_example in enumerate(chosen_fewshot_examples):
            system_prompt += f"\n\n--------------------\n## Request {example_idx_in_prompt + 1}\n\n"
            system_prompt += create_query_prompt_for_model_evaluation(
                scenario_domains[fewshot_example.scenario_id],
                scenario_text_passage_descriptions[fewshot_example.scenario_id], schemas[fewshot_example.scenario_id],
                fewshot_example.text_passage)
            system_prompt += f"\n\n## Response {example_idx_in_prompt + 1}\n\n"
            system_prompt += "... (CoT analysis) ...\n\n```json\n" if cot else ""
            system_prompt += json.dumps(fewshot_example.object, indent=2)
            system_prompt += "\n```" if cot else ""
    
    return system_prompt


def generate_outputs_for_evaluation(
        eval_config: ModelEvaluationConfig, scenario_domains: list[str], scenario_text_passage_descriptions: list[str],
        schemas: list[dict[str, Any]], fewshot_examples: list[DataSplitRecord],
        evaluation_src_set: list[DataSplitRecord], src_set_nm: Literal["validation", "test"]
) -> list[EvaluationModelOutputRecord]:
    eval_model_outputs: list[EvaluationModelOutputRecord] = []
    
    # even if fewshot count for this evaluation config is equal to the number of examples in the fewshot split,
    # this randomizes the order in which the chosen fewshot examples are used while still letting the output records
    # identify which examples were used and in what order
    chosen_fewshot_indices = np.random.choice(len(fewshot_examples), eval_config.fewshot_count, replace=False).tolist()
    chosen_fewshot_examples = [fewshot_examples[idx] for idx in chosen_fewshot_indices]
    
    system_prompt = create_sys_prompt_for_model_evaluation(eval_config, chosen_fewshot_examples, scenario_domains,
                                                           scenario_text_passage_descriptions, schemas)
    logger.debug(f"System prompt for model evaluation config {eval_config.label()}:\n{system_prompt}")
    logger.debug(f"chosen fewshot example indices: {chosen_fewshot_indices}")
    bundled_client = OpenAiClientBundle(eval_config.client, system_prompt, 8192, 0.0, eval_config.model_spec,
                                        is_response_forced_json=not eval_config.is_cot_enabled)
    for src_record_idx, src_record in enumerate(evaluation_src_set):
        scenario_id = src_record.scenario_id
        extracted_obj, extraction_analysis_output, _, num_retries_used = extract_obj_from_passage_with_retry(
            eval_config.provider, eval_config.model_spec, src_record.text_passage, scenario_domains[scenario_id],
            scenario_text_passage_descriptions[scenario_id], schemas[scenario_id],
            f"{src_record_idx}'th record in the {src_set_nm} set (scenario id={scenario_id}, domain={scenario_domains[scenario_id]}, name={src_record.scenario_name})",
            f"{src_set_nm}-{src_record_idx}-{eval_config.label()}", openai_client_bundle=bundled_client,
            is_cot_enabled=eval_config.is_cot_enabled
        )
        
        eval_model_outputs.append(EvaluationModelOutputRecord(
            scenario_id, src_record.scenario_name, src_set_nm == "validation", src_record_idx, chosen_fewshot_indices,
            extracted_obj, extraction_analysis_output, num_retries_used
        ))
        if (src_record_idx + 1) % 25 == 0:
            logger.info(
                f"Completed {src_record_idx + 1} records in the {src_set_nm} set for model evaluation config {eval_config.label()}")
    
    return eval_model_outputs


def main():
    openai_client = OpenAI(api_key=os.environ[openai_api_key_env])
    llama_provider_client = OpenAI(api_key=os.environ[deepinfra_api_key_env],
                                   base_url="https://api.deepinfra.com/v1/openai")
    
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)
    
    fewshot_examples = load_data_split(fewshot_examples_path, schemas)
    validation_set = load_data_split(validation_set_path, schemas)
    test_set = load_data_split(test_set_path, schemas)
    
    evaluation_models_output_path.mkdir(exist_ok=True)
    
    gpt_4o_model_spec = "gpt-4o-2024-11-20"
    gpt_4o_mini_model_spec = "gpt-4o-mini-2024-07-18"
    llama_3_3_70b_model_spec = "meta-llama/Llama-3.3-70B-Instruct"
    llama_3_1_405b_model_spec = "meta-llama/Meta-Llama-3.1-405B-Instruct"
    
    evaluation_configs: list[ModelEvaluationConfig] = \
        ([
             ModelEvaluationConfig(llama_provider_client, ModelProvider.DEEPINFRA, model_choice, fewshot_count,
                                   cot_choice)
             for fewshot_count in [0, 5, 10, 50] for model_choice in
             [llama_3_3_70b_model_spec, llama_3_1_405b_model_spec] for cot_choice in [False, True]
         ] + [
             ModelEvaluationConfig(openai_client, ModelProvider.OPENAI, model_choice, fewshot_count, cot_choice)
             for fewshot_count in [0, 5, 10, 50] for model_choice in [gpt_4o_mini_model_spec, gpt_4o_model_spec] for
             cot_choice in [False, True]
         ]
         )
    
    for eval_config in evaluation_configs:
        logger.info(f"starting evaluation for model config {eval_config.label()}")
        eval_outputs = generate_outputs_for_evaluation(
            eval_config, scenario_domains, scenario_text_passage_descriptions, schemas, fewshot_examples,
            test_set, "test")
            # validation_set, "validation")
        
        with open(eval_config.output_path(), "w") as output_file:
            json.dump(list(map(asdict, eval_outputs)), output_file, indent=2)


if __name__ == "__main__":
    main()
