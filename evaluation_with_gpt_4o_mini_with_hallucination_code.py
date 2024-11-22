import json
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Union
from collections import Counter
from us import states
from logging_setup import create_logger

logger = create_logger(__name__)

PrimitiveJsonVal = Union[str, int, float, bool, None]
AnyJsonVal = Union[PrimitiveJsonVal, dict, list]

@dataclass(order=True)
class PrioritizedImperfectMatch:
    #when comparing entries from 2 lists whose entries are lists or dicts; this is used in a priority queue of possible matches for a given entry of the expected-side list
    score: int #lower is better, compute as hallucinated_info_count - correct_info_count
    idx_in_actual_list: int=field(compare=False)
    correct_info_count: int=field(compare=False)
    hallucinated_info_count: int=field(compare=False)
    differences: list[str]=field(compare=False)


def count_total_pieces_of_info_in_json(json_obj: AnyJsonVal) -> int:
    if isinstance(json_obj, dict) and len(json_obj) > 0:
        return sum(count_total_pieces_of_info_in_json(val) for val in json_obj.values())
    if isinstance(json_obj, list) and len(json_obj) > 0:
        return sum(count_total_pieces_of_info_in_json(val) for val in json_obj)
    #treating an empty list or dict as a single piece of information
    return 1


def separate_duplicates_in_primitive_list(primitive_list: list[PrimitiveJsonVal]) -> (list[PrimitiveJsonVal], list[tuple[PrimitiveJsonVal, int]]):
    counts = Counter(primitive_list)
    duplicates = [(val, count) for val, count in counts.items() if count > 1]
    unique_vals = [val for val, count in counts.items() if count == 1]
    return unique_vals, duplicates

def is_singular_plural_match(expected: str, actual: str) -> bool:
    """
    Determine whether two strings represent singular and plural forms of the same word.

    Args:
        expected (str): The expected string
        actual (str): The actual string

    Returns:
        bool: True if the strings are singular/plural forms of the same word, False otherwise.
    """
    # Define common pluralization rules
    def is_plural_of_singular(singular, plural):
        return (
                singular + 's' == plural
                or (singular.endswith('y') and plural == singular[:-1] + 'ies')
                or (singular.endswith(('s', 'sh', 'ch', 'x', 'z')) and plural == singular + 'es')
                or (singular.endswith('f') and plural == singular[:-1] + 'ves')
                or (singular.endswith('fe') and plural == singular[:-2] + 'ves')
        )
    
    # Check both directions since either string could be singular or plural
    return is_plural_of_singular(expected, actual) or is_plural_of_singular(actual, expected)

def compare_values_from_json(expected: PrimitiveJsonVal, actual: PrimitiveJsonVal, path: str) -> bool:
    assert not isinstance(expected, dict) and not isinstance(actual, dict), f"compare_values should only be called with non-dict values; path: {path}"
    assert not isinstance(expected, list) and not isinstance(actual, list), f"compare_values should only be called with non-list values; path: {path}"
    if expected == actual:
        return True
    is_expected_str = isinstance(expected, str)
    is_actual_str = isinstance(actual, str)
    if is_expected_str and is_actual_str:
        lc_expected = expected.lower()
        lc_actual = actual.lower()
        if lc_expected == lc_actual:
            return True
        if is_singular_plural_match(lc_expected, lc_actual):
            logger.debug(f"expected and actual values at path {path} were singular/plural matches: {expected} and {actual}")
            return True
        if states.lookup(expected) == states.lookup(actual):
            logger.debug(f"expected and actual values at path {path} were state names: {expected} and {actual}")
            return True
    elif (isinstance(expected, int) and is_actual_str) or (is_expected_str and isinstance(actual, int)):
        curr_str_val: str = actual if is_actual_str else expected
        curr_int_val: int = expected if is_actual_str else actual
        try:
            if int(curr_str_val) == curr_int_val:
                logger.debug(f"expected and actual values at path {path} were effectively equal after parsing int from str: {expected} and {actual}")
                return True
        except ValueError:
            pass
    elif (isinstance(expected, float) or isinstance(actual, float)) and isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if abs(expected - actual) < 1e-6:
            return True
    return False

