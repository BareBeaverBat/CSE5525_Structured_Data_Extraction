import os
from enum import Enum
from pathlib import Path

from trivial_util_funcs import d

claude_folder_nm = "claude"
gemini_folder_nm = "gemini"


schemas_path = Path("json_schemas")
objects_path = Path("json_objects")
claude_objs_path = objects_path / claude_folder_nm
gemini_objs_path = objects_path / gemini_folder_nm
texts_path = Path("text_passages")
claude_texts_path = texts_path / claude_folder_nm
gemini_texts_path = texts_path / gemini_folder_nm

split_data_folder_path = Path("split_data")
fewshot_examples_path = split_data_folder_path / "fewshot_examples.json"
validation_set_path = split_data_folder_path / "validation_set.json"
test_set_path = split_data_folder_path / "test_set.json"

google_api_key_env = "GOOGLE_DEEPMIND_API_KEY"
is_google_api_key_using_free_tier = os.environ.get("GOOGLE_DEEPMIND_API_KEY_IS_FREE_TIER") == "True"
anthropic_api_key_env = "ANTHROPIC_API_KEY"

google_model_specifier = "gemini-1.5-pro-002"
anthropic_model_specifier = "claude-3-5-sonnet-20241022"

anthropic_generation_temp = 1.0
google_generation_temp = anthropic_generation_temp
anthropic_reconstruction_temp = 0.0
google_reconstruction_temp = anthropic_reconstruction_temp

anthropic_obj_gen_group_size = 20
google_obj_gen_group_size = anthropic_obj_gen_group_size

max_num_api_calls_for_schema_validation_retry_logic = 3

max_num_api_calls_for_anthropic_overloaded_retry_logic = 5
max_num_api_calls_for_google_refusals_retry_logic = 5

class ModelProvider(Enum):
    ANTHROPIC = "claude"
    GOOGLE_DEEPMIND = "gemini"


anthropic_object_generation_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario.
You will then be asked to generate diverse JSON objects following that schema. The objects should fill in different numbers of the non-required fields: some top-level array entries should fill in all optional fields while others fill only 1-2. They should largely make different choices about which optional fields to fill in (and, in the case of array-type fields, they should vary in how many things they put in that array type field). Meanwhile, each entry in the top-level array should contain no more than 20 pieces of information in total.
Use natural, dynamic values without duplication, avoiding generic or placeholder or obviously-fake values wherever possible. For example, don't use values like 'Product 1', '[Company Name]', 'email1@example.com', or "Shiny New Web App". It is also not appropriate in this context to use values that are subtly but detectably fake, e.g. values making pop-culture references.

Start by brainstorming a markdown list of descriptions for the different cases/objects that you'd generate.
Check whether they're diverse enough in terms of how-many/which optional fields they would fill in and how many things they put in array-type fields.
If there are any diversity problems with the original list of descriptions, revise it.
Finally, convert the last list of descriptions into a JSON array of JSON objects that obey the given schema. The JSON array of JSON objects should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").

When a schema field name ends with `_verbatim`, you should ensure that the corresponding JSON object field contains a string that would naturally show up in exactly that form in one of the current scenario's text passages.

Partial examples of good responses with JSON objects (omitting CoT analysis and full list of JSON objects for brevity):
--------------------
## Request 1

