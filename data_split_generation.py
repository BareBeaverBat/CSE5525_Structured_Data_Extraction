from data_loading import *
import random
import os
import json

path_of_one_models_texts_claude = Path("text_passages/claude")
path_of_one_models_texts_gemini = Path("text_passages/gemini")

path_of_one_models_objects_claude = Path("json_objects/claude")
path_of_one_models_objects_gemini = Path("json_objects/gemini")

# Load the data
scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(Path("json_schemas"))

text_passages_claude = []
text_passages_gemini = []

objects_claude = []
objects_gemini = []

scenario_id_claude = []
scenario_id_gemini = []

fewshot_ratio = 0.15
val_ratio = 0.75
test_ratio = 0.1

for i in range(len(scenario_domains)):
    text_passages_claude.append(load_text_passages_for_one_model_and_scenario(path_of_one_models_texts_claude, i))
    text_passages_gemini.append(load_text_passages_for_one_model_and_scenario(path_of_one_models_texts_gemini,i))

    objects_claude.append(load_objects_for_one_model_and_scenario(path_of_one_models_objects_claude, schemas[i], i))
    objects_gemini.append(load_objects_for_one_model_and_scenario(path_of_one_models_objects_gemini, schemas[i], i))

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
    dataset.append({"text_passage": flattened_text_passages_claude[i], "object": flattened_objects_claude[i], "scenario_id": flattened_scenario_id_claude[i], "was_claude_vs_gemini_generated": True})

for i in range(len(flattened_text_passages_gemini)):
    dataset.append({"text_passage": flattened_text_passages_gemini[i], "object": flattened_objects_gemini[i], "scenario_id": flattened_scenario_id_gemini[i], "was_claude_vs_gemini_generated": False})



def split_data(data, fewshot_ratio, val_ratio, test_ratio):
    random.shuffle(data)
    total_len = len(data)
    fewshot_len = int(total_len * fewshot_ratio)
    val_len = int(total_len * val_ratio)

    fewshot = data[:fewshot_len]
    val = data[fewshot_len : fewshot_len + val_len]
    test = data[fewshot_len + val_len :]

    return fewshot, val, test

# Split the data
fewshot,val,test = split_data(dataset, fewshot_ratio, val_ratio, test_ratio)

print(f"Number of fewshot samples: {len(fewshot)}")
print(f"Number of validation samples: {len(val)}")
print(f"Number of test samples: {len(test)}")

# Save the data
# Create directory if not available
if not os.path.exists("data"):
    os.makedirs("data")

# Save the data
json.dump(fewshot, open("data/fewshot.json", "w"), indent=2)
json.dump(val, open("data/val.json", "w"), indent=2)
json.dump(test, open("data/test.json", "w"), indent=2)