def compare_lists_from_json(expected_list: list, actual_list: list, path:str) -> (int, int, list[str]):
    """
    
    :param expected_list:
    :param actual_list:
    :param path:
    :return: a tuple of (total number correctly extracted pieces of information from this path inward, total number of hallucinated pieces of information from this path inward, list of descriptions of differences)
    """
    assert isinstance(expected_list, list) and isinstance(actual_list, list), f"compare_lists should only be called with list values; path: {path}"
    
    expected_entries_all_primitive = all(not isinstance(item, (dict, list)) for item in expected_list)
    expected_entries_all_lists = all(isinstance(item, list) for item in expected_list)
    expected_entries_all_dicts = all(isinstance(item, dict) for item in expected_list)
    
    total_num_correctly_extracted_pieces_of_info = 0
    total_num_hallucinated_pieces_of_info = 0
    differences = []
    
    if len(expected_list) == 0:
        if len(actual_list) == 0:
            total_num_correctly_extracted_pieces_of_info += 1
        else:
            total_num_hallucinated_pieces_of_info += count_total_pieces_of_info_in_json(actual_list)
            differences.append(f"Expected an empty array at {path}, but got an array with entries: {json.dumps(actual_list)}")
    elif len(actual_list) == 0:
        differences.append(f"Expected an array at {path} with entries: {json.dumps(expected_list)}, but got an empty array")
    elif expected_entries_all_primitive:
        actual_complex_vals = [val for val in actual_list if isinstance(val, (list, dict))]
        if actual_complex_vals:
            total_num_hallucinated_pieces_of_info += count_total_pieces_of_info_in_json(actual_complex_vals)
            differences.append(f"Expected only primitive values in {path}, but got some array or object type entries: {json.dumps(actual_complex_vals)}")
        actual_primitives_list: list[PrimitiveJsonVal] = [val for val in actual_list if not isinstance(val, (dict, list))]
        #based on constraints of JSON, this means the values in both lists will be of hashable types, so we can use set operations as long as we account for duplicates in a list
        
        if all(isinstance(val, str) for val in expected_list) and all(isinstance(val, str) for val in actual_list):
            expected_list = [val.lower() for val in expected_list]
            actual_primitives_list = [val.lower() for val in actual_primitives_list]
        
        expected_nondup_vals, expected_dup_vals = separate_duplicates_in_primitive_list(expected_list)
        actual_nondup_vals, actual_dup_vals = separate_duplicates_in_primitive_list(actual_primitives_list)
        
        excess_nondup_vals = list(set(actual_nondup_vals) - set(expected_nondup_vals))
        missed_nondup_vals = list(set(expected_nondup_vals) - set(actual_nondup_vals))
        
        missed_nondup_idxs_matched_to_actual_dup = set()
        actual_dup_idxs_matched_to_missed_nondup = set()
        for i, missed_nondup_val in enumerate(missed_nondup_vals):
            for j, actual_dup_val in enumerate(actual_dup_vals):
                if j in actual_dup_idxs_matched_to_missed_nondup:
                    continue
                actual_dup_val_value=actual_dup_val[0]
                actual_dup_val_count=actual_dup_val[1]
                
                if compare_values_from_json(missed_nondup_val, actual_dup_val_value, f"{path}[{expected_list.index(missed_nondup_val)}]"):
                    missed_nondup_idxs_matched_to_actual_dup.add(i)
                    actual_dup_idxs_matched_to_missed_nondup.add(j)
                    total_num_correctly_extracted_pieces_of_info += 1
                    total_num_hallucinated_pieces_of_info += actual_dup_val_count - 1
                    differences.append(f"Expected value {missed_nondup_val} was present in the actual array at path {path} but had {actual_dup_val_count} copies in the actual array (rather than 1)")
                    break
        
        missed_nondup_vals = [missed_nondup_vals[i] for i in range(len(missed_nondup_vals)) if i not in missed_nondup_idxs_matched_to_actual_dup]
        actual_dup_vals = [actual_dup_vals[j] for j in range(len(actual_dup_vals)) if j not in actual_dup_idxs_matched_to_missed_nondup]

        expected_dup_idxs_matched_to_excess_nondup = set()
        excess_nondup_idxs_matched_to_expected_dup = set()
        for i, expected_dup_val in enumerate(expected_dup_vals):
            for j, excess_nondup_val in enumerate(excess_nondup_vals):
                if j in excess_nondup_idxs_matched_to_expected_dup:
                    continue
                expected_dup_val_value=expected_dup_val[0]
                expected_dup_val_count=expected_dup_val[1]
                
                if compare_values_from_json(expected_dup_val_value, excess_nondup_val, f"{path}[{expected_list.index(expected_dup_val_value)}]"):
                    expected_dup_idxs_matched_to_excess_nondup.add(i)
                    excess_nondup_idxs_matched_to_expected_dup.add(j)
                    total_num_correctly_extracted_pieces_of_info += 1
                    differences.append(f"at path {path}, Expected value {expected_dup_val_value} was present in the actual array just once but had {expected_dup_val_count} copies in the expected array")
                    break
        
        expected_dup_vals = [expected_dup_vals[i] for i in range(len(expected_dup_vals)) if i not in expected_dup_idxs_matched_to_excess_nondup]
        excess_nondup_vals = [excess_nondup_vals[j] for j in range(len(excess_nondup_vals)) if j not in excess_nondup_idxs_matched_to_expected_dup]
        
        total_num_correctly_extracted_pieces_of_info += len(expected_nondup_vals) - len(missed_nondup_vals)
        if missed_nondup_vals:
            differences.append(f"Missed values in {path} (which weren't supposed to be duplicated): {missed_nondup_vals}")
        if excess_nondup_vals:
            differences.append(f"Excess values in {path} (which at least didn't show up multiple times in the actual array): {excess_nondup_vals}")
            total_num_hallucinated_pieces_of_info += len(excess_nondup_vals)

        expected_dup_idxs_matched_to_actual_dup = set()
        actual_dup_idxs_matched_to_expected_dup = set()
        for i, expected_dup_val in enumerate(expected_dup_vals):
            for j, actual_dup_val in enumerate(actual_dup_vals):
                if j in actual_dup_idxs_matched_to_expected_dup:
                    continue
                expected_dup_val_value=expected_dup_val[0]
                expected_dup_val_count=expected_dup_val[1]
                actual_dup_val_value=actual_dup_val[0]
                actual_dup_val_count=actual_dup_val[1]
                
                if compare_values_from_json(expected_dup_val_value, actual_dup_val_value, f"{path}[{expected_list.index(expected_dup_val_value)}]"):
                    expected_dup_idxs_matched_to_actual_dup.add(i)
                    actual_dup_idxs_matched_to_expected_dup.add(j)
                    total_num_correctly_extracted_pieces_of_info += min(expected_dup_val_count, actual_dup_val_count)
                    if actual_dup_val_count > expected_dup_val_count:
                        total_num_hallucinated_pieces_of_info += actual_dup_val_count - expected_dup_val_count
                        differences.append(f"The value {expected_dup_val_value} that was present multiple times in the expected array at path {path} was present multiple times in the actual array but had {actual_dup_val_count-expected_dup_val_count} too many copies in the actual array")
                    elif actual_dup_val_count < expected_dup_val_count:
                        differences.append(f"The value {expected_dup_val_value} that was present multiple times in the expected array at path {path} was present multiple times in the actual array but had {actual_dup_val_count-expected_dup_val_count} too few copies in the actual array")
                    break
        
        missing_dup_vals = [expected_dup_vals[i] for i in range(len(expected_dup_vals)) if i not in expected_dup_idxs_matched_to_actual_dup]
        excess_dup_vals = [actual_dup_vals[j] for j in range(len(actual_dup_vals)) if j not in actual_dup_idxs_matched_to_expected_dup]
        
        if missing_dup_vals:
            differences.append(f"at {path}, certain values showed up multiple times in the expected array but not at all in the actual array: {missing_dup_vals}")
        if excess_dup_vals:
            differences.append(f"at {path}, certain values showed up multiple times in the actual array but not at all in the expected array: {excess_dup_vals}")
            total_num_hallucinated_pieces_of_info += sum(val[1] for val in excess_dup_vals)
        
    elif expected_entries_all_lists or expected_entries_all_dicts:
        #i.e. expected_entries_are_list_vs_dict is True if entries are all lists, it's False if entries are all dicts
        expected_entries_are_list_vs_dict = expected_entries_all_lists
        json_type_nm = "array" if expected_entries_are_list_vs_dict else "object"
        expected_py_type = list if expected_entries_are_list_vs_dict else dict
        
        actual_entries_of_wrong_type = [val for val in actual_list if not isinstance(val, expected_py_type)]
        if actual_entries_of_wrong_type:
            total_num_hallucinated_pieces_of_info += count_total_pieces_of_info_in_json(actual_entries_of_wrong_type)
            differences.append(f"Expected only {json_type_nm} values in {path}, but got some non-{json_type_nm} entries: {actual_entries_of_wrong_type}")
        
        expected_entries: list[list[AnyJsonVal]] | list[dict[str, AnyJsonVal]] = expected_list
        actual_entries: list[list[AnyJsonVal]] | list[dict[str, AnyJsonVal]] = [val for val in actual_list if isinstance(val, expected_py_type)]
        
        if len(actual_entries) == 0:
            differences.append(f"Expected an array at {path} with one or more {json_type_nm}-type entries: {json.dumps(expected_list)}, but got an array whose entries were all of non-{json_type_nm} types")
        else:
            #this greedy matching can probably be surpassed by some dynamic programming optimization of all of the
            # expected-list's entries' matches at once; that currently seems not even remotely worth the effort
            matched_positions_in_expected = set()
            matched_positions_in_actual = set()
            ranking_of_imperfect_matches_for_expected: dict[int, PriorityQueue[PrioritizedImperfectMatch]] = {}
            for i, expected_list_entry in enumerate(expected_entries):
                ranking_of_imperfect_matches_for_expected[i] = PriorityQueue()
                for j, actual_list_entry in enumerate(actual_entries):
                    if j in matched_positions_in_actual:
                        continue
                    #this if block is supposed to just be a performance boost relative to the recursive call (in cases where the entries are sublists that're exactly the same including in terms of order)
                    if expected_list_entry == actual_list_entry:
                        matched_positions_in_expected.add(i)
                        matched_positions_in_actual.add(j)
                        total_num_correctly_extracted_pieces_of_info += count_total_pieces_of_info_in_json(expected_list_entry)
                        break
                    correct_info_count_for_pairing: int
                    hallucinated_info_count_for_pairing: int
                    differences_for_pairing: list[str]
                    if expected_entries_are_list_vs_dict:
                        assert isinstance(expected_list_entry, list) and isinstance(actual_list_entry, list), f"expected_list_entry and actual_list_entry should both be lists in this scenario, something went wrong with the generified code for iterating over complex entries in arrays; path: {path}"
                        (correct_info_count_for_pairing, hallucinated_info_count_for_pairing,
                         differences_for_pairing) = compare_lists_from_json(expected_list_entry, actual_list_entry, f"{path}[{i}]")
                    else:
                        assert isinstance(expected_list_entry, dict) and isinstance(actual_list_entry, dict), f"expected_list_entry and actual_list_entry should both be dicts in this scenario, something went wrong with the generified code for iterating over complex entries in arrays; path: {path}"
                        (correct_info_count_for_pairing, hallucinated_info_count_for_pairing,
                         differences_for_pairing) = compare_dicts_from_json(expected_list_entry, actual_list_entry, f"{path}[{i}]")
                    if (correct_info_count_for_pairing == count_total_pieces_of_info_in_json(expected_list_entry)
                            and  hallucinated_info_count_for_pairing == 0 and len(differences_for_pairing) == 0):
                        matched_positions_in_expected.add(i)
                        matched_positions_in_actual.add(j)
                        total_num_correctly_extracted_pieces_of_info += count_total_pieces_of_info_in_json(expected_list_entry)
                        break
                    score = hallucinated_info_count_for_pairing - correct_info_count_for_pairing
                    ranking_of_imperfect_matches_for_expected[i].put(PrioritizedImperfectMatch(
                        score, j, correct_info_count_for_pairing, hallucinated_info_count_for_pairing, differences_for_pairing))
            
            unmatched_expected_entry_idxs = [i for i in range(len(expected_entries)) if i not in matched_positions_in_expected]
            num_actual_entries_that_exactly_matched = len(matched_positions_in_actual)
            num_not_perfectly_matched_actual_entries = len(actual_entries) - num_actual_entries_that_exactly_matched

            if len(unmatched_expected_entry_idxs) > 0 and num_not_perfectly_matched_actual_entries > 0:                
                for expected_entry_idx in unmatched_expected_entry_idxs:
                    imperfect_matches_queue = ranking_of_imperfect_matches_for_expected.pop(expected_entry_idx)
                    if imperfect_matches_queue.empty():
                        logger.warning(f"at path {path}, process for creating ranking_of_imperfect_matches_for_expected failed to add any entries to the queue for expected entry index {expected_entry_idx}")
                    
                    while not imperfect_matches_queue.empty():
                        next_best_match_info = imperfect_matches_queue.get()
                        if next_best_match_info.idx_in_actual_list in matched_positions_in_actual:
                            continue
                        
                        matched_positions_in_expected.add(expected_entry_idx)
                        matched_positions_in_actual.add(next_best_match_info.idx_in_actual_list)
                        total_num_correctly_extracted_pieces_of_info += next_best_match_info.correct_info_count
                        total_num_hallucinated_pieces_of_info += next_best_match_info.hallucinated_info_count
                        differences.extend(next_best_match_info.differences)
                        break
            
            num_actual_entries_at_least_partly_matched = len(matched_positions_in_actual)
            num_not_matched_actual_entries = len(actual_entries) - num_actual_entries_at_least_partly_matched
            
            if num_not_matched_actual_entries > 0:
                unmatched_actual_entries = [actual_entries[j] for j in range(len(actual_entries)) if j not in matched_positions_in_actual]
                total_num_hallucinated_pieces_of_info += count_total_pieces_of_info_in_json(unmatched_actual_entries)
                differences.append(f"Expected an array at {path} with {len(expected_list)} entries of type {json_type_nm}; got an array with {len(actual_entries)} entries of type {json_type_nm} where {num_actual_entries_that_exactly_matched} entries exactly matched an expected entry and {num_actual_entries_at_least_partly_matched-num_actual_entries_that_exactly_matched} entries only partially matched an expected entry, then had {len(unmatched_actual_entries)} extra entries: {json.dumps(unmatched_actual_entries)}")
    else:
        #TODO maybe at some point implement the sub-case where everything is a list or None on both sides, and the case where everything is a dict or None on both sides
        # before trying to implement the general case
        raise ValueError(f"not yet supporting schemas where a json array contains some primitive (string, number, boolean, null) entries and some complex (array or object) entries; cannot process array at path {path} in expected json")
    
    return total_num_correctly_extracted_pieces_of_info, total_num_hallucinated_pieces_of_info, differences