Here is such a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "patient_visit_notes" text passages.
Please generate a JSON array containing diverse JSON objects conforming to that schema, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```json
[
  {
    "symptoms": [
      {
        "name": "migraine headache",
        "duration_days": 3,
        "severity": 8,
        "frequency": "intermittent"
      },
      {
        "name": "nausea",
        "duration_days": 2,
        "severity": 6,
        "frequency": "occasional"
      }
    ],
    "medications": [
      {
        "name": "sumatriptan",
        "dosage": "100mg",
        "frequency": "as needed"
      },
      {
        "name": "ondansetron",
        "dosage": "4mg",
        "frequency": "twice daily"
      }
    ],
    "allergies": [
      "penicillin",
      "sulfa drugs",
      "latex"
    ],
    "family_history_flags": [
      "diabetes",
      "hypertension",
      "cancer"
    ]
  },
  {
    "medications": [
      {
        "name": "Lipitor",
        "dosage": "10mg",
        "frequency": "daily"
      },
      {
        "name": "Metformin",
        "dosage": "500mg",
        "frequency": "twice daily"
      },
      {
        "name": "Aspirin",
        "dosage": "81mg",
        "frequency": "daily"
      }
    ]
  },
  {
    "symptoms": [
      {
        "name": "Shortness of breath",
        "duration_days": 5,
        "severity": 6,
        "frequency": "intermittent"
      }
    ],
    "medications": [
      {
        "name": "Albuterol",
        "dosage": "2 puffs",
        "frequency": "as needed"
      }
    ],
    "allergies": [
      "Pollen"
    ],
    "family_history_flags": [
      "asthma"
    ]
  },
  ...
]
```

--------------------
## Request 2

Here is such a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "support ticket description" text passages.
Please generate a JSON array containing diverse JSON objects conforming to that schema, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```json
[
  {
    "product": {
      "name": "Keychron K3",
      "version": "2"
    },
    "impact_level": "minor",
    "system_state": {
      "os": "macOS 13.4"
    },
    "reproduction": {
      "reproducible": false,
      "frequency": "once"
    }
  },
  {
    "product": {
      "name": "Smart Thermostat"
    },
    "error_codes": [
      "ST-E001",
      "ST-E003",
      "ST-COMM-ERR"
    ],
    "impact_level": "minor",
    "system_state": {
      "os": "Android 12"
    }
  },
  ...
]
```

--------------------
""")

google_object_generation_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario.
You will then be asked to generate diverse JSON objects following that schema. The objects should fill in different numbers of the non-required fields: some top-level array entries should fill in all optional fields while others fill only 1-2. They should largely make different choices about which optional fields to fill in (and, in the case of array-type fields, they should vary in how many things they put in that array type field). Meanwhile, each entry in the top-level array should contain no more than 20 pieces of information in total.
Use natural, dynamic values without duplication, avoiding generic or placeholder values like 'Product 1', '[Company Name]', or 'email1@example.com'.

Start by brainstorming a markdown list of descriptions for the different cases/objects that you'd generate.
Check whether they're diverse enough in terms of how-many/which optional fields they would fill in and how many things they put in array-type fields.
If there are any diversity problems with the original list of descriptions, revise it.
Finally, convert the last list of descriptions into a JSON array of JSON objects that obey the given schema. The JSON array of JSON objects should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").

When a schema field name ends with `_verbatim`, you should ensure that the corresponding JSON object field contains a string that would naturally show up in exactly that form in one of the current scenario's text passages.

Partial examples of good responses with JSON objects (omitting CoT analysis and full list of JSON objects for brevity):
--------------------
## Request 1

Here is such a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "support ticket description" text passages.
Please generate a JSON array containing diverse JSON objects conforming to that schema, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```json
[
  {
    "product": {
      "name": "Dell Precision Touchpad",
      "model": "DL4872",
      "version": "10.3.302.13"
    },
    "error_codes": [
      "TPD-1044"
    ],
    "impact_level": "major",
    "reproduction": {
      "reproducible": true,
      "frequency": "sometimes"
    }
  },
  {
    "product": {
      "name": "MusicStreamer+"
    },
    "error_codes": [
      "MS-PLAYBACK-ERR"
    ],
    "impact_level": "blocking",
    "reproduction": {
      "reproducible": true,
      "frequency": "sometimes"
    },
    "system_state": {
      "browser": "Chrome 114"
    }
  },
  {
    "product": {
      "name": "SmartThings Hub",
      "model": "GP-U999SJVLGDA",
      "version": "43.6"
    },
    "system_state": {
      "connected_devices": [
        "Yale Lock YRD226",
        "Ecobee Thermostat",
        "Philips Hue Bridge",
        "Ring Doorbell Pro",
        "Samsung TV"
      ]
    }
  },
  ...
]
```

--------------------
## Request 2

Here is such a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "patient_visit_notes" text passages.
Please generate a JSON array containing diverse JSON objects conforming to that schema, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```json
[
  {
    "symptoms": [
      {
        "name": "sore throat"
      }
    ],
    "medications": [
      {
        "name": "acetaminophen"
      }
    ]
  },
  {
    "allergies": [
      "Penicillin",
      "Peanuts",
      "Dust mites"
    ],
    "family_history_flags": [
      "diabetes",
      "heart_disease"
    ]
  },
  {
    "symptoms": [
      {
        "name": "Shortness of breath",
        "duration_days": 5,
        "severity": 6,
        "frequency": "intermittent"
      }
    ],
    "medications": [
      {
        "name": "Albuterol",
        "dosage": "2 puffs",
        "frequency": "as needed"
      }
    ],
    "allergies": [
      "Pollen"
    ],
    "family_history_flags": [
      "asthma"
    ]
  },
  ...
]
```

--------------------
""")

