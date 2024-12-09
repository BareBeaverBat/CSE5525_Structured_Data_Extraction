from data_processing.data_loading import load_scenarios, load_data_split
from data_processing.data_mngmt_defs import schemas_path, fewshot_examples_path, validation_set_path, test_set_path


#TODO function that takes a given folder of evaluation output/result records and analyzes it, accumulating statistics
# about the model's performance overall and also its performance broken down by either scenario or by source/generator model
# and also writing a comprehensive report for human review of any model output that the auto-grader marked wrong (as with the report generated for auto-validation failures in experimental_data_generation.py)

#todo main function that loads schemas, fewshot dataset split, and evaluation dataset split, and then calls the above functions
# for each model in a list, storing the results somewhere?

def main():
    scenario_domains, scenario_text_passage_descriptions, schemas = load_scenarios(schemas_path)
    
    fewshot_examples = load_data_split(fewshot_examples_path, schemas)
    validation_set = load_data_split(validation_set_path, schemas)
    test_set = load_data_split(test_set_path, schemas)
    
    
    
    pass

if __name__ == "__main__":
    main()