#it might be good to pass in the relevant subsection of the schema to distinguish between hallucinations in actual
# that are part of the schema and those that aren't, b/c our original plan for the 'extraction accuracy' metric treated
# those differently (technically, it only thought about the former, but in any case it would be ideal to allow metric
# calculations to weight those mistakes differently)
# This is doable but gets complicated, b/c if it hallucinate the inclusion of a value for an object-type field of the
#  top-level of the schema, we'd want to only count as within-schema hallucinations the pieces of info inside the actual
#  dict for that field that _are_ in that part of the schema (and this rule would apply recursively, including through
#  objects nested in arrays nested in objects)

def compare_dicts_from_json(expected: dict, actual: dict, path="") -> (int, int, list[str]):
    """
    
    :param expected:
    :param actual:
    :param path:
    :return: a tuple of (total number correctly extracted pieces of information from this path inward, total number of hallucinated pieces of information from this path inward, list of descriptions of differences)
    """
    assert isinstance(expected, dict) and isinstance(actual, dict), f"compare_dicts should only be called with dict values; path: {path}"
    
    total_num_correctly_extracted_pieces_of_info = 0
    total_num_hallucinated_pieces_of_info = 0
    differences = []

    for key, expected_value in expected.items():
        current_path = f"{path}.{key}" if path else key
        actual_value = actual.get(key)

        if actual_value is None:
            differences.append(f"Missing key '{current_path}' in actual output")
            continue

        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                differences.append(f"Type mismatch for key '{current_path}': Expected dict, got {type(actual_value)}")
            else:
                correct_info_count_in_child_objs, hallucination_count_in_child_objs, diffs_in_child_objs = \
                    compare_dicts_from_json(expected_value, actual_value, current_path)
                total_num_correctly_extracted_pieces_of_info += correct_info_count_in_child_objs
                total_num_hallucinated_pieces_of_info += hallucination_count_in_child_objs
                differences.extend(diffs_in_child_objs)
        elif isinstance(expected_value, list):
            if not isinstance(actual_value, list):
                differences.append(f"Type mismatch for key '{current_path}': Expected list, got {type(actual_value)}")
            else:
                correct_info_count_in_lists, hallucination_count_in_lists, diffs_in_lists = \
                    compare_lists_from_json(expected_value, actual_value, current_path)
                total_num_correctly_extracted_pieces_of_info += correct_info_count_in_lists
                total_num_hallucinated_pieces_of_info += hallucination_count_in_lists
                differences.extend(diffs_in_lists)
        else:
            if compare_values_from_json(expected_value, actual_value, current_path):
                total_num_correctly_extracted_pieces_of_info += 1
            else:
                differences.append(f"Value mismatch for key '{current_path}': Expected '{expected_value}', got '{actual_value}'")
    excess_keys = set(actual.keys()) - set(expected.keys())
    for key in excess_keys:
        differences.append(f"Excess key '{key}' in actual output at path {path}")
        total_num_hallucinated_pieces_of_info += count_total_pieces_of_info_in_json(actual[key])

    return total_num_correctly_extracted_pieces_of_info, total_num_hallucinated_pieces_of_info, differences


