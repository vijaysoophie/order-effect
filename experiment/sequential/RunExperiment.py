import argparse
import os
import random
import subprocess
import sys

# Configuration.
#
# The base folder is the directory that holds `Utilities/` (with the compiled
# application), `Condition/` and `Data/`. It is resolved in this order:
#
#   1. the --base-folder command-line option
#   2. the ORDER_EFFECT_BASE environment variable
#   3. the directory containing this script
#
# so the script runs wherever the repository is checked out, with no editing.
DEFAULT_BASE_FOLDER = os.environ.get(
    "ORDER_EFFECT_BASE", os.path.dirname(os.path.abspath(__file__)))
NUM_REPETITIONS = 1  # Number of repetitions
CONDITIONS = ["condition_demo","condition_0", "condition_1", "condition_2", "condition_3"]  # List of conditions
PROJECT_APP_NAME = "Experiment1.app"  # Name of the project app

def check_condition_files(base_folder, conditions):
    """
    Checks if the input files for all conditions exist.
    """
    missing_files = []
    for condition in conditions:
        input_file_path = os.path.join(base_folder, "Condition", condition, f"{condition}.txt")
        if not os.path.exists(input_file_path):
            missing_files.append(input_file_path)
    
    if missing_files:
        print("Error: The following condition files are missing:")
        for file in missing_files:
            print(file)
        sys.exit(1)

def generate_sequence(base_folder, subject_name, conditions):
    """
    Generates a random sequence of conditions and saves it to a file.
    """
    # Separate condition_0 and randomize the rest
    condition_demo = [conditions[0]]
    condition_0 = [conditions[1]]
    other_conditions = conditions[2:]
    random.shuffle(other_conditions)
    
    # Combine with condition_0 first
    shuffled_conditions = condition_demo + condition_0 + other_conditions

    # Create the subject folder if it doesn't exist
    subject_folder = os.path.join(base_folder, "Data", subject_name)
    os.makedirs(subject_folder, exist_ok=True)

    # Define the sequence file path
    sequence_file_path = os.path.join(subject_folder, "sequence.txt")

    # Save the sequence to the file
    with open(sequence_file_path, "w") as file:
        file.write("\n".join(shuffled_conditions))

    print(f"Sequence generated and saved to {sequence_file_path}")
    return shuffled_conditions

def run_condition(base_folder, subject_name, condition_name, repetition):
    """
    Runs the experiment for a specific condition and repetition.
    """
    # Define paths
    app_path = os.path.join(base_folder, "Utilities", PROJECT_APP_NAME, "Contents", "MacOS", "My project")
    input_file_path = os.path.join(base_folder, "Data", subject_name, condition_name, f"Repetition_{repetition}",f"trials_{condition_name}_rep_{repetition}_gamma_corrected.txt")
    output_folder = os.path.join(base_folder, "Data", subject_name, condition_name, f"Repetition_{repetition}")
    output_file_path = os.path.join(output_folder, f"{subject_name}_{condition_name}_Repetition_{repetition}.txt")
    record_file_path = os.path.join(base_folder, "Data", subject_name, condition_name, f"Repetition_{repetition}",f"trials_{condition_name}_rep_{repetition}.txt")

    # Create the output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Define the command
    command = [
        app_path,
        "-colorInput", input_file_path,
        "-input", record_file_path,
        "-output", output_file_path]

    # Run the command
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print(f"Command executed successfully for {condition_name}, Repetition {repetition}!")
        print("Output:", result.stdout)  # Print the output of the command (if any)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while running the command for {condition_name}, Repetition {repetition}:")
        print("Error code:", e.returncode)
        print("Error output:", e.stderr)

def load_progress(subject_folder):
    """
    Loads the progress from the progress file.
    """
    progress_file_path = os.path.join(subject_folder, "progress.txt")
    if os.path.exists(progress_file_path):
        with open(progress_file_path, "r") as file:
            lines = file.read().splitlines()
            if len(lines) == 2:
                return int(lines[0]), int(lines[1])  # current_condition_index, current_repetition
    return 0, 0  # Default to starting from the first condition and first repetition

def save_progress(subject_folder, current_condition_index, current_repetition):
    """
    Saves the progress to the progress file.
    """
    progress_file_path = os.path.join(subject_folder, "progress.txt")
    with open(progress_file_path, "w") as file:
        file.write(f"{current_condition_index}\n{current_repetition}")

def main(base_folder, subject_name, num_repetitions, conditions):
    """
    Main function to manage the experiment.
    """
    # Check if condition files exist
    # check_condition_files(base_folder, conditions)

    # Define the subject folder and sequence file path
    subject_folder = os.path.join(base_folder, "Data", subject_name)
    # Check if the subject folder exists
    if not os.path.exists(subject_folder):
        print(f"Subject folder '{subject_folder}' does not exist. Exiting the program. Check if the name is correct or generate conditions.")
        sys.exit(1)  # Exit the program if the subject folder doesn't exist
    
    sequence_file_path = os.path.join(subject_folder, "sequence.txt")

    # Check if the subject folder exists
    if not os.path.exists(subject_folder):
        print(f"Subject folder '{subject_folder}' does not exist. Creating folder and generating sequence...")
        conditions = generate_sequence(base_folder, subject_name, conditions)
    else:
        # Check if the sequence file exists
        if not os.path.exists(sequence_file_path):
            print(f"Sequence file '{sequence_file_path}' does not exist. Generating sequence...")
            conditions = generate_sequence(base_folder, subject_name, conditions)
        else:
            # Read the sequence from the file
            with open(sequence_file_path, "r") as file:
                conditions = file.read().splitlines()

    # Load progress
    current_condition_index, current_repetition = load_progress(subject_folder)

    # Check if all conditions and repetitions are completed
    if current_condition_index >= len(conditions) and current_repetition >= num_repetitions:
        print("All conditions and repetitions have been completed for this subject.")
        return

    # Run the next condition
    condition = conditions[current_condition_index]
    repetition = current_repetition + 1

    print(f"Running {condition}, Repetition {repetition}...")
    run_condition(base_folder, subject_name, condition, repetition)

    # Update progress
    if repetition >= num_repetitions:
        current_condition_index += 1
        current_repetition = 0
    else:
        current_repetition += 1

    save_progress(subject_folder, current_condition_index, current_repetition)

    print(f"Progress saved. Next condition: {conditions[current_condition_index] if current_condition_index < len(conditions) else 'None'}, Next repetition: {current_repetition + 1}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run one condition of the experiment for a subject.")
    parser.add_argument("subject_name",
                        help="nickname of the subject to run")
    parser.add_argument("--base-folder", default=DEFAULT_BASE_FOLDER,
                        help="folder containing Utilities/, Condition/ and "
                             "Data/ (default: the folder holding this script, "
                             "or $ORDER_EFFECT_BASE)")
    args = parser.parse_args()

    print(f"Base folder: {args.base_folder}")
    main(args.base_folder, args.subject_name, NUM_REPETITIONS, CONDITIONS)