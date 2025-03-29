import csv
import sys

# List of compiler-related variables (CMake variables related to compilers)
compiler_variables = [
    "CMAKE_CXX_COMPILER", "CMAKE_C_COMPILER", "CMAKE_CXX_FLAGS", 
    "CMAKE_C_FLAGS", "CMAKE_C_COMPILER_ID", "CMAKE_CXX_COMPILER_ID", 
    "CMAKE_CXX_STANDARD", "CMAKE_C_STANDARD", "CMAKE_CXX_COMPILER_VERSION", 
    "CMAKE_C_COMPILER_VERSION", "CMAKE_CXX_FLAGS_DEBUG", "CMAKE_CXX_FLAGS_RELEASE","CMAKE_C_FLAGS_DEBUG","CMAKE_CXX_FLAGS_RELEASE","CMAKE_C_FLAGS_RELEASE","CMAKE_CXX_COMPILER_ID",
    "CMAKE_C_COMPILER_ID","CMAKE_CXX_COMPILER_VERSION","CMAKE_C_COMPILER_VERSION","CMAKE_CXX_COMPILER_LAUNCHER","CMAKE_C_COMPILER_LAUNCHER"
]

# Function to check if any compiler-related variable is present in the reachability string
def contains_compiler_variable(reachability_str):
    return any(var in reachability_str for var in compiler_variables)

# Read the target CSV file specified in the command line argument
def process_csv(file_name):
    total_deps = 0  # Total number of dependencies
    compiler_deps = 0  # Number of dependencies containing compiler-related variables
    reachability_non_empty = 0  # Number of rows where 'reachability' column is not empty

    # Open and read the CSV file
    with open(file_name, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        
        # Skip the header row if any
        next(reader, None)
        
        # Iterate through each row in the CSV
        for row in reader:
            num = row[0].strip()  # The first column is 'num'
            reachability = row[2].strip() if len(row) > 2 else ""  # The 'reachability' column
            
            if num:  # Only process rows where 'num' is not empty
                total_deps += 1
                if reachability:
                    reachability_non_empty += 1
                    if contains_compiler_variable(reachability):
                        compiler_deps += 1

    # Calculate the percentage of dependencies containing compiler-related variables
    compiler_percentage = (compiler_deps / total_deps * 100) if total_deps > 0 else 0
    # Calculate the percentage of dependencies with compiler-related variables among non-empty reachability rows
    compiler_percentage_non_empty = (compiler_deps / reachability_non_empty * 100) if reachability_non_empty > 0 else 0

    # Output the results
    print(f"Total dependencies: {total_deps}")
    print(f"Dependencies with compiler variables: {compiler_deps}")
    print(f"Percentage of total deps: {compiler_percentage:.2f}%")
    print(f"Percentage of deps with reachability not empty: {compiler_percentage_non_empty:.2f}%")

# Main function to execute the script
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)

    # Process the specified CSV file
    process_csv(sys.argv[1])
