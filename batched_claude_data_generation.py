


#TODO function for starting a batch with json obj generation prommpts
#TODO func for downloading the results of a json-obj-gen batch (once it's done), processing them (e.g. handling failed/expired cases or those with invalid responses) and creating new batch of prompts to deal with the problems from previous round
#TODO func for starting a batch with text generation prompts (given that it reads in the json objs from the previous step)
#TODO func for downloading the results of a text-gen batch (once it's done), processing them (e.g. handling failed/expired cases or those with invalid responses) and creating new batch of prompts to deal with the problems from previous round

#TODO function for starting a batch with json obj reconstruction-from-text-passage prompts
#TODO function for downloading the results of a json-obj-reconstruction batch (once it's done), processing them (e.g. handling failed/expired cases or those with invalid responses) and creating a report about the schema-idx/obj-idx pairings that had problems (needing manual intervention to determine whether the issue was in the text passage generation or the obj reconstruction)



#TODO main function that uses argparse to decide which of the above functions to call
# or possibly (ideally) a single function that flows through that process, with polling logic to wait for a batch to finish
