import numpy as np
import itertools
import random
import colorsys
import os
import re

def gamma_correct(R,G,B):

    # Apply gamma correction
    r_corrected = (R/255) ** (1.0 / b_values['R'])
    g_corrected = (G/255) ** (1.0 / b_values['G'])
    b_corrected = (B/255) ** (1.0 / b_values['B'])

    return(round(r_corrected*255), round(g_corrected*255), round(b_corrected*255))


# MODIFY THIS FUNCTION
def generate_trials(reference_color_rgb, comparison_colors_rgb, background_colors_rgb, fixed_background_rgb,
                    num_trials, output_file="colors.txt", condition_file="condition.txt", base_folder="."):

    trials_gamma = []
    trials_linear = []

    order_number = 1

    # Prepare rgb combinations for pairing
    comparison_pairs_rgb = list(zip(comparison_colors_rgb, comparison_colors_rgb))
    all_combinations_rgb = list(itertools.product(background_colors_rgb, comparison_pairs_rgb))

    for trial_number in range(num_trials):
        for bg2_rgb, (comp_rgb, _) in all_combinations_rgb:
            # Always use the first reference color and first fixed background
            ref_rgb = reference_color_rgb[0]
            fixed_bg_rgb = fixed_background_rgb[0]

            # Randomize reference/comparison square positions
            if trial_number < (num_trials/2):
                rgb_sq1, rgb_sq2 = ref_rgb, comp_rgb
                rgb_bg1, rgb_bg2 = fixed_bg_rgb, bg2_rgb
                expected_response = 1 if ref_rgb[0] == comp_rgb[0] else 2
                ref_pos = 1
            else:
                rgb_sq1, rgb_sq2 = comp_rgb, ref_rgb
                rgb_bg1, rgb_bg2 = bg2_rgb, fixed_bg_rgb
                expected_response = 1 if ref_rgb[0] == comp_rgb[0] else 2
                ref_pos = 2

            # Convert to RGB
            sq1_gamma = gamma_correct(*rgb_sq1)
            sq2_gamma = gamma_correct(*rgb_sq2)
            bg1_gamma = gamma_correct(*rgb_bg1)
            bg2_gamma = gamma_correct(*rgb_bg2)

            sq1_linear = rgb_sq1
            sq2_linear = rgb_sq2
            bg1_linear = rgb_bg1
            bg2_linear = rgb_bg2

            trial_gamma = (*bg1_gamma, *bg2_gamma, *sq1_gamma, *sq2_gamma, order_number, ref_pos, expected_response)
            trial_linear = (*bg1_linear, *bg2_linear, *sq1_linear, *sq2_linear, order_number, ref_pos, expected_response)

            trials_gamma.append(trial_gamma)
            trials_linear.append(trial_linear)

            order_number += 1

    # Shuffle both lists using the same permutation
    permutation = list(range(len(trials_gamma)))
    random.shuffle(permutation)
    trials_gamma = [trials_gamma[i] for i in permutation]
    trials_linear = [trials_linear[i] for i in permutation]

    os.makedirs(base_folder, exist_ok=True)

    # Save gamma-corrected file
    gamma_path = os.path.join(base_folder, output_file.replace(".txt", "_gamma_corrected.txt"))
    with open(gamma_path, "w") as f:
        for trial in trials_gamma:
            f.write(",".join(f"{x:d}" for x in trial) + "\n")

    # Save non-gamma-corrected (linear) file
    linear_path = os.path.join(base_folder, output_file)
    with open(linear_path, "w") as f:
        for trial in trials_linear:
            f.write(",".join(f"{x:d}" for x in trial) + "\n")

    # Save condition parameters
    condition_path = os.path.join(base_folder, condition_file)
    with open(condition_path, "w") as f:
        f.write("Parameters used to generate the output file:\n")
        f.write(f"Reference Color rgb: {reference_color_rgb}\n")
        f.write(f"Comparison Colors rgb: {comparison_colors_rgb}\n")
        f.write(f"Background Colors rgb: {background_colors_rgb}\n")
        f.write(f"Fixed Background rgb: {fixed_background_rgb}\n")
        f.write(f"Number of Repetitions: {num_trials}\n")
        f.write(f"Output File (Gamma Corrected): {gamma_path}\n")
        f.write(f"Output File (Linear RGB): {linear_path}\n")
        f.write(f"Condition File: {condition_file}\n")
        f.write(f"Base Folder: {base_folder}\n")
        # f.write(f"Gamma Correction Exponent File: {input_exponent_file}\n")

    print(f"Generated {len(trials_gamma)} gamma-corrected trials and saved to {gamma_path}")
    print(f"Generated {len(trials_linear)} linear (non-gamma) trials and saved to {linear_path}")
    print(f"Condition parameters saved to {condition_path}")

def generate_achromatic_tuples(values):
    """
    Generates a list of rgb tuples from a list of integer values.
    
    Parameters:
        values (list): A list of integers in range [0, 255] representing the grayscale values
    
    Returns:
        list: A list of tuples in the format [(R, G, B)] where R, G, B are all equal
              to the provided values (clamped to [0, 255])
    """
    tuples = []
    for val in values:
        # Clamp value to valid range
        clamped = max(0, min(255, val))
        tuples.append((clamped, clamped, clamped))
    
    return tuples

# Example usage:
# my_values = [50, 100, 128, 150, 200]
# result = generate_achromatic_tuples_from_values(my_values)
# print(result)  # [(50, 50, 50), (100, 100, 100), (128, 128, 128), (150, 150, 150), (200, 200, 200)]

