# CSE5525_Structured_Data_Extraction
Evaluating and improving smallish language models for the purpose of extracting data from short text passages according to a schema that's provided at inference time. Will contain data preparation/validation code, evaluation code, and code for refinement methods like few-shot prompting and possibly self-consistency

For a summary of this project, please see the [project's final report](Improving_structured_details_extraction_from_short_text_passages_with_LLMs.pdf).

# To set the environment variables

On Windows:  
```cmd
set OPENAI_API_KEY=your_api_key_here
set ANTHROPIC_API_KEY=your_api_key_here
set GOOGLE_DEEPMIND_API_KEY=your_api_key_here
set DEEPINFRA_API_KEY=your_api_key_here
```

On macOS/Linux:  
```bash
export OPENAI_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_api_key_here
export GOOGLE_DEEPMIND_API_KEY=your_api_key_here
export DEEPINFRA_API_KEY=your_api_key_here
```

In Pycharm, you can modify a script's run configuration to include the environment variables.

In VS Code, you can do something similar.

If your Gemini/Google-DeepMind API key is on the Free Tier, you should also set the `GOOGLE_DEEPMIND_API_KEY_IS_FREE_TIER` environment variable to `True`. This will slow things down but will avert job failures.

# Notes and assumptions
When comparing extractions we will ignore case based mismatches.  
We also ignore singular vs plural discrepancies.

