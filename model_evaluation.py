import json
import re
from dataclasses import dataclass, asdict
from statistics import mean
from typing import Optional, Any

import numpy as np

from data_processing.data_loading import load_scenarios, load_data_split, load_evaluation_model_outputs
from data_processing.data_mngmt_defs import schemas_path, fewshot_examples_path, validation_set_path, test_set_path, \
    EvaluationModelOutputRecord, evaluation_models_output_path, evaluation_config_regex, evaluation_reports_path, \
    DataSplitRecord
from data_processing.json_obj_comparison import evaluate_extraction
from utils_and_defs.logging_setup import create_logger

logger = create_logger(__name__)


@dataclass
class OutputObjectGrading:
    text_passage: str
    expected_object: dict[str, Any]
    output_record: EvaluationModelOutputRecord
    
    overall_extraction_quality: float
    correct_fact_inclusion_rate: float
    hallucinated_info_count: int
    differences: list[str]
    
    def to_dict(self):
        return {
            "text_passage": self.text_passage,
            "expected_object": self.expected_object,
            "output_record": asdict(self.output_record),
            "overall_extraction_quality": self.overall_extraction_quality,
            "correct_fact_inclusion_rate": self.correct_fact_inclusion_rate,
            "hallucinated_info_count": self.hallucinated_info_count,
            "differences": self.differences
        }


@dataclass
class OutputsGroupingAggregateGrade:
    avg_extraction_quality: float
    avg_correct_fact_inclusion_rate: float
    avg_hallucinated_info_count: float
    avg_differences_count: float
    avg_num_retries_used: float
    fraction_of_records_where_retries_used: float
    num_outputs_in_grouping: int


class OutputsGroupingMetricsAggregator:
    def __init__(self):
        self.extraction_qualities: list[float] = []
        self.correct_fact_inclusion_rates: list[float] = []
        self.hallucinated_info_counts: list[int] = []
        self.differences_counts: list[int] = []
        self.num_retries_used_for_output_record: list[int] = []
    
    def add_output_record(self, output_grading: OutputObjectGrading):
        self.extraction_qualities.append(output_grading.overall_extraction_quality)
        self.correct_fact_inclusion_rates.append(output_grading.correct_fact_inclusion_rate)
        self.hallucinated_info_counts.append(output_grading.hallucinated_info_count)
        self.differences_counts.append(len(output_grading.differences))
        self.num_retries_used_for_output_record.append(output_grading.output_record.num_retries_used)
    
    def finalize(self) -> OutputsGroupingAggregateGrade:
        num_records = len(self.extraction_qualities)
        assert (num_records == len(self.correct_fact_inclusion_rates) == len(self.hallucinated_info_counts)
                == len(self.differences_counts) == len(self.num_retries_used_for_output_record))
        return OutputsGroupingAggregateGrade(
            mean(self.extraction_qualities), mean(self.correct_fact_inclusion_rates),
            mean(self.hallucinated_info_counts), mean(self.differences_counts),
            mean(self.num_retries_used_for_output_record),
            sum([1.0 for retries_used in self.num_retries_used_for_output_record if retries_used > 0]) / num_records,
            num_records
        ) if num_records else OutputsGroupingAggregateGrade(np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 0)


@dataclass
class ModelEvaluationConfigAssessment:
    model_spec: str
    fewshot_count: int
    is_cot_enabled: bool
    eval_model_outputs_gradings: list[OutputObjectGrading]
    overall_metrics: OutputsGroupingAggregateGrade
    claude_generated_data_metrics: OutputsGroupingAggregateGrade
    gemini_generated_data_metrics: OutputsGroupingAggregateGrade
    scenario_metrics: list[OutputsGroupingAggregateGrade]
    
    def to_saveable_report(self, scenario_domains: list[str], scenario_text_passage_descriptions: list[str]
                           ) -> dict[str, Any]:
        assert len(scenario_domains) == len(scenario_text_passage_descriptions) == len(self.scenario_metrics)
        correct_outputs_gradings = [grading for grading in self.eval_model_outputs_gradings
                                    if grading.overall_extraction_quality == 1.0]
        incorrect_outputs_gradings = [grading for grading in self.eval_model_outputs_gradings
                                        if grading.overall_extraction_quality < 1.0]
        gradings_dicts_for_outputs_correct_after_retries = [asdict(grading) for grading in correct_outputs_gradings
                                                     if grading.output_record.num_retries_used > 0]
        gradings_dicts_for_outputs_correct_without_retries = [asdict(grading) for grading in correct_outputs_gradings
                                                         if grading.output_record.num_retries_used == 0]
        gradings_dicts_for_outputs_incorrect_despite_retries = \
            [asdict(grading) for grading in incorrect_outputs_gradings if grading.output_record.num_retries_used > 0]
        gradings_dicts_for_outputs_incorrect_without_retries = \
            [asdict(grading) for grading in incorrect_outputs_gradings if grading.output_record.num_retries_used == 0]
        
        return {
            "model_spec": self.model_spec,
            "fewshot_count": self.fewshot_count,
            "is_cot_enabled": self.is_cot_enabled,
            "overall_metrics": asdict(self.overall_metrics),
            "claude_generated_data_metrics": asdict(self.claude_generated_data_metrics),
            "gemini_generated_data_metrics": asdict(self.gemini_generated_data_metrics),
            "scenario_metrics": [{
                "scenario_id": scenario_id,
                "scenario_domain": scenario_domains[scenario_id],
                "scenario_text_passage_description": scenario_text_passage_descriptions[scenario_id],
                **asdict(scenario_metrics)
            } for scenario_id, scenario_metrics in enumerate(self.scenario_metrics)],
            "num_outputs_incorrect_despite_retries": len(gradings_dicts_for_outputs_incorrect_despite_retries),
            "num_outputs_incorrect_without_retries": len(gradings_dicts_for_outputs_incorrect_without_retries),
            "num_outputs_correct_after_retries": len(gradings_dicts_for_outputs_correct_after_retries),
            "num_outputs_correct_without_retries": len(gradings_dicts_for_outputs_correct_without_retries),
            "gradings_of_outputs_incorrect_despite_retries": gradings_dicts_for_outputs_incorrect_despite_retries,
            "gradings_of_outputs_incorrect_without_retries": gradings_dicts_for_outputs_incorrect_without_retries,
            "gradings_of_outputs_correct_after_retries": gradings_dicts_for_outputs_correct_after_retries,
            "gradings_of_outputs_correct_without_retries": gradings_dicts_for_outputs_correct_without_retries
        }
    
    def label(self) -> str:
        return f"Model__{self.model_spec}__Fewshot__{self.fewshot_count}__CoT__{self.is_cot_enabled}"

