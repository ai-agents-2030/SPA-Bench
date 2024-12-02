import os
import ast
import pandas as pd


def try_literal_eval(val):
    try:
        return ast.literal_eval(val)
    except (ValueError, SyntaxError):
        return val


def get_dataset(path):
    """Load a CSV into a pandas DataFrame, attempting to apply ast.literal_eval to columns.

    Parameters:
    - path (str): Path to the CSV file.

    Returns:
    - pd.DataFrame: The loaded DataFrame.
    """

    data = pd.read_csv(
        path, encoding="utf-8", header=0, index_col=0  # Assuming first row as header  # Assuming first column as index
    )

    # Apply ast.Literal_eval to all columns
    for col in data.columns:
        data[col] = data[col].apply(try_literal_eval)

    return data


if __name__ == "__main__":
    # Determine the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the paths relative to the script's directory
    benchmark_data_path = os.path.join(script_dir, "../../data/single-app-ENG.csv")

    # Load the datasets
    benchmark_data = get_dataset(benchmark_data_path)

    # Print the datasets
    print(benchmark_data[benchmark_data["task_language"] == "ENG"])
    print(type(benchmark_data.loc["clock_0", "key_component_final"]))
    print(benchmark_data.loc["clock_0", "key_component_final"])
