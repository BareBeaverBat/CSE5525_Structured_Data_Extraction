import json
import os
import random
import re

# JSON objects are stored in these directories
json_obj_claude = 'json_objects/claude'
json_obj_gemini = 'json_objects/gemini'

# Text passages are stored in these directories
json_text_claude = 'text_passages/claude'
json_text_gemini = 'text_passages/gemini'

# Schema for the JSON objects
json_schema = 'json_schemas'

def load_json_objects_from_directory(directory_path):
    """Load all JSON objects from files within a directory."""
    json_objects = {"strata" : [], "strata_label" : []}


    file_list = sorted(os.listdir(directory_path))
    for filename in file_list:
        if filename.endswith('.json'):
            file_path = os.path.join(directory_path, filename)
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        json_objects["strata"].append(data)
                      
                        json_objects["strata_label"].append(filename.replace('__objs',""))
                    else:
                        print(f"Warning: JSON file '{filename}' does not contain a list at the root level.")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error: Could not process file '{file_path}': {e}")
    return json_objects

def load_json_schemas_from_directory(directory_path):
    """Load all JSON objects from files within a directory."""
    json_schemas = {}


    file_list = sorted(os.listdir(directory_path))
    for filename in file_list:
        if filename.endswith('.json'):
            file_path = os.path.join(directory_path, filename)
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    json_schemas[filename] = data
                    
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error: Could not process file '{file_path}': {e}")
    return json_schemas

def stratified_sampling(strata, sizes, all_labels):
    # Check if the total requested size exceeds available objects
    total_objects = sum(len(stratum) for stratum in strata)
    if sum(sizes.values()) > total_objects:
        raise ValueError("Not enough objects to sample from.")

    selections = {name: {'objects': [], 'indices': [], 'schema': []} for name in sizes}

    # For each stratum (JSON file), perform proportional sampling
    current_index = 0  # Track global index across strata
    schema_index = 0
    for stratum_index, stratum in enumerate(strata):
        stratum_size = len(stratum)
        remaining_sizes = {k: v for k, v in sizes.items()}
        
        stratum_indices = list(range(stratum_size))
        random.shuffle(stratum_indices)  # Shuffle to ensure random selection


        # Calculate proportional sizes for each category in this stratum
        for name in sizes:
            stratum_proportion = sizes[name] / total_objects
            num_samples = int(round(stratum_proportion * stratum_size))
            num_samples = min(num_samples, remaining_sizes[name])  # Don't exceed the needed samples

            if num_samples > 0:
                selected_indices = stratum_indices[:num_samples]
                selected_objects = [stratum[i] for i in selected_indices]

                selections[name]['objects'].extend(selected_objects)
                selections[name]['indices'].extend(current_index + i for i in selected_indices)
                selections[name]['schema'].extend(all_labels[schema_index] for _ in selected_objects)
                

                # Update remaining sizes and remove used indices
                remaining_sizes[name] -= num_samples
                stratum_indices = stratum_indices[num_samples:]

        current_index += stratum_size  # Update global index
        schema_index += 1

    return selections

def main():
    
    schemas = load_json_schemas_from_directory(json_schema)
    
    strata1 = load_json_objects_from_directory(json_obj_claude)['strata']
    strata2 = load_json_objects_from_directory(json_obj_gemini)['strata']

    all_strata = strata1 + strata2

    all_labels = load_json_objects_from_directory(json_obj_claude)['strata_label'] + load_json_objects_from_directory(json_obj_gemini)['strata_label']


    if sum(len(stratum) for stratum in all_strata) != 340:
        print(f"Expected 340 objects but found {sum(len(stratum) for stratum in all_strata)}. Please check the directories.")
        return

    sizes = {'fewshot': 50, 'validation': 160, 'test': 130}
    selections = stratified_sampling(all_strata, sizes, all_labels)

    os.makedirs('datasets', exist_ok=True)

    # Save the objects and their indices
    for name, selection in selections.items():
        file_path = f'datasets/{name}_objs.json'
        with open(file_path, 'w') as outfile:
            json.dump(selection['objects'], outfile, indent=2)
        print(f"{name.capitalize()} selection and indices saved to '{file_path}'.")

    

    text_strata1 = load_json_objects_from_directory(json_text_claude)['strata']
    text_strata2 = load_json_objects_from_directory(json_text_gemini)['strata']
    all_text_strata = text_strata1 + text_strata2

    all_text_objects = [obj for stratum in all_text_strata for obj in stratum]

    # Debugging: Ensure the length of all text matches the objects
    if len(all_text_objects) != sum(len(stratum) for stratum in all_strata):
        print(f"Mismatch! Text objects: {len(all_text_objects)}, Expected objects: {sum(len(stratum) for stratum in all_strata)}")
        return

    for name in sizes.keys():
        indices = selections[name]['indices']
        
        # Debugging: Check indices validity
        for idx in indices:
            if idx >= len(all_text_objects):
                print(f"Error: Invalid index {idx} for all_text_objects of length {len(all_text_objects)}")
                return

        selected_text_objects = [all_text_objects[i] for i in indices]

        output_file = f'datasets/{name}_text_passages.json'
        with open(output_file, 'w') as outfile:
            json.dump(selected_text_objects, outfile, indent=2)
        print(f"{name.capitalize()} text passages saved to '{output_file}'.")

    # Save the schema for each dataset
    for name in sizes.keys():
        schema_label = selections[name]['schema']
        schema_objects = [schemas[label] for label in schema_label]
        output_file = f'datasets/{name}_schema.json'
        with open(output_file, 'w') as outfile:
            json.dump(schema_objects, outfile, indent=2)
        print(f"{name.capitalize()} schema saved to '{output_file}'.")

if __name__ == "__main__":
    main()