anthropic_text_passage_generation_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a JSON object that follows that schema, and you will be asked to create a free-text document of the appropriate type from that JSON object. The free-text document must a) contain all information from the given object, b) contain no information that is relevant to the given schema but is not in the given object, and c) is otherwise filled out with plausible and coherent content. It should contain at least a few details that are context-appropriate, not relevant to the given schema, and not found in the given object.
It should NOT contain any obviously-fake, placeholder, or subtly-but-detectably-fake data like [Customer Name]
You should start your response by discussing the typical structure of the given type of free-text document and how each piece of information in the json object could be included naturally.
You should then analyze what fields from the schema are missing from the given object and how you can ensure that the text passage doesn't contain any information relevant to those missing fields.
You would then write a first draft of the text document (NOT in a markdown code block).
Please then review it to double check for any details that are relevant to the schema but not present in the json object. This includes cases where the text document says something that implies the value for a schema key is `null` or `[]` while the json object simply didn't mention that key from the schema.
Please also review it to ensure that every detail in the json object is included without loss of information in the text passage.
Finally, if a filled schema field's name ended in `_verbatim`, you should ensure that the corresponding text passage includes the exact value from the json object for that field.

After those checks, you would provide the final (possibly revised) free-text document inside a markdown code block to separate it from your analysis of the problem.

Partial examples of good responses (omitting CoT analysis for brevity):
--------------------
## Request 1

Here is a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "support ticket description" text passages.
Here is a JSON object that follows that schema:
```json
{
  "product": {
    "name": "SmartThings Hub",
    "model": "GP-U999SJVLGDA",
    "version": "43.6"
  },
  "system_state": {
    "connected_devices": [
      "Yale Lock YRD226",
      "Ecobee Thermostat",
      "Philips Hue Bridge",
      "Ring Doorbell Pro",
      "Samsung TV"
    ]
  }
}
```