def generate_conditions_for_subject(subject_name, base_folder, num_repetitions):
    """
    Generates experiment conditions for a subject and saves the files in the specified folder structure.
    
    Parameters:
        subject_name (str): Name of the subject.
        base_folder (str): Base folder where the data will be saved.
    """

    # Define the five conditions
    conditions = {
        "condition_demo": {
            "reference_color_rgb": generate_achromatic_tuples([60]),
            "comparison_colors_rgb": generate_achromatic_tuples([40, 45, 52, 60, 69, 79, 91]),
            "background_colors_rgb": generate_achromatic_tuples([0]),
            "fixed_background_rgb": generate_achromatic_tuples([0]),
            "num_trials": 12,
        },
        "condition_0": {
            "reference_color_rgb": generate_achromatic_tuples([60]),
            "comparison_colors_rgb": generate_achromatic_tuples([40, 45, 52, 60, 69, 79, 91]),
            "background_colors_rgb": generate_achromatic_tuples([0]),
            "fixed_background_rgb": generate_achromatic_tuples([0]),
            "num_trials": 48,
        },
        "condition_1": {
            "reference_color_rgb": generate_achromatic_tuples([30]),
            "comparison_colors_rgb": generate_achromatic_tuples([20, 23, 26, 30, 34, 40, 45]),
            "background_colors_rgb": generate_achromatic_tuples([0]),
            "fixed_background_rgb": generate_achromatic_tuples([0]),
            "num_trials": 48,
        },
        "condition_2": {
            "reference_color_rgb": generate_achromatic_tuples([60]),
            "comparison_colors_rgb": generate_achromatic_tuples([40, 45, 52, 60, 69, 79, 91]),
            "background_colors_rgb": generate_achromatic_tuples([0]),
            "fixed_background_rgb": generate_achromatic_tuples([0]),
            "num_trials": 48,
        },
        "condition_3": {
            "reference_color_rgb": generate_achromatic_tuples([90]),
            "comparison_colors_rgb": generate_achromatic_tuples([59, 68, 78, 90, 103, 119, 136]),
            "background_colors_rgb": generate_achromatic_tuples([0]),
            "fixed_background_rgb": generate_achromatic_tuples([0]),
            "num_trials": 48,
        },
    }

    # Iterate over conditions and repetitions
    for condition_name, params in conditions.items():
        for repetition in range(1, num_repetitions + 1):
            # Define the output folder
            output_folder = os.path.join(base_folder, "Data", subject_name, condition_name, f"Repetition_{repetition}")
            os.makedirs(output_folder, exist_ok=True)

            # Define the output file and condition file names
            output_file = f"trials_{condition_name}_rep_{repetition}.txt"
            condition_file = f"conditions_{condition_name}_rep_{repetition}.txt"

            # Generate trials and save files
            generate_trials(
                reference_color_rgb=params["reference_color_rgb"],
                comparison_colors_rgb=params["comparison_colors_rgb"],
                background_colors_rgb=params["background_colors_rgb"],
                fixed_background_rgb=params["fixed_background_rgb"],
                num_trials=params["num_trials"],
                output_file=output_file,
                condition_file=condition_file,
                base_folder=output_folder,
            )

            print(f"Generated {condition_name}, Repetition {repetition} for subject {subject_name} in {output_folder}")

if __name__ == "__main__":
    import argparse

    # Paths are resolved from the command line or the environment so that this
    # script runs wherever the repository is checked out:
    #
    #   --base-folder / $ORDER_EFFECT_BASE   where Data/ is written
    #                                        (default: this script's folder)
    #   --gamma-file  / $ORDER_EFFECT_GAMMA  display calibration exponents
    #
    # The gamma file is the output of the monitor calibration and is specific
    # to the display in use; it is not included in this repository. It is a
    # plain text file with one line per channel, for example:
    #
    #     R gamma (γ): 2.1234
    #     G gamma (γ): 2.2345
    #     B gamma (γ): 2.3456
    #
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Generate the trial lists for one subject.")
    parser.add_argument("--subject", default=None,
                        help="subject nickname (prompted for if omitted)")
    parser.add_argument("--base-folder",
                        default=os.environ.get("ORDER_EFFECT_BASE", here),
                        help="folder beneath which Data/ is written")
    parser.add_argument("--gamma-file",
                        default=os.environ.get("ORDER_EFFECT_GAMMA"),
                        help="display calibration file holding the per-channel "
                             "gamma exponents")
    parser.add_argument("--repetitions", type=int, default=1,
                        help="number of repetitions per condition")
    args = parser.parse_args()

    subject_name = args.subject or input("Enter subject name: ")

    if not args.gamma_file:
        parser.error(
            "no display calibration file given. Pass --gamma-file or set "
            "$ORDER_EFFECT_GAMMA. See the comment above for its format.")
    if not os.path.isfile(args.gamma_file):
        parser.error(f"calibration file not found: {args.gamma_file}")

    input_exponent_file = args.gamma_file
    print(f"Gamma exponents read from {input_exponent_file}")

    # Read exponent values (first part of original read_b_values function)
    b_values = {}
    with open(input_exponent_file, 'r') as file:
        for line in file:
            match = re.match(r'([RGB]) gamma \(γ\): ([\d.]+)', line)
            if match:
                channel = match.group(1)
                b_value = float(match.group(2))
                b_values[channel] = b_value

    if set(b_values) != {"R", "G", "B"}:
        parser.error(
            f"calibration file did not yield R, G and B exponents; got "
            f"{sorted(b_values)}")

    num_repetitions = args.repetitions
    base_folder = args.base_folder
    print(f"Base folder: {base_folder}")

    generate_conditions_for_subject(subject_name, base_folder = base_folder, num_repetitions=num_repetitions)