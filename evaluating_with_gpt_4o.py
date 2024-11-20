import json
from openai import OpenAI
import os
import datetime
from logging_setup import create_logger

# Set up the logger
logger = create_logger(__name__)

# Retrieve the API key from the environment variable
api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    logger.error("API key for OpenAI is not set in environment variable 'OPENAI_API_KEY'.")
    raise ValueError("API key for OpenAI is not set in environment variable 'OPENAI_API_KEY'.")

# API setup for OpenAI using the environment variable
client = OpenAI(api_key=api_key)

# System instruction guiding structured data extraction
SYSTEM_INSTRUCTION = """
You are an expert in generating JSON objects. You receive a JSON schema and a text passage as inputs.
Respond with a JSON object only, formatted exactly according to the provided schema, without any additional text or comments.
"""

# Function to dynamically load the schema from the json_schemas folder
def load_schema_from_file(file_path):
    """Load JSON schema from a file using relative path."""
    logger.info(f"Loading schema from file: {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to read the text from the specified JSON file
def load_text_from_file(file_path):
    """Load all text entries from the JSON file."""
    logger.info(f"Loading text from file: {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to load the expected schema
def load_expected_schema(file_path):
    """Load all objects from the expected schema JSON file."""
    logger.info(f"Loading expected schema from file: {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)

# Get the current working directory (where the script is located)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Go up three directory levels to reach the "OSU" directory
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

# Construct the path to the schema, text, and expected schema files
schema_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'test_schema.json')
text_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'test_text_passages.json')
test_obj = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'test_objs.json')

# Log file paths for debugging
logger.info(f"Attempting to open schema file: {schema_file_path}")
logger.info(f"Attempting to open text file: {text_file_path}")
logger.info(f"Attempting to open expected schema file: {test_obj}")

# Load the schema, texts, and expected schemas
schema = load_schema_from_file(schema_file_path)
texts = load_text_from_file(text_file_path)
expected_schemas = load_expected_schema(test_obj)

# Function to call GPT model with system instruction only
def call_gpt_model(schema, text):
    formatted_schema = json.dumps(schema, indent=2)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  
            messages=[{
                "role": "system", 
                "content": SYSTEM_INSTRUCTION
            }, {
                "role": "user", 
                "content": f"Schema:\n{formatted_schema}\n\nText:\n{text}"
            }],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling GPT model: {e}")
        raise

def compare_values(expected, actual):
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.lower() == actual.lower()
    return expected == actual

def compare_lists(expected_list, actual_list, path):
    if len(expected_list) != len(actual_list):
        return 0.0, [f"Length mismatch for {path}: Expected {len(expected_list)}, got {len(actual_list)}"]
    
    correct_items = 0
    differences = []
    for i, (expected_item, actual_item) in enumerate(zip(expected_list, actual_list)):
        if isinstance(expected_item, dict) and isinstance(actual_item, dict):
            sub_diff, sub_accuracy, sub_total_accuracy = compare_dicts(expected_item, actual_item, f"{path}[{i}]")
            if sub_total_accuracy == 1.0:
                correct_items += 1
            else:
                differences.extend(sub_diff)
        elif not compare_values(expected_item, actual_item):
            differences.append(f"Mismatch in {path}[{i}]: Expected '{expected_item}', got '{actual_item}'")
        else:
            correct_items += 1
    
    accuracy = correct_items / len(expected_list)
    return accuracy, differences

def compare_dicts(expected, actual, path=""):
    differences = []
    accuracy_per_field = {}

    for key, expected_value in expected.items():
        current_path = f"{path}.{key}" if path else key
        actual_value = actual.get(key)

        if actual_value is None:
            differences.append(f"Missing key '{current_path}' in actual output")
            accuracy_per_field[current_path] = 0.0
            continue

        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                differences.append(f"Type mismatch for key '{current_path}': Expected dict, got {type(actual_value)}")
                accuracy_per_field[current_path] = 0.0
            else:
                sub_diff, sub_accuracy, sub_total_accuracy = compare_dicts(expected_value, actual_value, current_path)
                differences.extend(sub_diff)
                accuracy_per_field.update(sub_accuracy)
        elif isinstance(expected_value, list):
            if not isinstance(actual_value, list):
                differences.append(f"Type mismatch for key '{current_path}': Expected list, got {type(actual_value)}")
                accuracy_per_field[current_path] = 0.0
            else:
                list_accuracy, list_differences = compare_lists(expected_value, actual_value, current_path)
                accuracy_per_field[current_path] = list_accuracy
                if list_accuracy < 1.0:
                    differences.extend(list_differences)
        else:
            if compare_values(expected_value, actual_value):
                accuracy_per_field[current_path] = 1.0
            else:
                differences.append(f"Value mismatch for key '{current_path}': Expected '{expected_value}', got '{actual_value}'")
                accuracy_per_field[current_path] = 0.0

    total_accuracy = sum(accuracy_per_field.values()) / len(accuracy_per_field) if accuracy_per_field else 0.0
    return differences, accuracy_per_field, total_accuracy

# Create a timestamp for the output file
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
output_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction', f'test_results_{timestamp}.txt')

# Run the tests and save results to file
all_test_accuracies = []
with open(output_file_path, 'w') as output_file:
    for i, (text, expected_schema) in enumerate(zip(texts, expected_schemas), 1):
        logger.info(f"\nRunning test {i}:")
        try:
            gpt_output = call_gpt_model(schema, text)

            gpt_json = json.loads(gpt_output)
            
            differences, accuracy_per_field, total_accuracy = compare_dicts(expected_schema, gpt_json)
            all_test_accuracies.append(total_accuracy)
            is_gpt_correct = len(differences) == 0

            # Write results to file
            output_file.write(f"Test {i} Results:\n")
            output_file.write("Differences found:\n")
            for diff in differences:
                output_file.write(f"- {diff}\n")

            # Write field accuracies
            output_file.write("\nField accuracy breakdown:\n")
            for field, accuracy in accuracy_per_field.items():
                output_file.write(f"  {field}: {accuracy * 100:.2f}%\n")
            
            output_file.write(f"\nTotal accuracy for this test: {total_accuracy * 100:.2f}%\n")
            output_file.write("\n")

            # Print results to console
            logger.info(f"Test {i} Results:")
            logger.info(f"Is GPT Output Correct: {is_gpt_correct}")
            logger.info(f"Differences:")
            for diff in differences:
                logger.info(f"- {diff}")
            
            logger.info(f"\nField Accuracy Breakdown:")
            for field, accuracy in accuracy_per_field.items():
                logger.info(f"  {field}: {accuracy * 100:.2f}%")

            logger.info(f"Total Accuracy: {total_accuracy * 100:.2f}%")

        except Exception as e:
            logger.error(f"Error running test {i}: {e}")
            output_file.write(f"Error running test {i}: {e}\n")

# Log the overall accuracy
average_accuracy = sum(all_test_accuracies) / len(all_test_accuracies)
logger.info(f"\nOverall Accuracy: {average_accuracy * 100:.2f}%")