Please generate a “support ticket description” free-text document that includes the JSON object's details, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```markdown
I am setting up my SmartThings Hub (Model: GP-U999SJVLGDA) running firmware version 43.6. I've successfully connected several devices to the hub, including my Yale Lock YRD226, Ecobee Thermostat, Philips Hue Bridge, Ring Doorbell Pro, and Samsung TV. I'm having trouble with some of the automation features and would appreciate some guidance on getting everything working together smoothly. The devices show up as connected, but I'm not sure if I've configured everything correctly. I've reviewed the quick start guide but feel I might be missing something in the setup process.
```

--------------------

## Request 2

Here is a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "patient visit notes" text passages.
Here is a JSON object that follows that schema:
```json
{
  "allergies": [
    "Penicillin",
    "Peanuts",
    "Dust mites"
  ],
  "family_history_flags": [
    "diabetes",
    "heart_disease"
  ]
}
```

Please generate a “patient visit notes” free-text document that includes the JSON object's details, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```markdown
Patient presented on October 26, 2024, for a routine check-up and discussion of preventative health measures.  The patient expressed concerns about their family history of diabetes and heart disease. They are particularly interested in understanding their risk factors and exploring lifestyle changes to mitigate those risks. The patient also confirmed known allergies to Penicillin, Peanuts, and Dust mites. Patient reports exercising regularly, mainly by walking, and maintains a balanced diet. They expressed interest in learning more about a heart-healthy diet and incorporating stress management techniques. We discussed a plan for follow-up appointments to monitor key health indicators and offer guidance on appropriate lifestyle modifications. Patient was provided with educational materials related to their concerns.
```

--------------------
""")

google_text_passage_generation_sys_prompt = ("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a JSON object that follows that schema, and you will be asked to create a free-text document of the appropriate type from that JSON object. The free-text document must a) contain all information from the given object, b) contain no information that is relevant to the given schema but is not in the given object, and c) is otherwise filled out with plausible and coherent content. It should contain at least a few details that are context-appropriate, not relevant to the given schema, and not found in the given object.
It should NOT contain any obviously-fake, placeholder, or subtly-but-detectably-fake data like [Customer Name]
You should start your response by discussing the typical structure of the given type of free-text document and how each piece of information in the json object could be included naturally.
You should then analyze what fields from the schema are missing from the given object and how you can ensure that the text passage doesn't contain any information relevant to those missing fields.
You would then write a first draft of the text document (NOT in a markdown code block).
Please then review it to double check for any details that are relevant to the schema but not present in the json object. This includes cases where the text document says something that implies the value for a schema key is `null` or `[]` while the json object simply didn't mention that key from the schema.
Please also review it to ensure that every detail in the json object is included without loss of information in the text passage.
Finally, if a filled schema field's name ended in `_verbatim`, you should ensure that the corresponding text passage includes the exact value from the json object for that field.

After those checks, you would provide the final (possibly revised) free-text document inside a markdown code block to separate it from your analysis of the problem.

Partial examples of good responses (omitting CoT analysis for brevity):
--------------------
## Request 1

Here is a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "patient visit notes" text passages.
Here is a JSON object that follows that schema:
```json
{
  "symptoms": [
    {
      "name": "migraine headache",
      "duration_days": 3,
      "severity": 8,
      "frequency": "intermittent"
    },
    {
      "name": "nausea",
      "duration_days": 2,
      "severity": 6,
      "frequency": "occasional"
    }
  ],
  "medications": [
    {
      "name": "sumatriptan",
      "dosage": "100mg",
      "frequency": "as needed"
    },
    {
      "name": "ondansetron",
      "dosage": "4mg",
      "frequency": "twice daily"
    }
  ],
  "allergies": [
    "penicillin",
    "sulfa drugs",
    "latex"
  ],
  "family_history_flags": [
    "diabetes",
    "hypertension",
    "cancer"
  ]
}
```

Please generate a “patient visit notes” free-text document that includes the JSON object's details, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```markdown
PATIENT VISIT NOTES

Chief Complaint:
Patient presents with migraine headache and nausea.

History of Present Illness:
Patient reports experiencing intermittent migraine headaches for the past 3 days, rating pain intensity as 8/10. Associated symptoms include occasional nausea for the past 2 days, with severity rated at 6/10. Patient appears uncomfortable but is in no acute distress.

Current Medications:
- Sumatriptan 100mg as needed for migraine
- Ondansetron 4mg twice daily for nausea

Allergies:
Patient has known allergies to:
- Penicillin
- Sulfa drugs
- Latex

Family History:
Significant family history of:
- Diabetes
- Hypertension
- Cancer

Physical Examination:
Patient is alert and oriented. Demonstrates mild photophobia and tenderness in temporal region. Vital signs within normal limits. Neurological examination grossly intact.

