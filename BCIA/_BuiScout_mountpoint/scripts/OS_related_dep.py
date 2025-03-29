import csv
import sys

# List of platform-related variables
platform_variables = [
    "ANDROID", "APPLE", "BORLAND", "BSD", "CMAKE_SYSTEM", "CMAKE_SYSTEM_NAME", 
    "CMAKE_SYSTEM_PROCESSOR", "CMAKE_SYSTEM_VERSION", "CYGWIN", "IOS", "LINUX", 
    "MINGW", "MSVC", "MSVC_IDE", "MSVC_TOOLSET_VERSION", "MSVC_VERSION", 
    "MSYS", "UNIX", "WASI", "WIN32", "WINCE", "WINDOWS_PHONE", 
    "WINDOWS_STORE", "XCODE", "XCODE_VERSION"
]

# Function to check if any platform-related variable is present in the reachability string
def contains_platform_variable(reachability_str):
    return any(var in reachability_str for var in platform_variables)

# Read the target CSV file specified in the command line argument
def process_csv(file_name):
    total_deps = 0  # Total number of dependencies
    platform_deps = 0  # Number of dependencies containing platform-related variables
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
                    if contains_platform_variable(reachability):
                        platform_deps += 1

    # Calculate the percentage of dependencies containing platform variables
    platform_percentage = (platform_deps / total_deps * 100) if total_deps > 0 else 0
    # Calculate the percentage of dependencies with platform-related variables among non-empty reachability rows
    platform_percentage_non_empty = (platform_deps / reachability_non_empty * 100) if reachability_non_empty > 0 else 0

    # Output the results
    print(f"Total dependencies: {total_deps}")
    print(f"Dependencies with platform variables: {platform_deps}")
    print(f"Percentage of total deps: {platform_percentage:.2f}%")
    print(f"Percentage of deps with reachability not empty: {platform_percentage_non_empty:.2f}%")

# Main function to execute the script
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)

    # Process the specified CSV file
    process_csv(sys.argv[1])
