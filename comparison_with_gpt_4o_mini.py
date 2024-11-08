import json
from openai import OpenAI
import os
import datetime

# API setup for OpenAI (API key is required)
client = OpenAI(api_key="")  # Replace with your actual API key

# System instruction guiding structured data extraction
SYSTEM_INSTRUCTION = """
You are an expert in generating JSON objects. You receive a JSON schema and a text passage as inputs.
Respond with a JSON object only, formatted exactly according to the provided schema, without any additional text or comments.
"""

# Function to dynamically load the schema from the json_schemas folder
def load_schema_from_file(file_path):
    """Load JSON schema from a file using relative path."""
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to read the text from the specified JSON file
def load_text_from_file(file_path):
    """Load all text entries from the JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to load the expected schema
def load_expected_schema(file_path):
    """Load all objects from the expected schema JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

# Get the current working directory (where the script is located)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Go up three directory levels to reach the "OSU" directory
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

# Construct the path to the schema, text, and expected schema files
schema_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', 'json_schemas', '0_healthcare__patient_visit_notes.json')
text_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', 'text_passages', 'claude', '0_healthcare__patient_visit_notes__texts.json')
expected_schema_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', 'json_objects', 'claude', '0_healthcare__patient_visit_notes__objs.json')

# Print the paths for debugging
print(f"Attempting to open schema file: {schema_file_path}")
print(f"Attempting to open text file: {text_file_path}")
print(f"Attempting to open expected schema file: {expected_schema_file_path}")

# Load the schema, texts, and expected schemas
schema = load_schema_from_file(schema_file_path)
texts = load_text_from_file(text_file_path)
expected_schemas = load_expected_schema(expected_schema_file_path)

# Function to call GPT model with system instruction only
def call_gpt_model(schema, text):
    formatted_schema = json.dumps(schema, indent=2)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4" if you have access
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": f"Schema:\n{formatted_schema}\n\nText:\n{text}"}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content

# Function to compare two dictionaries in a case-insensitive manner
def compare_dicts(expected, actual):
    differences = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value is None:
            differences.append(f"Missing key '{key}' in actual output")
            continue
        if isinstance(expected_value, list):
            if not isinstance(actual_value, list):
                differences.append(f"Type mismatch for key '{key}': Expected list, got {type(actual_value)}")
            elif len(expected_value) != len(actual_value):
                differences.append(f"Length mismatch for key '{key}'")
            else:
                for e_item, a_item in zip(expected_value, actual_value):
                    if isinstance(e_item, dict) and isinstance(a_item, dict):
                        differences.extend(compare_dicts(e_item, a_item))
                    elif isinstance(e_item, str) and isinstance(a_item, str):
                        if e_item.lower() != a_item.lower():
                            differences.append(f"Value mismatch for key '{key}': Expected '{e_item}', got '{a_item}'")
                    else:
                        differences.append(f"Type mismatch for key '{key}': Expected '{type(e_item)}', got '{type(a_item)}'")
        else:
            if isinstance(expected_value, str) and isinstance(actual_value, str):
                if expected_value.lower() != actual_value.lower():
                    differences.append(f"Value mismatch for key '{key}': Expected '{expected_value}', got '{actual_value}'")
            elif expected_value != actual_value:
                differences.append(f"Value mismatch for key '{key}': Expected '{expected_value}', got '{actual_value}'")
    
    return differences

# Create a timestamp for the output file
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
output_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', f'test_results_{timestamp}.txt')

# Run the tests and save results to file
with open(output_file_path, 'w') as output_file:
    for i, (text, expected_schema) in enumerate(zip(texts, expected_schemas), 1):
        print(f"\nRunning test {i}:")
        gpt_output = call_gpt_model(schema, text)

        try:
            gpt_json = json.loads(gpt_output)
            differences = compare_dicts(expected_schema, gpt_json)
            is_gpt_correct = len(differences) == 0
        except json.JSONDecodeError:
            is_gpt_correct = False
            differences = ["JSON Decode Error"]

        # Write results to file
        output_file.write(f"Test {i} Results:\n")
        if is_gpt_correct:
            output_file.write("No differences found.\n")
        else:
            output_file.write("Differences found:\n")
            for diff in differences:
                output_file.write(f"- {diff}\n")
        output_file.write("\n")

        # Print results to console
        print(f"Test {i} Results:")
        print("Is GPT Output Correct:", is_gpt_correct)
        if not is_gpt_correct:
            print("Differences:", differences)
        print()

print(f"Results have been saved to: {output_file_path}")