Assessment/Plan:
Will continue current medication regimen. Patient advised to maintain headache diary and follow up in one week if symptoms persist or worsen.
```

--------------------
## Request 2

Here is a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

This describes the pieces of information that someone might want to extract in a structured way from "support ticket description" text passages.
Here is a JSON object that follows that schema:
```json
{
  "product": {
    "name": "Smart Thermostat"
  },
  "error_codes": [
    "ST-E001",
    "ST-E003",
    "ST-COMM-ERR"
  ],
  "impact_level": "minor",
  "system_state": {
    "os": "Android 12"
  }
}
```

Please generate a “support ticket description” free-text document that includes the JSON object's details, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```markdown
My Smart Thermostat is showing multiple error codes and not working correctly. The error codes displayed are ST-E001, ST-E003, and ST-COMM-ERR. This is a minor inconvenience, as the main thermostat functions are still working, but some smart features seem to be unavailable. I am using an Android 12 device to control the thermostat. Earlier today, I noticed that some settings, like "eco mode" weren't available in the app.
```

--------------------
""")

anthropic_object_reconstruction_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a text passage of that scenario’s type, and you will be asked to create a JSON object that follows the given schema and captures all schema-relevant information that is in the text passage.
If there is no mention of anything related to a given schema key in the text, don't include that schema key in the JSON object. For example, if the schema has an array-type key and the text actually indicates that the correct number of entries for that array-type field is 0, then include that key, but simply omit that key if the text says nothing at all that's related to that array-type key.
Please start any response by analyzing each schema field in turn to see what in the text passage might be relevant to it. If nothing in the text is directly relevant for a schema field, you should note that (because such fields’ keys should be entirely omitted from the JSON object).
Watch out for cases where a phrase in the text passage could all be assigned to one key in the schema but the most reasonable fit is actually to split that phrase between two keys.
You should conclude the response with a json document containing a single JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage.
Any string values in the JSON object should be rendered in a manner that is as concise as possible without losing any specific information that couldn't be inferred from context and general world knowledge.
However, if the relevant schema field's name ends in `_verbatim`, you should ensure that the corresponding JSON object value includes the exact value from the text passage for that field.
This json document should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").

Partial examples of good responses (omitting CoT analysis for brevity):
--------------------
## Request 1

Here is a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

Here is the "patient visit notes" text passage.
```
Patient visit notes - 2024-03-15 10:00 AM

Patient reports shortness of breath that started five days ago. The shortness of breath is intermittent and of moderate severity (6/10). Patient describes it as worse with exertion.  Patient currently takes Albuterol, 2 puffs as needed.  Patient is allergic to pollen.  There is a family history of asthma.
```

Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```json
{
  "symptoms": [
    {
      "name": "Shortness of breath",
      "duration_days": 5,
      "severity": 6,
      "frequency": "intermittent"
    }
  ],
  "medications": [
    {
      "name": "Albuterol",
      "dosage": "2 puffs",
      "frequency": "as needed"
    }
  ],
  "allergies": [
    "Pollen"
  ],
  "family_history_flags": [
    "asthma"
  ]
}
```

--------------------
## Request 2

Here is a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

Here is the "support ticket description" text passage.
```
I am experiencing significant issues with my Dell Precision Touchpad (Model DL4872, version 10.3.302.13). The touchpad periodically becomes completely unresponsive, which is severely impacting my ability to work effectively. When this occurs, the system logs error code TPD-1044. 

