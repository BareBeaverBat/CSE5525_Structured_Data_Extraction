import os
import json
import glob
from openai import OpenAI
from logging_setup import create_logger

# this is the code that will be used to generate the objects for evaluation using GPT-4o-mini model in zero-shot setting

# Initialize logger
logger = create_logger(__name__)

# Retrieve the OpenAI API key
api_key = os.getenv("OPENAI_API_KEY") or "api_key"
if not api_key:
    logger.error("OpenAI API key is missing.")
    raise ValueError("API key is required for OpenAI interaction.")

# OpenAI client setup
client = OpenAI(api_key=api_key)

# Directories and file paths
SCHEMA_DIR = "json_schemas"
OUTPUT_DIR = "gpt_outputs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "output_gpt_zero_shot.json")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# System instruction for OpenAI
SYSTEM_INSTRUCTION = """
You are an expert in generating JSON objects. You receive a JSON schema and a text passage as inputs.
Respond with a JSON object only, formatted exactly according to the provided schema, without any additional text or comments.
"""

# Function to load data from specified directory
def load_data():
    data_files = {
        "few_shot": "split_data/fewshot_examples.json",
        "validation": "split_data/validation_set.json",
        "test": "split_data/test_set.json",
    }

    datasets = {}
    
    for key, file_path in data_files.items():
        if not os.path.exists(file_path):
            logger.error(f"Missing required file: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, "r") as file:
                datasets[key] = json.load(file)
            logger.info(f"Successfully loaded {key} dataset from {file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON file {file_path}: {e}")
            raise ValueError(f"Invalid JSON in file: {file_path}")
        except Exception as e:
            logger.error(f"Unexpected error loading file {file_path}: {e}")
            raise

    return datasets["few_shot"], datasets["validation"], datasets["test"]

# Function to initialize or validate the output JSON file
def initialize_output_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("[\n")  # Start a JSON array
        logger.info(f"Created new output file: {file_path}")
    else:
        # Ensure the file ends in a valid JSON array format
        with open(file_path, "rb+") as file:
            file.seek(-1, os.SEEK_END)
            last_char = file.read(1)
            if last_char == b"]":
                file.seek(-1, os.SEEK_END)
                file.truncate()  # Remove the closing bracket
                file.write(b",")  # Prepare for new entries
            elif last_char != b"[":
                raise ValueError(f"The file {file_path} is not in a valid JSON array format.")

# Function to find the correct schema file
def find_schema_file(scenario_id, schema_dir):
    matching_files = glob.glob(os.path.join(schema_dir, f"{scenario_id}_*.json"))
    matching_files = [file for file in matching_files if os.path.basename(file).startswith(f"{scenario_id}_")]
    if not matching_files:
        logger.error(f"No schema file found for scenario_id: {scenario_id}")
        return None
    return matching_files[0]

# Function to call the GPT model
def call_gpt_model(schema, text):
    formatted_schema = json.dumps(schema, indent=2)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": f"Schema:\n{formatted_schema}\n\nText:\n{text}"}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Failed to call GPT model: {e}")
        return None

# Function to process a single dataset entry
def process_entry(entry, schema_dir, output_file_path):
    scenario_id = entry["scenario_id"]
    text_passage = entry["text_passage"]

    # Find and load the schema
    schema_path = find_schema_file(scenario_id, schema_dir)
    if not schema_path:
        return

    try:
        with open(schema_path, "r") as file:
            schema = json.load(file)
    except Exception as e:
        logger.error(f"Failed to load schema file {schema_path}: {e}")
        return

    # Call the GPT model and write the output
    try:
        response = call_gpt_model(schema, text_passage)
        if response:
            output_data = {
                "scenario_id": scenario_id,
                "text_passage": text_passage,
                "object": json.loads(response)
            }
            with open(output_file_path, "a") as output_file:
                json.dump(output_data, output_file, indent=2)
                output_file.write(",\n")
            logger.info(f"Processed entry for scenario_id: {scenario_id}")
    except Exception as e:
        logger.error(f"Error processing entry for scenario_id {scenario_id}: {e}")

# Function to finalize the output JSON file
def finalize_output_file(file_path):
    with open(file_path, "rb+") as file:
        file.seek(-2, os.SEEK_END)  # Remove the trailing comma and newline
        file.truncate()
        file.write(b"\n]")  # Close the JSON array
    logger.info(f"Finalized output file: {file_path}")

# Main function to process the dataset
def main():
    try:
        # Load datasets
        _, dataset_val, _ = load_data()

        # Initialize output file
        initialize_output_file(OUTPUT_FILE)

        # Process each validation entry
        for entry in dataset_val:
            process_entry(entry, SCHEMA_DIR, OUTPUT_FILE)

        # Finalize the output file
        finalize_output_file(OUTPUT_FILE)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()
