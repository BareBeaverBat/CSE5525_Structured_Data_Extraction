Scott's ideas for possible next steps after the course is done:

- fix some dataset issues
    - at least gemini-produced data has a lot of obviously-fake and/or insufficiently-diverse data (e.g. "Jane Doe" or "John Doe" being used as a name and being used repeatedly, phone numbers starting with 555-, "email.com" as an email domain name, etc.)
        - look more closely at claude and gemini data to see how widespread this is and whether there are other such problems
        - experiment with effects of increasing gemini generation temperature to 1.5 or 2
        - try tweaking object generation prompt
- process the examples from the big (260ish) review file
    - need to watch out for (tweaking both json object and text passage as necessary)
        - scenario id 4: 'experience_years' in flagged-for-review records
        - scenario ids 3/13/14: the addition of "_verbatim" suffix to some field names
- Evaluate whether self-review with self-consistency at the
  json-object-generation stage and again at the text passage
  generation stage improves the quality of generated records.
  - Self-review with self-consistency might involve 3-5 additional API calls per json object or text passage to scrutinize
    it for rule-following and plausibility, with the object or
    passage being regenerated if a majority of the self-review
    API calls judged it to not be following all instructions fully
  - If frontier models can actually associate points of criticism
    with locations in the JSON object (i.e. JSONPath strings) or
    text passage (e.g. sentence numbers) reliably enough, we
    might even be able to include feedback in the regeneration
    prompt (i.e. feedback from critic LLM responses) based
    on which pieces of feedback referred to sections of the
    thing being critiqued that a majority of critic responses
    took issue with.
- Make multiple reconstruction attempts with nonzero temperature (in the new-data-validation stage) to reduce the risk
  that imperfect records are saved as part of the dataset because the validating LLM happened to miss an extra (not in the original JSON object) schema-relevant detail (in the text passage) some of the time.
- Add a self-consistency component to the structured-extraction-from-text-passage code. This could involve making multiple
  (3, 5, or even 10) queries per text passage and only including
  a given piece of information in the final result object if it
  was found in a majority of the queries’ outputs.
- Add a self-consistency component to the structured-extraction-from-text-passage code. This could involve making multiple
  (3, 5, or even 10) queries per text passage and only including
  a given piece of information in the final result object if it
  was found in a majority of the queries’ outputs.
- ?implement a version of the data synthesis pipeline that uses Anthropic's and Google Vertex's batch API's for the 50% discount  
- another round of data generation (bringing total dataset size to 3-5k)
- update/upgrade the dataset splitting code to
    - reserve some scenarios for only validation/test sets and to reserve some for only the test set,
    - include training split in addition to fewshot/validation/test
    - double check whether the split is evenly including gemini-vs-claude-generated data in each partition
    - evenly distribute a scenario's records across the partition that that scenario is allowed to be a part of
- test more models
    - o1-mini would be very interesting and is only slightly more expensive than gpt-4o, but that would require some annoying hacks because e.g. it doesn't support the "system" role in its prompt messages and would need higher limit on output tokens than other models and so on
    - Given how well even GPT-4o-mini did, it would be good to find out how well even a comparatively quite small LLM like Llama 3.1 8B or Gemma 2 9B would do.
- test out SFT of Llama 3.3 70B
- test out RL fine-tuning of GPT-4o-mini