I've been able to reproduce this issue, though it doesn't happen every time I use the computer. The problem seems to occur sometimes without any clear pattern. I've noticed it tends to happen more during extended work sessions, though I haven't identified any specific triggers.
```

Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```json
{
  "product": {
    "name": "Dell Precision Touchpad",
    "model": "DL4872",
    "version": "10.3.302.13"
  },
  "error_codes": [
    "TPD-1044"
  ],
  "impact_level": "major",
  "reproduction": {
    "reproducible": true,
    "frequency": "sometimes"
  }
}
```

--------------------
""")

google_object_reconstruction_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a text passage of that scenario’s type, and you will be asked to create a JSON object that follows the given schema and captures all schema-relevant information that is in the text passage.
If there is no mention of anything related to a given schema key in the text, don't include that schema key in the JSON object. For example, if the schema has an array-type key and the text actually indicates that the correct number of entries for that array-type field is 0, then include that key, but simply omit that key if the text says nothing at all that's related to that array-type key.
Please start any response by analyzing each schema field in turn to see what in the text passage might be relevant to it. If nothing in the text is directly relevant for a schema field, you should note that (because such fields’ keys should be entirely omitted from the JSON object).
Watch out for cases where a phrase in the text passage could all be assigned to one key in the schema but the most reasonable fit is actually to split that phrase between two keys.
You should conclude the response with a json document containing a single JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage.
Any string values in the JSON object should be rendered in a manner that is as concise as possible without losing any specific information that couldn't be inferred from context and general world knowledge.
However, if the relevant schema field's name ends in `_verbatim`, you should ensure that the corresponding JSON object value includes the exact value from the text passage for that field.
This json document should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").

Partial examples of good responses (omitting CoT analysis for brevity):
--------------------
## Request 1

Here is a JSON schema for the domain "customer service":
```json
{
"$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "model": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["name"]
    },
    "error_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "impact_level": {
      "type": "string",
      "enum": ["blocking", "major", "minor", "cosmetic"]
    },
    "system_state": {
      "type": "object",
      "properties": {
        "os": { "type": "string" },
        "browser": { "type": "string" },
        "connected_devices": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "reproduction": {
      "type": "object",
      "properties": {
        "reproducible": { "type": "boolean" },
        "frequency": {
          "type": "string",
          "enum": ["always", "often", "sometimes", "once"]
        }
      }
    }
  }
}
```

Here is the "support ticket description" text passage.
```
I am experiencing a critical issue with my Arctis Nova Pro headset (Model 61486, firmware version 2.4.3). The headset is completely unusable due to a series of errors that appear every time I try to use it.

My system is running Windows 11 with Chrome browser version 114.0.5735. The connected devices during this issue are my Arctis Nova Pro headset, a Logitech G502 mouse, and a Dell U2719D monitor.

When attempting to use the headset, I consistently receive three error codes: AUD-442, DRV-891, and USB-127. This issue is completely blocking my ability to use the product.

I can reproduce this issue 100% of the time - it happens without fail every single time I try to use the headset. I've tried disconnecting and reconnecting the device multiple times, but the behavior remains the same.
```

Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage, following the above instructions while doing so.

## Response 1

... (CoT analysis) ...

```json
{
  "product": {
    "name": "Arctis Nova Pro",
    "model": "61486",
    "version": "2.4.3"
  },
  "error_codes": [
    "AUD-442",
    "DRV-891",
    "USB-127"
  ],
  "impact_level": "blocking",
  "system_state": {
    "os": "Windows 11",
    "browser": "Chrome 114.0.5735",
    "connected_devices": [
      "Arctis Nova Pro",
      "Logitech G502",
      "Dell U2719D"
    ]
  },
  "reproduction": {
    "reproducible": true,
    "frequency": "always"
  }
}
```

--------------------
## Request 2

Here is a JSON schema for the domain "healthcare":
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "symptoms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "duration_days": { "type": "integer" },
          "severity": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10
            },
          "frequency": {
            "type": "string",
            "enum": ["constant", "intermittent", "occasional", "first_occurrence"]
          }
        },
        "required": ["name"]
      }
    },
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "dosage": { "type": "string" },
          "frequency": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "allergies": {
      "type": "array",
      "items": { "type": "string" }
    },
    "family_history_flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [ "diabetes", "heart_disease", "cancer", "asthma", "hypertension", "other" ]
      }
    }
  }
}
```

Here is the "patient visit notes" text passage.
```
PATIENT VISIT NOTES

Chief Complaint:
Patient presents with complaint of sore throat.

Physical Examination:
General appearance is well-kept. Vital signs within normal limits. Physical examination performed.

Assessment & Plan:
1. Sore throat
   - Patient advised to take acetaminophen for symptom management
   - Adequate hydration recommended
   - Gargle with warm salt water as needed
   - Follow-up recommended if symptoms persist or worsen
```

Please create a JSON object that obeys the given schema and captures all schema-relevant information that is actually present in or that is definitely implied by the text passage, following the above instructions while doing so.

## Response 2

... (CoT analysis) ...

```json
{
  "symptoms": [
    {
      "name": "sore throat"
    }
  ],
  "medications": [
    {
      "name": "acetaminophen"
    }
  ]
}
```

--------------------
""")