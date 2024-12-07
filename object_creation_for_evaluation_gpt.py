import json
from openai import OpenAI
import os
import datetime
from logging_setup import create_logger
from data_loading import *

# Set up the logger
logger = create_logger(__name__)

path_to_one_models_texts = Path("text_passages/gemini")

scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(Path("json_schemas"))
text_passages = []



# Retrieve the API key from the environment variable
# api_key = os.getenv("OPENAI_API_KEY")
api_key = "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"

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

# # Helper function to list all files in a directory, optionally filtering by subfolder
# def list_files_in_subfolder(parent_dir, subfolder_name):
#     """List all files within a specific subfolder of a parent directory."""
#     subfolder_path = os.path.join(parent_dir, subfolder_name)
#     if not os.path.exists(subfolder_path):
#         logger.warning(f"Subfolder does not exist: {subfolder_path}")
#         return []
#     logger.info(f"Listing files in subfolder: {subfolder_path}")
#     return [os.path.join(subfolder_path, f) for f in os.listdir(subfolder_path) if os.path.isfile(os.path.join(subfolder_path, f))]

# # Function to process files for a specific folder (e.g., 'claude' or 'gemini')
# def process_subfolder(schema_dir, text_dir, base_output_dir, subfolder_name):
#     # Load all schema and text files from the subfolder
#     schema_files = list_files_in_subfolder(schema_dir, subfolder_name)
#     text_files = list_files_in_subfolder(text_dir, subfolder_name)

#     # Define the output directory for this subfolder
#     output_dir = os.path.join(base_output_dir, subfolder_name)
#     os.makedirs(output_dir, exist_ok=True)

#     for schema_file, text_file in zip(schema_files, text_files):
#         # Load schema and text
#         logger.info(f"Processing schema file: {schema_file} and text file: {text_file}")
#         schema = load_schema_from_file(schema_file)
#         text = load_text_from_file(text_file)

#         # Generate JSON object using GPT model
#         try:
#             gpt_output = call_gpt_model(schema, text)
#             output_file_name = os.path.basename(text_file).replace(".json", "_output.json")
#             output_file_path = os.path.join(output_dir, output_file_name)

#             # Save the result
#             with open(output_file_path, 'w') as output_file:
#                 json.dump(json.loads(gpt_output), output_file, indent=2)
#             logger.info(f"Output written to {output_file_path}")
#         except Exception as e:
#             logger.error(f"Failed to process files {schema_file} and {text_file}: {e}")

# # Load schema from a file
# def load_schema_from_file(file_path):
#     """Load JSON schema from a file."""
#     logger.info(f"Loading schema from file: {file_path}")
#     with open(file_path, 'r') as f:
#         return json.load(f)

# # Load text from a file
# def load_text_from_file(file_path):
#     """Load text from a file."""
#     logger.info(f"Loading text from file: {file_path}")
#     with open(file_path, 'r') as f:
#         return json.load(f)

# Call GPT model
def call_gpt_model(schema, text):
    formatted_schema = json.dumps(schema, indent=2)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  
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
    
for i in range(len(scenario_domains)):
    
    text_passages = load_text_passages_for_one_model_and_scenario(path_to_one_models_texts, i)
    
    for text_passage in text_passages:
        
        try:
            gpt_output = call_gpt_model(schemas[i], text_passage)
            output_file_name = f"{i}_{scenario_domains[i]}_gpt_gemini.json"
            output_file_path = os.path.join("outputs_gpt/zero_shot/gemini", output_file_name)

            # Load existing data from the file if it exists
            if os.path.exists(output_file_path):
                with open(output_file_path, 'r') as output_file:
                    existing_data = json.load(output_file)
            else:
                existing_data = []

            # Append the new object to the data
            existing_data.append(json.loads(gpt_output))

            # Save the updated data back to the file
            with open(output_file_path, 'w') as output_file:
                json.dump(existing_data, output_file, indent=2)
            
            logger.info(f"Output written to {output_file_path}")
        
        except Exception as e:
            logger.error(f"Failed to process files: {e}")



# Define folder paths
# current_dir = os.path.dirname(os.path.abspath(__file__))
# json_schemas_dir = os.path.join(current_dir, 'json_schemas')
# text_passage_dir = os.path.join(current_dir, 'text_passage')
# output_base_dir = os.path.join(current_dir, 'output')

# Create base output directory if it doesn't exist
# os.makedirs(output_base_dir, exist_ok=True)

# Process 'claude' and 'gemini' subfolders with separate output directories
# for subfolder in ['claude', 'gemini']:
#     process_subfolder(json_schemas_dir, text_passage_dir, output_base_dir, subfolder)
