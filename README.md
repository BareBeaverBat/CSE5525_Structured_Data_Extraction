# CSE5525_Structured_Data_Extraction
Evaluating and improving smallish language models for the purpose of extracting data from short text passages according to a schema that's provided at inference time. Will contain data preparation/validation code, evaluation code, and code for refinement methods like few-shot prompting and possibly self-consistency

agenda
- fix some dataset issues
  - add `"additionalProperties": false` to every object-type part of every one of the schemas!
  - remove "experience_years" from the schema, json objects, and text passages of "4_job_recruiting__resume_or_cv" case because the correct value would change every year
    - or at least there would be ambiguity about whether to infer the real number of years of experience from the earliest start date in the text passage and what the model 'thought' the current/'Present' year was
    - For example, some of the objects that initially failed auto-validation did so because the text passage generation didn't explicitly state the number of years of experience, but the model doing the extraction/reconstruction said "well, I know when their first position started, I 'know' the present time is at least _, and I can see an unbroken chain of employment from that start point to 'Present', so I can calculate total years of experience"
      - inconsistent behavior around when the model 'thinks' the current date is, maybe related to when the end of the pre-training data window was? sometimes vague talk that seems to assume "2023 or maybe later?", sometimes a confident and wrong (but less off in an absolute sense) assertion that the date is in "July 2024", etc.
  - models apparently interpreted "termination clause" field for legal contract as something to be summarized/approximated, but imo it should be marked somehow as verbatim
    - maybe the system prompts can explain a special flag/suffix for json fields that should be treated that way
    - maybe simply the suffix "_verbatim"
- process the examples from the big (260ish) review file
- maybe another round of data generation?
- update/upgrade the dataset splitting code to 
  - use existing data loading/checking code, 
  - reserve some scenarios for only validation/test or only test sets, 
  - maybe include training split in addition to fewshot/validation/test
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
  - if we have time, implement self-consistency and measure its effectiveness?


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

