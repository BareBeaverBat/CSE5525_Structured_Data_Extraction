
#TODO will need to add logic at each stage to either add to a single data structure recording of which schema-idx/obj-idx pairings had problems (which gets saved at the end of the run, then we'd need a follow-up script to go through that) or else to reprompt whenever a problem arose (with limit on number of retries)

#TODO write logic to generate 100 objects and associated text passages for each schema, then to assemble one or more 'batches' of claude queries for reconstruction/validation step

#TODO function for downloading the results of a reconstruction-by-claude batch (once it's done), processing them (e.g. handling failed/expired cases or those with invalid responses) and creating a report about the schema-idx/obj-idx pairings that had problems (needing manual intervention to determine whether the issue was in the text passage generation or the obj reconstruction)

