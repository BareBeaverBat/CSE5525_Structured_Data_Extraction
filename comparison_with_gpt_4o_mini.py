import json
from openai import OpenAI
import os

# API setup for OpenAI (API key is required)
client = OpenAI(api_key="")  # Replace with your actual API key

# System instruction guiding structured data extraction
SYSTEM_INSTRUCTION = """
You are an expert in generating JSON objects. You receive a JSON schema and respond with a list of 1 JSON objects based on the JSON schema. Each object should include between 2 and 20 facts with diverse, realistic content and vary in which optional fields are filled. Ensure that optional fields are selectively included or omitted to create unique, authentic records, avoiding generic labels like 'Product 1', '[Company Name]', or 'email1@example.com.' Use natural, dynamic values without duplication. Output only the JSON objects with no explanations, placeholders, or additional text."
"""

# Function to dynamically load the schema from the json_schemas folder
def load_schema_from_file(file_path):
    """Load JSON schema from a file using relative path."""
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to read the text from the specified JSON file
def load_text_from_file(file_path):
    """Load the first text entry from the JSON file."""
    with open(file_path, 'r') as f:
        texts = json.load(f)
    return texts[0]  # Assuming you want the first text

# Get the current working directory (where the script is located)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Go up three directory levels to reach the "OSU" directory
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

# Construct the path to the schema and text files
schema_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', 'json_schemas', '0_healthcare__patient_visit_notes.json')
text_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language', 'text_passages', 'claude', '0_healthcare__patient_visit_notes__texts.json')

# Print the paths for debugging
print(f"Attempting to open schema file: {schema_file_path}")
print(f"Attempting to open text file: {text_file_path}")

# Load the schema from the file
schema = load_schema_from_file(schema_file_path)

# Load the first text from the JSON file
text = load_text_from_file(text_file_path)

# Sample data to test the models: list of dicts with 'schema' and 'text'
data_pairs = [
    {
        "schema": schema,  # Use the loaded schema here
        "text": text  # Use the first text from the loaded file
    },
]

# Expected schema for validation
expected_schema = [
    {
        "symptoms": [
            {"name": "headache", "duration_days": 3, "severity": 6, "frequency": "intermittent"},
            {"name": "fatigue", "duration_days": 7, "severity": 4, "frequency": "constant"}
        ],
        "medications": [
            {"name": "ibuprofen", "dosage": "200mg", "frequency": "as needed"}
        ],
        "allergies": ["pollen", "dust mites"]
    }
]

# Function to call GPT model with system instruction only
def call_gpt_model(schema, text):
    # Format the schema as a JSON string
    formatted_schema = json.dumps(schema, indent=2)
    
    response = client.chat.completions.create(
        model="gpt-4",  # or "gpt-4" if you have access
        messages=[{
            "role": "system", "content": SYSTEM_INSTRUCTION
        },
        {
            "role": "user", "content": f"Schema:\n{formatted_schema}\n\nText:\n{text}"
        }],
        temperature=0.0
    )
    # Extract the response text from the model
    gpt_output = response.choices[0].message.content
    return gpt_output

# Function to compare two dictionaries in a case-insensitive manner
def compare_dicts(expected, actual):
    differences = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, list):
            # If the value is a list, compare each element in a case-insensitive manner
            if len(expected_value) != len(actual_value):
                differences.append(f"Length mismatch for key '{key}'")
            else:
                for e_item, a_item in zip(expected_value, actual_value):
                    if isinstance(e_item, dict) and isinstance(a_item, dict):
                        differences.extend(compare_dicts(e_item, a_item))  # Recursively compare nested dicts
                    elif isinstance(e_item, str) and isinstance(a_item, str):
                        if e_item.lower() != a_item.lower():
                            differences.append(f"Value mismatch for key '{key}': Expected '{e_item}', got '{a_item}'")
                    else:
                        differences.append(f"Type mismatch for key '{key}': Expected '{type(e_item)}', got '{type(a_item)}'")
        else:
            # Compare individual values
            if isinstance(expected_value, str) and isinstance(actual_value, str):
                if expected_value.lower() != actual_value.lower():
                    differences.append(f"Value mismatch for key '{key}': Expected '{expected_value}', got '{actual_value}'")
            elif expected_value != actual_value:
                differences.append(f"Value mismatch for key '{key}': Expected '{expected_value}', got '{actual_value}'")
    
    return differences

# Testing function to extract structured data and compare with the expected schema
def test_data_extraction(data_pairs):
    results = []
    for idx, pair in enumerate(data_pairs):
        print(f"\nRunning test {idx+1}...")
        
        # Call GPT model with the schema and text
        gpt_output = call_gpt_model(pair["schema"], pair["text"])
        print("GPT Model Output:", gpt_output)
        
        # Validate if the extracted JSON aligns with the original schema
        try:
            gpt_json = json.loads(gpt_output)  # Parse the output to a Python object
            
            # Check if the output is a list and validate each element against the expected schema
            if isinstance(gpt_json, list):
                is_gpt_correct = True
                differences = []

                # Compare each item in the list against the expected schema
                for expected_item, actual_item in zip(expected_schema, gpt_json):
                    differences.extend(compare_dicts(expected_item, actual_item))
                
                if differences:
                    is_gpt_correct = False
            else:
                # If it's a single object, check the object structure directly
                differences = compare_dicts(expected_schema[0], gpt_json) if not gpt_json == expected_schema else []
                is_gpt_correct = len(differences) == 0

        except json.JSONDecodeError:
            is_gpt_correct = False  # Parsing error indicates an issue with the output format
            differences = [{"error": "JSON Decode Error"}]

        results.append({
            "test_number": idx + 1,
            "original_schema": pair["schema"],
            "original_text": pair["text"],
            "gpt_model_output": gpt_output,
            "gpt_model_correct": is_gpt_correct,
            "differences": differences
        })

    return results


# Run the tests
results = test_data_extraction(data_pairs)

# Print and log results
for result in results:
    print(f"\nTest {result['test_number']} Results:")
    print("Original Schema:", result['original_schema'])
    print("Original Text:", result['original_text'])
    print("GPT Model Output:", result['gpt_model_output'])
    print("Is GPT Output Correct:", result['gpt_model_correct'])
    print("Differences:", result['differences'])
