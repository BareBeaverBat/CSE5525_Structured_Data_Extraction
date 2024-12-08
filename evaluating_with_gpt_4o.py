import json
import os
from json_obj_comparison import evaluate_extraction


def load_json(file_path):
    """Load a JSON file."""
    with open(file_path) as f:
        return json.load(f)


def calculate_averages(total_quality, total_inclusion_rate, total_hallucinations, count):
    """Calculate average metrics."""
    if count == 0:
        return 0, 0, 0
    return (total_quality / count, total_inclusion_rate / count, total_hallucinations / count)


def evaluate_all_samples(validation_set, gpt_output):
    """Evaluate all samples and return results and aggregated metrics."""
    evaluation_results = []
    aggregated_metrics = {
        "full": {"quality": 0, "inclusion_rate": 0, "hallucinations": 0},
        "claude": {"quality": 0, "inclusion_rate": 0, "hallucinations": 0, "count": 0},
        "gemini": {"quality": 0, "inclusion_rate": 0, "hallucinations": 0, "count": 0},
        "scenarios": {}
    }

    for i in range(len(validation_set)):
        overall_quality, inclusion_rate, hallucinations, differences = evaluate_extraction(
            gpt_output[i], validation_set[i]
        )

        # Record results
        evaluation_results.append({
            "scenario_id": validation_set[i]["scenario_id"],
            "scenario_name": validation_set[i]["scenario_name"],
            "was_claude_vs_gemini_generated": validation_set[i]["was_claude_vs_gemini_generated"],
            "overall_extraction_quality": overall_quality,
            "correct_fact_inclusion_rate": inclusion_rate,
            "hallucinated_info_count": hallucinations,
            "differences": differences,
        })

        # Update aggregated metrics
        aggregated_metrics["full"]["quality"] += overall_quality
        aggregated_metrics["full"]["inclusion_rate"] += inclusion_rate
        aggregated_metrics["full"]["hallucinations"] += hallucinations

        generator_type = "claude" if validation_set[i]["was_claude_vs_gemini_generated"] else "gemini"
        aggregated_metrics[generator_type]["quality"] += overall_quality
        aggregated_metrics[generator_type]["inclusion_rate"] += inclusion_rate
        aggregated_metrics[generator_type]["hallucinations"] += hallucinations
        aggregated_metrics[generator_type]["count"] += 1

        scenario_id = validation_set[i]["scenario_id"]
        if scenario_id not in aggregated_metrics["scenarios"]:
            aggregated_metrics["scenarios"][scenario_id] = {
                "quality": 0,
                "inclusion_rate": 0,
                "hallucinations": 0,
                "count": 0
            }

        scenario_metrics = aggregated_metrics["scenarios"][scenario_id]
        scenario_metrics["quality"] += overall_quality
        scenario_metrics["inclusion_rate"] += inclusion_rate
        scenario_metrics["hallucinations"] += hallucinations
        scenario_metrics["count"] += 1

    return evaluation_results, aggregated_metrics


def finalize_scenario_averages(scenarios):
    """Calculate average metrics for each scenario."""
    for scenario_id, metrics in scenarios.items():
        metrics["quality"], metrics["inclusion_rate"], metrics["hallucinations"] = calculate_averages(
            metrics["quality"], metrics["inclusion_rate"], metrics["hallucinations"], metrics["count"]
        )


def evaluate(validation_set_file, zero_shot_gpt_output_file):
    """Main evaluation function."""
    # Load datasets
    validation_set = load_json(validation_set_file)
    zero_shot_gpt_output = load_json(zero_shot_gpt_output_file)

    assert len(validation_set) == len(zero_shot_gpt_output), \
        "Validation set and GPT output must have the same number of samples."

    print(f"Number of samples in validation set: {len(validation_set)}")
    print(f"Number of samples in zero-shot GPT output: {len(zero_shot_gpt_output)}")

    # Evaluate all samples
    evaluation_results, aggregated_metrics = evaluate_all_samples(validation_set, zero_shot_gpt_output)

    # Finalize scenario averages
    finalize_scenario_averages(aggregated_metrics["scenarios"])

    # Calculate overall averages
    full_metrics = aggregated_metrics["full"]
    full_averages = calculate_averages(
        full_metrics["quality"], full_metrics["inclusion_rate"], full_metrics["hallucinations"], len(validation_set)
    )

    claude_averages = calculate_averages(
        aggregated_metrics["claude"]["quality"],
        aggregated_metrics["claude"]["inclusion_rate"],
        aggregated_metrics["claude"]["hallucinations"],
        aggregated_metrics["claude"]["count"]
    )

    gemini_averages = calculate_averages(
        aggregated_metrics["gemini"]["quality"],
        aggregated_metrics["gemini"]["inclusion_rate"],
        aggregated_metrics["gemini"]["hallucinations"],
        aggregated_metrics["gemini"]["count"]
    )

    # Output aggregated results
    return {
        "evaluation_results": evaluation_results,
        "full_averages": full_averages,
        "claude_averages": claude_averages,
        "gemini_averages": gemini_averages,
        "averaged_scenario_evaluations": aggregated_metrics["scenarios"]
    }


validation_set_file = "split_data/validation_set.json"
zero_shot_gpt_output_file = "gpt_outputs/output_gpt_zero_shot.json"

results = evaluate(validation_set_file, zero_shot_gpt_output_file)

# Print results
print("Full averages:")
print("Extraction Quality:", results["full_averages"][0])
print("Inclusion rate:", results["full_averages"][1])
print("Hallucinations:", results["full_averages"][2])

print("\nClaude averages:")
print("Extraction Quality:", results["claude_averages"][0])
print("Inclusion rate:", results["claude_averages"][1])
print("Hallucinations:", results["claude_averages"][2])

print("\nGemini averages:")
print("Extraction Quality:", results["gemini_averages"][0])
print("Inclusion rate:", results["gemini_averages"][1])
print("Hallucinations:", results["gemini_averages"][2])

print("\nScenario averages:")
for scenario_id, metrics in results["averaged_scenario_evaluations"].items():
    print(f"Scenario {scenario_id}:")
    print("Extraction Quality:", metrics["quality"])
    print("Inclusion rate:", metrics["inclusion_rate"])
    print("Hallucinations:", metrics["hallucinations"])
    print("Count:", metrics["count"])

