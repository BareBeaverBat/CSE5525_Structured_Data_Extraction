from logging_setup import create_logger

# Set up the logger
logger = create_logger(__name__)

def compare_values(expected, actual):
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.lower() == actual.lower()
    return expected == actual

def compare_lists(expected_list, actual_list, path):
    if len(expected_list) != len(actual_list):
        return 0.0, [f"Length mismatch for {path}: Expected {len(expected_list)}, got {len(actual_list)}"]
    
    correct_items = 0
    differences = []
    for i, (expected_item, actual_item) in enumerate(zip(expected_list, actual_list)):
        if isinstance(expected_item, dict) and isinstance(actual_item, dict):
            sub_diff, sub_accuracy, sub_total_accuracy = compare_dicts(expected_item, actual_item, f"{path}[{i}]")
            if sub_total_accuracy == 1.0:
                correct_items += 1
            else:
                differences.extend(sub_diff)
        elif not compare_values(expected_item, actual_item):
            differences.append(f"Mismatch in {path}[{i}]: Expected '{expected_item}', got '{actual_item}'")
        else:
            correct_items += 1
    
    accuracy = correct_items / len(expected_list)
    return accuracy, differences

def compare_dicts(expected, actual, path=""):
    differences = []
    accuracy_per_field = {}

    for key, expected_value in expected.items():
        current_path = f"{path}.{key}" if path else key
        actual_value = actual.get(key)

        if actual_value is None:
            differences.append(f"Missing key '{current_path}' in actual output")
            accuracy_per_field[current_path] = 0.0
            continue

        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                differences.append(f"Type mismatch for key '{current_path}': Expected dict, got {type(actual_value)}")
                accuracy_per_field[current_path] = 0.0
            else:
                sub_diff, sub_accuracy, sub_total_accuracy = compare_dicts(expected_value, actual_value, current_path)
                differences.extend(sub_diff)
                accuracy_per_field.update(sub_accuracy)
        elif isinstance(expected_value, list):
            if not isinstance(actual_value, list):
                differences.append(f"Type mismatch for key '{current_path}': Expected list, got {type(actual_value)}")
                accuracy_per_field[current_path] = 0.0
            else:
                list_accuracy, list_differences = compare_lists(expected_value, actual_value, current_path)
                accuracy_per_field[current_path] = list_accuracy
                if list_accuracy < 1.0:
                    differences.extend(list_differences)
        else:
            if compare_values(expected_value, actual_value):
                accuracy_per_field[current_path] = 1.0
            else:
                differences.append(f"Value mismatch for key '{current_path}': Expected '{expected_value}', got '{actual_value}'")
                accuracy_per_field[current_path] = 0.0

    total_accuracy = sum(accuracy_per_field.values()) / len(accuracy_per_field) if accuracy_per_field else 0.0
    return differences, accuracy_per_field, total_accuracy
