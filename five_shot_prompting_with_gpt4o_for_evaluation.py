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
#These examples are the top 5 from each schema, text and objects
# Removed these 5 object, text, and schemas from the fewshot json files
SYSTEM_INSTRUCTION = """
You are an expert in generating JSON objects. You receive a JSON schema and a text passage as inputs.
Respond with a JSON object only, formatted exactly according to the provided schema, without any additional text or comments.

Here are five examples of how the schema and text are with the corresponding JSON object:

1. Example 1:
Schema:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "symptoms": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "duration_days": {
              "type": "integer"
            },
            "severity": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "frequency": {
              "type": "string",
              "enum": [
                "constant",
                "intermittent",
                "occasional",
                "first_occurrence"
              ]
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "medications": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "dosage": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "allergies": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "family_history_flags": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "diabetes",
            "heart_disease",
            "cancer",
            "asthma",
            "hypertension",
            "other"
          ]
        }
      }
    }
  }
Text: "Patient presents for follow-up regarding ongoing allergy management. Reports experiencing intermittent seasonal allergies. Known allergies include ragweed, birch pollen, dust mites, and cat dander. Family medical history is significant for asthma, hypertension, and inflammatory bowel disease. Patient appears comfortable during examination. We discussed environmental modification strategies and avoiding known allergens. Patient was provided with educational materials about allergen avoidance techniques and understanding seasonal patterns. Will follow up as needed if symptoms worsen or new concerns arise."
JSON object: {
    "symptoms": [
      {
        "name": "seasonal allergies",
        "frequency": "intermittent"
      }
    ],
    "allergies": [
      "ragweed",
      "birch pollen",
      "dust mites",
      "cat dander"
    ],
    "family_history_flags": [
      "asthma",
      "other",
      "hypertension"
    ]
  }

2. Example 2:
Schema:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "symptoms": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "duration_days": {
              "type": "integer"
            },
            "severity": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "frequency": {
              "type": "string",
              "enum": [
                "constant",
                "intermittent",
                "occasional",
                "first_occurrence"
              ]
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "medications": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "dosage": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "allergies": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "family_history_flags": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "diabetes",
            "heart_disease",
            "cancer",
            "asthma",
            "hypertension",
            "other"
          ]
        }
      }
    }
  }

Text: "Patient presents with a sore throat that started three days ago. They have been taking acetaminophen for symptom relief. Patient reports adequate fluid intake and rest. Physical examination shows mild erythema of the posterior pharynx without exudates. Lymph nodes are not enlarged. Temperature is 98.6\u00b0F. Advised to continue current management with rest and hydration. Will follow up if symptoms worsen or fail to improve within the next few days."
JSON object: {
    "symptoms": [
      {
        "name": "sore throat",
        "duration_days": 3
      }
    ],
    "medications": [
      {
        "name": "acetaminophen"
      }
    ]
  }

3. Example 3:
Schema:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "symptoms": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "duration_days": {
              "type": "integer"
            },
            "severity": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "frequency": {
              "type": "string",
              "enum": [
                "constant",
                "intermittent",
                "occasional",
                "first_occurrence"
              ]
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "medications": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "dosage": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "allergies": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "family_history_flags": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "diabetes",
            "heart_disease",
            "cancer",
            "asthma",
            "hypertension",
            "other"
          ]
        }
      }
    }
  }
Text: "Patient presents today with complaints of shortness of breath and cough. The shortness of breath started 5 days ago and occurs occasionally, with the patient rating it as 6 out of 10 in severity. The cough is a symptom that the patient mentions but provides no additional details about its severity or when it started. \n\nThe patient is currently using albuterol inhaler, 90mcg, which they take every 4-6 hours as needed for symptom relief.\n\nFamily history is significant for asthma.\n\nVitals are stable. Lung examination reveals some mild wheezing in the upper lobes. Will continue current management with albuterol and follow up in two weeks."
JSON object: {
    "symptoms": [
      {
        "name": "shortness of breath",
        "duration_days": 5,
        "severity": 6,
        "frequency": "occasional"
      },
      {
        "name": "cough"
      }
    ],
    "medications": [
      {
        "name": "albuterol",
        "dosage": "90mcg",
        "frequency": "every 4-6 hours as needed"
      }
    ],
    "family_history_flags": [
      "asthma"
    ]
  }

4. Example 4:
Schema:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "symptoms": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "duration_days": {
              "type": "integer"
            },
            "severity": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "frequency": {
              "type": "string",
              "enum": [
                "constant",
                "intermittent",
                "occasional",
                "first_occurrence"
              ]
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "medications": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "dosage": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "allergies": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "family_history_flags": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "diabetes",
            "heart_disease",
            "cancer",
            "asthma",
            "hypertension",
            "other"
          ]
        }
      }
    }
  }
Text: "Patient presents today with complaints of intermittent migraines over the past 3 days, rating pain intensity at 8/10. Associated symptoms include occasional nausea over the past 2 days and intermittent sensitivity to light (photophobia) rated at 7/10. Patient reports the symptoms are interfering with their ability to work and perform daily activities. Patient appears in mild distress during examination, wearing sunglasses in the office. Neurological examination performed, showing no focal deficits. Discussed lifestyle triggers and stress management techniques. Will schedule follow-up in two weeks to assess response to treatment plan."
JSON object: {
    "symptoms": [
      {
        "name": "migraine",
        "duration_days": 3,
        "severity": 8,
        "frequency": "intermittent"
      },
      {
        "name": "nausea",
        "duration_days": 2,
        "frequency": "occasional"
      },
      {
        "name": "photophobia",
        "severity": 7,
        "frequency": "intermittent"
      }
    ]
  }

5. Example 5:
Schema:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "symptoms": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "duration_days": {
              "type": "integer"
            },
            "severity": {
              "type": "integer",
              "minimum": 1,
              "maximum": 10
            },
            "frequency": {
              "type": "string",
              "enum": [
                "constant",
                "intermittent",
                "occasional",
                "first_occurrence"
              ]
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "medications": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string"
            },
            "dosage": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          },
          "required": [
            "name"
          ]
        }
      },
      "allergies": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "family_history_flags": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": [
            "diabetes",
            "heart_disease",
            "cancer",
            "asthma",
            "hypertension",
            "other"
          ]
        }
      }
    }
  }
  
Text: "Patient presents for follow-up of rheumatologic symptoms. Primary concerns include intermittent joint pain rated 7/10 in severity that started approximately 3 months ago, affecting multiple joints symmetrically. Patient also reports constant fatigue for the past 4 months (5/10 severity) that impacts daily activities, particularly in the afternoon. Morning stiffness (6/10 severity) has been present for 3 months, occurring intermittently and typically lasting about an hour after waking.\n\nCurrent medications include methotrexate 15mg weekly and folic acid 1mg daily, both started at previous visit. Medication compliance has been good with no missed doses.\n\nMedical history includes known allergies to ibuprofen and shellfish. Family history is significant for diabetes and cancer.\n\nPhysical examination shows mild synovitis in several MCP joints bilaterally. Range of motion is slightly decreased in affected joints. Vital signs are stable with BP 118/76, HR 72, temp 98.6\u00b0F.\n\nAssessment: Symptoms showing early response to current medication regimen. Will continue current doses and monitor for improvement.\n\nPlan:\n1. Continue current medications unchanged\n2. Return for follow-up in 6 weeks\n3. Complete scheduled lab work prior to next visit\n4. Call if symptoms worsen or new symptoms develop"
JSON object: {
    "symptoms": [
      {
        "name": "joint pain",
        "duration_days": 90,
        "severity": 7,
        "frequency": "intermittent"
      },
      {
        "name": "fatigue",
        "duration_days": 120,
        "severity": 5,
        "frequency": "constant"
      },
      {
        "name": "morning stiffness",
        "duration_days": 90,
        "severity": 6,
        "frequency": "intermittent"
      }
    ],
    "medications": [
      {
        "name": "methotrexate",
        "dosage": "15mg",
        "frequency": "weekly"
      },
      {
        "name": "folic acid",
        "dosage": "1mg",
        "frequency": "daily"
      }
    ],
    "allergies": [
      "ibuprofen",
      "shellfish"
    ],
    "family_history_flags": [
      "diabetes",
      "cancer"
    ]
  }

Use these examples to guide your response, ensuring that the JSON object you generate matches the schema exactly.
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
schema_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'validation_schema.json')
text_file_path = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'validation_text_passages.json')
test_obj = os.path.join(parent_dir, 'Third Year', 'Speech and Language','CSE5525_Structured_Data_Extraction','datasets' , 'validation_objs.json')

# Log file paths for debugging
logger.info(f"Attempting to open schema file: {schema_file_path}")
logger.info(f"Attempting to open text file: {text_file_path}")
logger.info(f"Attempting to open expected schema file: {test_obj}")

# Load the schema, texts, and expected schemas
schema = load_schema_from_file(schema_file_path)
texts = load_text_from_file(text_file_path)
expected_schemas = load_expected_schema(test_obj)

# Skip the first five entries in all three files becuase they are given as the examples for prompting
schema = schema[5:]
texts = texts[5:]
expected_schemas = expected_schemas[5:]

# Function to call GPT model with system instruction only
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