def main():
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)
    
    fewshot_examples = load_data_split(fewshot_examples_path, schemas)
    validation_set = load_data_split(validation_set_path, schemas)
    test_set = load_data_split(test_set_path, schemas)
    
    evaluation_configs_assessments: list[ModelEvaluationConfigAssessment] = []
    
    is_validation_vs_test: Optional[bool] = None
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
        logger.info(f"Loaded {len(eval_config_model_outputs)} evaluation records from path {eval_config_outputs_path} for model {eval_config_model_spec} with {eval_config_fewshot_count} fewshot examples and CoT {'enabled' if eval_config_cot_enabled else 'disabled'}")
        assert len(eval_config_model_outputs) > 0
        if is_validation_vs_test is None:
            is_validation_vs_test = eval_config_model_outputs[0].is_validation_vs_test
        assert all(model_output.is_validation_vs_test == is_validation_vs_test for model_output in eval_config_model_outputs)
        src_evaluation_set = validation_set if is_validation_vs_test else test_set
        assert len(eval_config_model_outputs) == len(src_evaluation_set)
        
        assessment = assess_model_eval_config_outputs(eval_config_cot_enabled, eval_config_fewshot_count,
                                                      eval_config_model_outputs, eval_config_model_spec, schemas,
                                                      src_evaluation_set)
        evaluation_configs_assessments.append(assessment)
    
    # model_specs_to_judge = set([eval_config_outputs.model_spec for eval_config_outputs in evaluation_configs_outputs])
    
    evaluation_reports_path.mkdir(exist_ok=True)
    
    for eval_config_assessment in evaluation_configs_assessments:
        with open(evaluation_reports_path / f"{eval_config_assessment.label()}.json", "w") as report_file:
            json.dump(eval_config_assessment.to_saveable_report(scenario_domains, scenario_text_passage_descriptions),
                      report_file, indent=2)


def assess_model_eval_config_outputs(
        eval_config_cot_enabled: bool, eval_config_fewshot_count: int,
        eval_config_model_outputs: list[EvaluationModelOutputRecord], eval_config_model_spec: str,
        scenarios_schemas: list[dict[str, Any]], src_evaluation_set: list[DataSplitRecord]
) -> ModelEvaluationConfigAssessment:
    overall_metrics_aggregator = OutputsGroupingMetricsAggregator()
    scenario_metrics_aggregators = [OutputsGroupingMetricsAggregator() for _ in scenarios_schemas]
    claude_generated_data_metrics_aggregator = OutputsGroupingMetricsAggregator()
    gemini_generated_data_metrics_aggregator = OutputsGroupingMetricsAggregator()
    output_object_gradings: list[OutputObjectGrading] = []
    for model_output in eval_config_model_outputs:
        src_record = src_evaluation_set[model_output.src_record_idx_in_split]
        overall_quality, inclusion_rate, hallucinations, differences = \
            evaluate_extraction(src_record.object, model_output.model_output_object)
        grading = OutputObjectGrading(src_record.text_passage, src_record.object, model_output, overall_quality,
                                      inclusion_rate, hallucinations, differences)
        overall_metrics_aggregator.add_output_record(grading)
        scenario_metrics_aggregators[src_record.scenario_id].add_output_record(grading)
        if src_record.was_claude_vs_gemini_generated:
            claude_generated_data_metrics_aggregator.add_output_record(grading)
        else:
            gemini_generated_data_metrics_aggregator.add_output_record(grading)
        
        output_object_gradings.append(grading)
    assessment = ModelEvaluationConfigAssessment(
        eval_config_model_spec, eval_config_fewshot_count, eval_config_cot_enabled, output_object_gradings,
        overall_metrics_aggregator.finalize(), claude_generated_data_metrics_aggregator.finalize(),
        gemini_generated_data_metrics_aggregator.finalize(),
        [scenario_metrics_aggregator.finalize() for scenario_metrics_aggregator in scenario_metrics_aggregators]
    )
    return assessment


if __name__ == "__main__":
    main()
