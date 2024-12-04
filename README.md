# CSE5525_Structured_Data_Extraction
Evaluating and improving smallish language models for the purpose of extracting data from short text passages according to a schema that's provided at inference time. Will contain data preparation/validation code, evaluation code, and code for refinement methods like few-shot prompting and possibly self-consistency

agenda
- fix some dataset issues
  - models apparently interpreted "termination clause" field for legal contract as something to be summarized/approximated, but imo it should be marked somehow as verbatim
    - maybe the system prompts can explain a special flag/suffix for json fields that should be treated that way
    - maybe simply the suffix "_verbatim"
    - update system prompts to explain how this flag should affect behavior in text passage generation and object extraction
    - review all previously-accepted records for scenario ids 3/13/14 and a) update field names in JSON plus b) double check that the text passage contains the exact text string from the verbatim-marked JSON field
  - at least gemini-produced data has a lot of obviously-fake and/or insufficiently-diverse data (e.g. "Jane Doe" or "John Doe" being used as a name and being used repeatedly, phone numbers starting with 555-, "email.com" as an email domain name, etc.)
    - ?experiment with effects of increasing gemini generation temperature to 1.5 or 2?
    - ?try tweaking object generation prompt
    - ?look more closely at claude and gemini data to see how widespread this is and whether there are other such problems
- ??process the examples from the big (260ish) review file
  - need to watch out for (tweaking both json object and text passage as necessary)
    - scenario id 4: 'experience_years' in flagged-for-review records
    - scenario ids 3/13/14: the addition of "_verbatim" suffix to some field names
- ?maybe another round of data generation?
- update/upgrade the dataset splitting code to 
  - use existing data loading/checking code, 
  - reserve some scenarios for only validation/test or only test sets, 
  - ~~maybe include training split in addition to fewshot/validation/test~~
  - double check whether the split is evenly including gemini-vs-claude-generated data in each partition
  - ideally, restructure how it stores the splits so that it 
    - doesn't repeat each schema string dozens of times and 
    - makes it easy to figure out which model generated a given record (and which scenario index it was associated with)
      - this latter desideratum would be useful for the data analysis and the report, breaking down how a given model's performance varied across different scenarios and source models
- upgrade/update the evaluation code to 
  - use existing data loading/checking code, 
  - check whether evaluation prompt could use some tweaking to match the original generation prompt, and whether the evaluation setting should be allowing CoT like the synthesis setting
  - get evaluation of gpt-4o working
  - set up testing of llama 3.1 70b and 405b using nebius to ensure reasonable costs
  - record full results (per-record, extraction-quality/fact-recall/hallucination-count) from an evaluation run in addition to computing/printing the summary statistics
  - jupyter notebook(s) to analyze the results
    - gpt-4o vs gpt-4o-mini vs llama 3.1 70b vs llama 3.1 405b
    - 0 shot vs 1 shot vs 3 shot vs 5 shot vs 10 shot vs 20 shot vs 50 shot prompting
    - whether different models struggled with different scenarios
    - whether source model (gemini vs claude) was a significant factor for some or all models, and if so whether they all had the same preference
  - if we have time, test how much of a difference it makes for the evaluation code to (first 2 are already implemented in generation code and would be easy to add):
    - allow CoT (extracting from a json-type markdown code block)
    - automatically validate the response for json-schema-compliance and reprompt if it fails that check
    - make several queries (3? 5? 10?) and use self-consistency to assemble a final result object field by field


# To set the environment variables
TODO add lines here for nebius/llama

On Windows:  
```cmd
set OPENAI_API_KEY=your_api_key_here
set ANTHROPIC_API_KEY=your_api_key_here
set GOOGLE_DEEPMIND_API_KEY=your_api_key_here
```

On macOS/Linux:  
```bash
export OPENAI_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_api_key_here
export GOOGLE_DEEPMIND_API_KEY=your_api_key_here
```

In Pycharm, you can modify a script's run configuration to include the environment variables.

In VS Code, you can do something similar.

If your Gemini/Google-DeepMind API key is on the Free Tier, you should also set the `GOOGLE_DEEPMIND_API_KEY_IS_FREE_TIER` environment variable to `True`. This will slow things down but will avert job failures.

# Notes and assumptions
When comparing extractions we will ignore case based mismatches.  
We also ignore singular vs plural discrepancies.

