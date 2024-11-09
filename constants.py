from pathlib import Path


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
anthropic_api_key_env = "ANTHROPIC_API_KEY"

google_model_specifier = "gemini-1.5-pro-002"
anthropic_model_specifier = "claude-3-5-sonnet-20241022"