def evaluate_extraction(expected_object: dict[str, AnyJsonVal], actual_object: dict[str, AnyJsonVal]) -> (float, float, int, list[str]):
    correct_info_count, hallucinated_info_count, differences = compare_dicts_from_json(expected_object, actual_object)
    total_expected_info_count = count_total_pieces_of_info_in_json(expected_object)
    correct_fact_inclusion_rate = correct_info_count / total_expected_info_count
    #this is admittedly not what we originally described in the project plan, but in the process of implementation
    # I've come to think that the original idea was only half-baked
    # Also not beautifully principled in a mathematical sense, but I think it should behave in a reasonably intuitive/desirable way
    #  If expecting a lot of pieces of info, 1-3 hallucinations is less bad than 1-3 hallucinations when expecting only 1-3 pieces of info, so we scale the hallucination count by the expected info count
    #  If hallucination rate is close to 0, then the harmonic mean of its complement (a number near one) with the fraction of expected info that was correctly provided will yield a number that's only slightly less than the expected-fact-recall
    #  If hallucination rate is high (close to 1), the complement will be low (even close to 0) and the harmonic mean will be close to 0 even if correct inclusion rate was nearly 100%
    #  If the hallucinated pieces of information outnumber even the set of expected pieces of information, judge the extraction to be worthlessly unreliable even if most of the expected info was correctly extracted (because the odds of a given piece of information in the extraction result being correct would be even at best)
    #  If there were ~no hallucinations, that should be rewarded by increasing the quality score if the correct inclusion rate was further from 1 than the hallucination ratio was from 0
    hallucination_ratio = hallucinated_info_count / total_expected_info_count
    overall_extraction_quality = 0
    if hallucination_ratio < 1:
        hallucination_ratio_complement = 1-hallucination_ratio
        overall_extraction_quality = 2*correct_fact_inclusion_rate*hallucination_ratio_complement/(correct_fact_inclusion_rate+hallucination_ratio_complement)
    
    assert correct_fact_inclusion_rate < 1 or hallucination_ratio > 0 or len(differences) == 0, f"correct_fact_inclusion_rate was 100% and hallucination ratio was 0, but there were differences: {differences}"
    return overall_extraction_quality, correct_fact_inclusion_rate, hallucinated_info_count, differences


expected_json_path = "datasets/expected_validation_five_shot.json"
actual_json_path = "datasets/actual_validation_five_shot.json"

logger.info(f"Comparing {actual_json_path} to {expected_json_path}")


with open(expected_json_path, "r") as expected_file:
    expected_json = json.load(expected_file)

with open(actual_json_path, "r") as actual_file:
    actual_json = json.load(actual_file)

for i, (expected_obj, actual_obj) in enumerate(zip(expected_json, actual_json)):
    extraction_quality, correct_inclusion_rate, hallucination_count, diffs = evaluate_extraction(expected_obj, actual_obj)
    logger.info(f"Extraction quality for object {i}: {extraction_quality}")
    logger.info(f"Correct inclusion rate for object {i}: {correct_inclusion_rate}")
    logger.info(f"Hallucination count for object {i}: {hallucination_count}")
    for diff in diffs:
        logger.info(diff)
    logger.info("\n")
    
    