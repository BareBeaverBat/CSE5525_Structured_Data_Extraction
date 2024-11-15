from enum import Enum
from pathlib import Path

from misc_util_funcs import d

claude_folder_nm = "claude"
gemini_folder_nm = "gemini"


schemas_path = Path("json_schemas")
objects_path = Path("json_objects")
claude_objs_path = objects_path / claude_folder_nm
gemini_objs_path = objects_path / gemini_folder_nm
texts_path = Path("text_passages")
claude_texts_path = texts_path / claude_folder_nm
gemini_texts_path = texts_path / gemini_folder_nm

google_api_key_env = "GOOGLE_DEEPMIND_API_KEY"
is_google_api_key_using_free_tier = True#change this to False in local copy of code when using a paid API key, b/c otherwise activities with Gemini will be very slow
anthropic_api_key_env = "ANTHROPIC_API_KEY"

google_model_specifier = "gemini-1.5-pro-002"
anthropic_model_specifier = "claude-3-5-sonnet-20241022"

anthropic_generation_temp = 1.0
google_generation_temp = anthropic_generation_temp
anthropic_reconstruction_temp = 0.0
google_reconstruction_temp = anthropic_reconstruction_temp

anthropic_obj_gen_group_size = 5
google_obj_gen_group_size = 5

max_num_api_calls_for_retry_logic = 3

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
""")

google_object_generation_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario.
You will then be asked to generate diverse JSON objects following that schema. The objects should fill in different numbers of the non-required fields: some top-level array entries should fill in all optional fields while others fill only 1-2. They should largely make different choices about which optional fields to fill in (and, in the case of array-type fields, they should vary in how many things they put in that array type field). Meanwhile, each entry in the top-level array should contain no more than 20 pieces of information in total.
Use natural, dynamic values without duplication, avoiding generic or placeholder values like 'Product 1', '[Company Name]', or 'email1@example.com'.

Start by brainstorming a markdown list of descriptions for the different cases/objects that you'd generate.
Check whether they're diverse enough in terms of how-many/which optional fields they would fill in and how many things they put in array-type fields.
If there are any diversity problems with the original list of descriptions, revise it.
Finally, convert the last list of descriptions into a JSON array of JSON objects that obey the given schema. The JSON array of JSON objects should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").
""")

anthropic_text_passage_generation_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a JSON object that follows that schema, and you will be asked to create a free-text document of the appropriate type from that JSON object. The free-text document must a) contain all information from the given object, b) contain no information that is relevant to the given schema but is not in the given object, and c) is otherwise filled out with plausible and coherent content. It should contain at least a few details that are context-appropriate, not relevant to the given schema, and not found in the given object.
It should NOT contain any obviously-fake, placeholder, or subtly-but-detectably-fake data like [Customer Name]
You should start your response by discussing the typical structure of the given type of free-text document and how each piece of information in the json object could be included naturally.
You should then analyze what fields from the schema are missing from the given object and how you can ensure that the text passage doesn't contain any information relevant to those missing fields.
You would then write a first draft of the text document (NOT in a markdown code block).
Please then review it to double check for any details that are relevant to the schema but not present in the json object. This includes cases where the text document says something that implies the value for a schema key is `null` or `[]` while the json object simply didn't mention that key from the schema.
Finally, you would provide the final (possibly revised) free-text document inside a markdown code block to separate it from your analysis of the problem.
""")

google_text_passage_generation_sys_prompt = anthropic_text_passage_generation_sys_prompt

anthropic_object_reconstruction_sys_prompt = d("""
You will be given a JSON schema that describes the pieces of information that someone might want to extract in a structured way from text passages in a particular scenario. You will also be given a text passage of that scenario’s type, and you will be asked to create a JSON object that follows the given schema and captures all schema-relevant information that is in the text passage.
If there is no mention of anything related to a given schema key in the text, don't include that schema key in the JSON object. For example, if the schema has an array-type key and the text actually indicates that the correct number of entries for that array-type field is 0, then include that key, but simply omit that key if the text says nothing at all that's related to that array-type key.
Please start any response by analyzing each schema field in turn to see what in the text passage might be relevant to it. If nothing in the text is directly relevant for a schema field, you should note that (because such fields’ keys should be entirely omitted from the JSON object).
You should conclude the response with a json document containing a single JSON object that obeys the given schema and captures all schema-relevant information that is actually present in  or that is definitely implied by the text passage. This json document should be in a json-labelled markdown code block (i.e. with 'json' after the first triplet of back ticks, like "```json").
""")

google_object_reconstruction_sys_prompt = anthropic_object_reconstruction_sys_prompt