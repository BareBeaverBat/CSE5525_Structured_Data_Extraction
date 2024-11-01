import google.generativeai as genai
import os
import json
import time

BATCH_SIZE = 20 # Number of JSON objects to generate per batch (avoid exceeding output length limit)
BATCHES = 5
TOTAL_OBJECTS = BATCH_SIZE * BATCHES

# Configure model
API_KEY = "" # Add your API key here
MODEL_VERSION = "gemini-1.5-pro-002"
# MODEL_VERSION = "gemini-1.5-flash"
SYSTEM_INSTRUCTION = f"You are an expert in generating JSON objects. You receive a JSON schema and respond with a list of {BATCH_SIZE} JSON objects based on the JSON schema. Each object should include between 2 and 20 facts with diverse, realistic content and vary in which optional fields are filled. Ensure that optional fields are selectively included or omitted to create unique, authentic records, avoiding generic labels like 'Product 1', '[Company Name]', or 'email1@example.com.' Use natural, dynamic values without duplication. Output only the JSON objects with no explanations, placeholders, or additional text."
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(
    MODEL_VERSION, system_instruction=SYSTEM_INSTRUCTION
)

# Create directories to store generated JSON objects and completed schemas
objects_folder = "objects" # Replace with the path to your objects folder
completed_schemas_folder = "completed_schemas" # Replace with the path to your completed schemas folder
os.makedirs(f"{objects_folder}", exist_ok=True)
os.makedirs(f"{completed_schemas_folder}", exist_ok=True)

# Generate JSON objects based on each schema
schema_folder = "./schemas" # Replace with the path to your schema folder
for schema_file in os.listdir(schema_folder):
    if schema_file.endswith(".json"):
        # Load schema
        schema_path = os.path.join(schema_folder, schema_file)
        schema_name = schema_file.split(".")[0]
        with open(schema_path) as schema_file_content:
            schema = schema_file_content.read()

        # Prompt model to generate JSON objects and extract them from the response
        combined_json_objects = []
        for i in range(BATCHES):
            response = model.generate_content(schema)
            print(response.text)
            # Strip any ```json or ``` delimiters
            cleaned_response = response.text.replace("```json", "").replace("```", "").strip()

            json_objects = json.loads(cleaned_response)
            if isinstance(json_objects, list):
                combined_json_objects.extend(json_objects)
            else:
                combined_json_objects.append(json_objects)
            
            # Sleep for 60 seconds to avoid rate limiting
            time.sleep(60)

        # Save all JSON objects to a file
        output_path = f"./{objects_folder}/{schema_name}.json"
        with open(output_path, "w") as output_file:
            json.dump(combined_json_objects, output_file, indent=2)
        print(
            f"Generated {TOTAL_OBJECTS} JSON objects based on {schema_name} schema and saved to {output_path}"
        )

        # Move completed schema to another folder
        os.rename(schema_path, f"./{completed_schemas_folder}/{schema_file}")
