from dataclasses import dataclass
from pathlib import Path
from typing import Any, List


@dataclass
class DataSplitRecord:
    text_passage: str
    object: dict[str, Any]
    scenario_id: int
    scenario_name: str
    was_claude_vs_gemini_generated: bool
    
    def __post_init__(self):
        assert isinstance(self.text_passage, str)
        assert isinstance(self.object, dict)
        assert isinstance(self.scenario_id, int)
        assert isinstance(self.scenario_name, str)
        assert isinstance(self.was_claude_vs_gemini_generated, bool)


@dataclass
class EvaluationModelOutputRecord:
    scenario_id: int
    scenario_name: str
    is_validation_vs_test: bool # True if the source record is from the validation set, False if from the test set
    src_record_idx_in_split: int # i.e. the index of the source record in the validation_set.json or test_set.json split file
    fewshot_example_idxs: List[int]
    model_output_object: dict[str, Any]
    # in cases where automated-validation-and-retry logic was enabled for querying the model being evaluated
    #  or where the model's output was not in the expected format, this may contain not simply a single round of the
    #  model's output text but rather one or more rounds of the model's output text followed by a feedback message from
    #  the automatic validation logic
    model_output_text: str
    num_retries_used: int


scenario_details_regex = r"^(\d+)_([a-zA-Z0-9]+(_[a-zA-Z0-9]+)*)__(\w+).json"
scenario_idx_regex = r"^(\d+)_"

claude_folder_nm = "claude"
gemini_folder_nm = "gemini"
schemas_path = Path("json_schemas")
objects_path = Path("json_objects")
claude_objs_path = objects_path / claude_folder_nm
gemini_objs_path = objects_path / gemini_folder_nm
texts_path = Path("text_passages")
claude_texts_path = texts_path / claude_folder_nm
gemini_texts_path = texts_path / gemini_folder_nm

split_data_folder_path = Path("split_data")
fewshot_examples_path = split_data_folder_path / "fewshot_examples.json"
validation_set_path = split_data_folder_path / "validation_set.json"
test_set_path = split_data_folder_path / "test_set.json"

evaluation_models_output_path = Path("evaluation_models_outputs")
