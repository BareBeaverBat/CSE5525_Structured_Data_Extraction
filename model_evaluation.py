



#todo function that takes an OpenAI client object (unknown whether it's for actual OpenAI api or some other provider
# like DeepInfra) and a model specification/name, a set of fewshot examples, a set of examples to evaluate the model on,
# how many fewshot examples to use (possibly 0), and a boolean flag for whether to modify
# a) the prompt, b) the request's output format specification, and c) the response-processing logic to allow CoT
# For each evaluation record, it should store in some file the model's full response and (if relevant) the isolated json object along with the fewshot examples that were used in that case? or maybe just the indexes (within the current fewshot_examples.json) of the examples used
#  Then analysis can be done later by another method


#TODO function that takes a given folder of evaluation output/result records and analyzes it, accumulating statistics
# about the model's performance overall and also its performance broken down by either scenario or by source/generator model
# and also writing a comprehensive report for human review of any model output that the auto-grader marked wrong (as with the report generated for auto-validation failures in experimental_data_generation.py)

#todo main function that loads schemas, fewshot dataset split, and evaluation dataset split, and then calls the above functions
# for each model in a list, storing the results somewhere?


