import matplotlib.pyplot as plt

def extract_values_from_log(log_file_path):
    extraction_qualities = []
    correct_inclusion_rates = []
    
    # Read the log file and extract "Extraction quality" and "Correct inclusion rate" values
    with open(log_file_path, 'r') as file:
        lines = file.readlines()
        
        for line in lines:
            if 'Extraction quality for object' in line:
                # Extract the extraction quality value
                extraction_quality = float(line.split(":")[-1].strip())
                extraction_qualities.append(extraction_quality)
            elif 'Correct inclusion rate for object' in line:
                # Extract the correct inclusion rate value
                inclusion_rate = float(line.split(":")[-1].strip())
                correct_inclusion_rates.append(inclusion_rate)
    
    return extraction_qualities, correct_inclusion_rates

def plot_pie_chart(values, title, output_file):
    # Prepare the data
    correct_value = sum(values) / len(values) * 100  # Mean value
    incorrect_value = 100 - correct_value
    
    
    # Create a pie chart
    labels = [ 'Correct','InCorrect']
    sizes = [correct_value, incorrect_value]
    colors = ['#4CAF50', '#FF6347']
    
    plt.figure(figsize=(7, 7))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.title(title)
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    
    # Save the pie chart as an image
    plt.savefig(output_file)
    plt.close()

def plot_accuracy_pie_chart(extraction_qualities, correct_inclusion_rates):
    # Plot the pie charts for extraction quality and inclusion rate
    plot_pie_chart(extraction_qualities, 'Extraction Quality Distribution', 'extraction_quality_pie_chart_5_shot.png')
    plot_pie_chart(correct_inclusion_rates, 'Correct Inclusion Rate Distribution', 'correct_inclusion_rate_pie_chart_5_shot.png')
    # plot_pie_chart(extraction_qualities, 'Extraction Quality Distribution', 'extraction_quality_pie_chart_zero_shot.png')
    # plot_pie_chart(correct_inclusion_rates, 'Correct Inclusion Rate Distribution', 'correct_inclusion_rate_pie_chart_zero_shot.png')

def print_extracted_values(extraction_qualities, correct_inclusion_rates):
    print("Extraction Quality for each object:")
    for i, value in enumerate(extraction_qualities, start=1):
        print(f"Object {i}: {value}")
    
    print("\nCorrect Inclusion Rate for each object:")
    for i, value in enumerate(correct_inclusion_rates, start=1):
        print(f"Object {i}: {value}")

# Example usage
# log_file_path = 'five_shot.log'  # 5 shot
log_file_path = 'five_shot.log'  # zero shot

extraction_qualities, correct_inclusion_rates = extract_values_from_log(log_file_path)
print_extracted_values(extraction_qualities, correct_inclusion_rates)
plot_accuracy_pie_chart(extraction_qualities, correct_inclusion_rates)

print("\nPie charts saved as extraction_quality_pie_chart.png and correct_inclusion_rate_pie_chart.png")
