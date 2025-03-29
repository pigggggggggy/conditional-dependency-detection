import csv
import sys

# List of building process related variables
variables_for_languages = [
    "CMAKE_C_COMPILE_FEATURES", "CMAKE_C_EXTENSIONS", "CMAKE_C_STANDARD", "CMAKE_C_STANDARD_REQUIRED",
    "CMAKE_CUDA_ARCHITECTURES", "CMAKE_CUDA_COMPILE_FEATURES", "CMAKE_CUDA_EXTENSIONS", "CMAKE_CUDA_HOST_COMPILER",
    "CMAKE_CUDA_STANDARD", "CMAKE_CUDA_STANDARD_REQUIRED", "CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES",
    "CMAKE_CXX_COMPILE_FEATURES", "CMAKE_CXX_COMPILER_IMPORT_STD", "CMAKE_CXX_EXTENSIONS", "CMAKE_CXX_STANDARD",
    "CMAKE_CXX_STANDARD_REQUIRED", "CMAKE_Fortran_MODDIR_DEFAULT", "CMAKE_Fortran_MODDIR_FLAG", "CMAKE_Fortran_MODOUT_FLAG",
    "CMAKE_HIP_ARCHITECTURES", "CMAKE_HIP_COMPILE_FEATURES", "CMAKE_HIP_EXTENSIONS", "CMAKE_HIP_PLATFORM",
    "CMAKE_HIP_STANDARD", "CMAKE_HIP_STANDARD_REQUIRED", "CMAKE_ISPC_HEADER_DIRECTORY", "CMAKE_ISPC_HEADER_SUFFIX",
    "CMAKE_ISPC_INSTRUCTION_SETS", "CMAKE_<LANG>_ANDROID_TOOLCHAIN_MACHINE", "CMAKE_<LANG>_ANDROID_TOOLCHAIN_PREFIX",
    "CMAKE_<LANG>_ANDROID_TOOLCHAIN_SUFFIX", "CMAKE_<LANG>_ARCHIVE_APPEND", "CMAKE_<LANG>_ARCHIVE_CREATE", 
    "CMAKE_<LANG>_ARCHIVE_FINISH", "CMAKE_<LANG>_BYTE_ORDER", "CMAKE_<LANG>_COMPILE_OBJECT", "CMAKE_<LANG>_COMPILER", 
    "CMAKE_<LANG>_COMPILER_EXTERNAL_TOOLCHAIN", "CMAKE_<LANG>_COMPILER_ID", "CMAKE_<LANG>_COMPILER_LOADED", 
    "CMAKE_<LANG>_COMPILER_PREDEFINES_COMMAND", "CMAKE_<LANG>_COMPILER_TARGET", "CMAKE_<LANG>_COMPILER_VERSION", 
    "CMAKE_<LANG>_CREATE_SHARED_LIBRARY", "CMAKE_<LANG>_CREATE_SHARED_LIBRARY_ARCHIVE", "CMAKE_<LANG>_CREATE_SHARED_MODULE",
    "CMAKE_<LANG>_CREATE_STATIC_LIBRARY", "CMAKE_<LANG>_EXTENSIONS", "CMAKE_<LANG>_EXTENSIONS_DEFAULT", "CMAKE_<LANG>_FLAGS",
    "CMAKE_<LANG>_FLAGS_<CONFIG>", "CMAKE_<LANG>_FLAGS_<CONFIG>_INIT", "CMAKE_<LANG>_FLAGS_DEBUG", 
    "CMAKE_<LANG>_FLAGS_DEBUG_INIT", "CMAKE_<LANG>_FLAGS_INIT", "CMAKE_<LANG>_FLAGS_MINSIZEREL", 
    "CMAKE_<LANG>_FLAGS_MINSIZEREL_INIT", "CMAKE_<LANG>_FLAGS_RELEASE", "CMAKE_<LANG>_FLAGS_RELEASE_INIT", 
    "CMAKE_<LANG>_FLAGS_RELWITHDEBINFO", "CMAKE_<LANG>_FLAGS_RELWITHDEBINFO_INIT", "CMAKE_<LANG>_HOST_COMPILER", 
    "CMAKE_<LANG>_HOST_COMPILER_ID", "CMAKE_<LANG>_HOST_COMPILER_VERSION", "CMAKE_<LANG>_IGNORE_EXTENSIONS", 
    "CMAKE_<LANG>_IMPLICIT_INCLUDE_DIRECTORIES", "CMAKE_<LANG>_IMPLICIT_LINK_DIRECTORIES", 
    "CMAKE_<LANG>_IMPLICIT_LINK_FRAMEWORK_DIRECTORIES", "CMAKE_<LANG>_IMPLICIT_LINK_LIBRARIES", 
    "CMAKE_<LANG>_LIBRARY_ARCHITECTURE", "CMAKE_<LANG>_LINK_EXECUTABLE", "CMAKE_<LANG>_LINKER_WRAPPER_FLAG", 
    "CMAKE_<LANG>_LINKER_WRAPPER_FLAG_SEP", "CMAKE_<LANG>_OUTPUT_EXTENSION", "CMAKE_<LANG>_SIMULATE_ID", 
    "CMAKE_<LANG>_SIMULATE_VERSION", "CMAKE_<LANG>_SIZEOF_DATA_PTR", "CMAKE_<LANG>_SOURCE_FILE_EXTENSIONS", 
    "CMAKE_<LANG>_STANDARD", "CMAKE_<LANG>_STANDARD_DEFAULT", "CMAKE_<LANG>_STANDARD_INCLUDE_DIRECTORIES", 
    "CMAKE_<LANG>_STANDARD_LATEST", "CMAKE_<LANG>_STANDARD_LIBRARIES", "CMAKE_<LANG>_STANDARD_LINK_DIRECTORIES", 
    "CMAKE_<LANG>_STANDARD_REQUIRED", "CMAKE_OBJC_EXTENSIONS", "CMAKE_OBJC_STANDARD", 
    "CMAKE_OBJC_STANDARD_REQUIRED", "CMAKE_OBJCXX_EXTENSIONS", "CMAKE_OBJCXX_STANDARD", 
    "CMAKE_OBJCXX_STANDARD_REQUIRED", "CMAKE_Swift_LANGUAGE_VERSION", "CMAKE_USER_MAKE_RULES_OVERRIDE_<LANG>"
]



# Function to check if any building process-related variable is present in the reachability string
def contains_building_process_related_variable(reachability_str):
    return any(var in reachability_str for var in variables_for_languages)

# Read the target CSV file specified in the command line argument
def process_csv(file_name):
    total_deps = 0  # Total number of dependencies
    building_process_related_deps = 0  # Number of dependencies containing building process-related variables
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
                    if contains_building_process_related_variable(reachability):
                        building_process_related_deps += 1

    # Calculate the percentage of dependencies containing building process-related variables
    building_process_related_percentage = (building_process_related_deps / total_deps * 100) if total_deps > 0 else 0
    # Calculate the percentage of dependencies with building process-related variables among non-empty reachability rows
    building_process_related_percentage_non_empty = (building_process_related_deps / reachability_non_empty * 100) if reachability_non_empty > 0 else 0

    # Output the results
    print(f"Total dependencies: {total_deps}")
    print(f"Dependencies with language-related variables: {building_process_related_deps}")
    print(f"Percentage of total deps: {building_process_related_percentage:.2f}%")
    print(f"Percentage of deps with reachability not empty: {building_process_related_percentage_non_empty:.2f}%")

# Main function to execute the script
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)

    # Process the specified CSV file
    process_csv(sys.argv[1])
