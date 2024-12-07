from constants import claude_texts_path, gemini_texts_path, claude_objs_path, gemini_objs_path, schemas_path, \
    split_data_folder_path, fewshot_examples_path, validation_set_path, test_set_path

import random
import json

from data_loading import load_scenarios, load_text_passages_for_one_model_and_scenario, \
    load_objects_for_one_model_and_scenario
from logging_setup import create_logger

logger = create_logger(__name__)

# Load the data
scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)

text_passages_claude = []
text_passages_gemini = []

objects_claude = []
objects_gemini = []

scenario_id_claude = []
scenario_id_gemini = []

fewshot_population_size = 50
val_ratio = 0.6
test_ratio = 1-val_ratio

for i in range(len(scenario_domains)):
    text_passages_claude.append(load_text_passages_for_one_model_and_scenario(claude_texts_path, i))
    text_passages_gemini.append(load_text_passages_for_one_model_and_scenario(gemini_texts_path, i))
    
    objects_claude.append(load_objects_for_one_model_and_scenario(claude_objs_path, schemas[i], i))
    objects_gemini.append(load_objects_for_one_model_and_scenario(gemini_objs_path, schemas[i], i))

    scenario_id_claude.append([f"{i}_{scenario_domains[i]}__{scenario_text_passage_descriptions[i]}"]*len(text_passages_claude[i]))
   
    scenario_id_gemini.append([f"{i}_{scenario_domains[i]}__{scenario_text_passage_descriptions[i]}"]*len(text_passages_gemini[i]))


flattened_text_passages_claude = [item for sublist in text_passages_claude for item in sublist]
flattened_text_passages_gemini = [item for sublist in text_passages_gemini for item in sublist]

flattened_objects_claude = [item for sublist in objects_claude for item in sublist]
flattened_objects_gemini = [item for sublist in objects_gemini for item in sublist]

flattened_scenario_id_claude = [item for sublist in scenario_id_claude for item in sublist]
flattened_scenario_id_gemini = [item for sublist in scenario_id_gemini for item in sublist]


dataset = []

for i in range(len(flattened_text_passages_claude)):
    # Add the claude vs gemini generated flag(True for claude, False for gemini)
    
    dataset.append({"text_passage": flattened_text_passages_claude[i], "object": flattened_objects_claude[i], "scenario_id": flattened_scenario_id_claude[i], "was_claude_vs_gemini_generated": True})

for i in range(len(flattened_text_passages_gemini)):
    dataset.append({"text_passage": flattened_text_passages_gemini[i], "object": flattened_objects_gemini[i], "scenario_id": flattened_scenario_id_gemini[i], "was_claude_vs_gemini_generated": False})



def split_data(data, fewshot_count, val_fraction):
    random.shuffle(data)
    total_len = len(data)
    len_after_fewshot_reserved = total_len - fewshot_count
    val_len = int(len_after_fewshot_reserved * val_fraction)

    fewshot = data[:fewshot_count]
    val = data[fewshot_count : fewshot_count + val_len]
    test = data[fewshot_count + val_len :]

    return fewshot, val, test

# Split the data
fewshot,val,test = split_data(dataset, fewshot_population_size, val_ratio)

logger.info(f"Number of fewshot samples: {len(fewshot)}")
logger.info(f"Number of validation samples: {len(val)}")
logger.info(f"Number of test samples: {len(test)}")

# Save the data
# Create directory if not available
if not split_data_folder_path.exists():
    split_data_folder_path.mkdir(exist_ok=True)

# Save the data
with open(fewshot_examples_path, "w") as f:
    json.dump(fewshot, f, indent=2)
with open(validation_set_path, "w") as f:
    json.dump(val, f, indent=2)
with open(test_set_path, "w") as f:
    json.dump(test, f, indent=2)


