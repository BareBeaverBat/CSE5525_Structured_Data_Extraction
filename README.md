# CSE5525_Structured_Data_Extraction
Evaluating and improving smallish language models for the purpose of extracting data from short text passages according to a schema that's provided at inference time. Will contain data preparation/validation code, evaluation code, and code for refinement methods like few-shot prompting and possibly self-consistency


# To set the environment variable
On Windows:
set OPENAI_API_KEY=your_api_key_here

On macOS/Linux:
export OPENAI_API_KEY=your_api_key_here

# Notes and assumptions
When comparing extractions we will ignore case based mismatches