import csv
import sys

# List of information-related variables
information_related_variables = [
    "CMAKE_AR", "CMAKE_ARGC", "CMAKE_ARGV0", "CMAKE_BINARY_DIR", "CMAKE_BUILD_TOOL", 
    "CMAKE_CACHE_MAJOR_VERSION", "CMAKE_CACHE_MINOR_VERSION", "CMAKE_CACHE_PATCH_VERSION", 
    "CMAKE_CACHEFILE_DIR", "CMAKE_CFG_INTDIR", "CMAKE_COMMAND", "CMAKE_CPACK_COMMAND", 
    "CMAKE_CROSSCOMPILING", "CMAKE_CROSSCOMPILING_EMULATOR", "CMAKE_CTEST_COMMAND", 
    "CMAKE_CURRENT_BINARY_DIR", "CMAKE_CURRENT_FUNCTION", "CMAKE_CURRENT_FUNCTION_LIST_DIR", 
    "CMAKE_CURRENT_FUNCTION_LIST_FILE", "CMAKE_CURRENT_FUNCTION_LIST_LINE", "CMAKE_CURRENT_LIST_DIR", 
    "CMAKE_CURRENT_LIST_FILE", "CMAKE_CURRENT_LIST_LINE", "CMAKE_CURRENT_SOURCE_DIR", 
    "CMAKE_DEBUG_TARGET_PROPERTIES", "CMAKE_DIRECTORY_LABELS", "CMAKE_DL_LIBS", "CMAKE_DOTNET_SDK", 
    "CMAKE_DOTNET_TARGET_FRAMEWORK", "CMAKE_DOTNET_TARGET_FRAMEWORK_VERSION", "CMAKE_EDIT_COMMAND", 
    "CMAKE_EXECUTABLE_SUFFIX", "CMAKE_EXECUTABLE_SUFFIX_<LANG>", "CMAKE_EXTRA_SHARED_LIBRARY_SUFFIXES", 
    "CMAKE_FIND_DEBUG_MODE", "CMAKE_FIND_PACKAGE_NAME", "CMAKE_FIND_PACKAGE_REDIRECTS_DIR", 
    "CMAKE_FIND_PACKAGE_SORT_DIRECTION", "CMAKE_FIND_PACKAGE_SORT_ORDER", "CMAKE_GENERATOR", 
    "CMAKE_GENERATOR_INSTANCE", "CMAKE_GENERATOR_PLATFORM", "CMAKE_GENERATOR_TOOLSET", 
    "CMAKE_IMPORT_LIBRARY_PREFIX", "CMAKE_IMPORT_LIBRARY_SUFFIX", "CMAKE_JOB_POOL_COMPILE", 
    "CMAKE_JOB_POOL_LINK", "CMAKE_JOB_POOL_PRECOMPILE_HEADER", "CMAKE_JOB_POOLS", "CMAKE_<LANG>_COMPILER_AR", 
    "CMAKE_<LANG>_COMPILER_FRONTEND_VARIANT", "CMAKE_<LANG>_COMPILER_LINKER", 
    "CMAKE_<LANG>_COMPILER_LINKER_FRONTEND_VARIANT", "CMAKE_<LANG>_COMPILER_LINKER_ID", 
    "CMAKE_<LANG>_COMPILER_LINKER_VERSION", "CMAKE_<LANG>_COMPILER_RANLIB", "CMAKE_<LANG>_LINK_LIBRARY_SUFFIX", 
    "CMAKE_LINK_LIBRARY_SUFFIX", "CMAKE_LINK_SEARCH_END_STATIC", "CMAKE_LINK_SEARCH_START_STATIC", 
    "CMAKE_MAJOR_VERSION", "CMAKE_MAKE_PROGRAM", "CMAKE_MATCH_COUNT", "CMAKE_MATCH_<n>", 
    "CMAKE_MINIMUM_REQUIRED_VERSION", "CMAKE_MINOR_VERSION", "CMAKE_NETRC", "CMAKE_NETRC_FILE", 
    "CMAKE_PARENT_LIST_FILE", "CMAKE_PATCH_VERSION", "CMAKE_PROJECT_DESCRIPTION", "CMAKE_PROJECT_HOMEPAGE_URL", 
    "CMAKE_PROJECT_NAME", "CMAKE_PROJECT_VERSION", "CMAKE_PROJECT_VERSION_MAJOR", "CMAKE_PROJECT_VERSION_MINOR", 
    "CMAKE_PROJECT_VERSION_PATCH", "CMAKE_PROJECT_VERSION_TWEAK", "CMAKE_RANLIB", "CMAKE_ROOT", 
    "CMAKE_RULE_MESSAGES", "CMAKE_SCRIPT_MODE_FILE", "CMAKE_SHARED_LIBRARY_PREFIX", "CMAKE_SHARED_LIBRARY_SUFFIX", 
    "CMAKE_SHARED_LIBRARY_ARCHIVE_SUFFIX", "CMAKE_SHARED_MODULE_PREFIX", "CMAKE_SHARED_MODULE_SUFFIX", 
    "CMAKE_SIZEOF_VOID_P", "CMAKE_SKIP_INSTALL_RULES", "CMAKE_SKIP_RPATH", "CMAKE_SOURCE_DIR", 
    "CMAKE_STATIC_LIBRARY_PREFIX", "CMAKE_STATIC_LIBRARY_SUFFIX", "CMAKE_Swift_COMPILATION_MODE", 
    "CMAKE_Swift_MODULE_DIRECTORY", "CMAKE_Swift_NUM_THREADS", "CMAKE_TEST_LAUNCHER", 
    "CMAKE_TOOLCHAIN_FILE", "CMAKE_TWEAK_VERSION", "CMAKE_VERBOSE_MAKEFILE", "CMAKE_VERSION", 
    "CMAKE_VS_DEVENV_COMMAND", "CMAKE_VS_MSBUILD_COMMAND", "CMAKE_VS_NsightTegra_VERSION", 
    "CMAKE_VS_NUGET_PACKAGE_RESTORE", "CMAKE_VS_PLATFORM_NAME", "CMAKE_VS_PLATFORM_NAME_DEFAULT", 
    "CMAKE_VS_PLATFORM_TOOLSET", "CMAKE_VS_PLATFORM_TOOLSET_CUDA", "CMAKE_VS_PLATFORM_TOOLSET_CUDA_CUSTOM_DIR", 
    "CMAKE_VS_PLATFORM_TOOLSET_FORTRAN", "CMAKE_VS_PLATFORM_TOOLSET_HOST_ARCHITECTURE", 
    "CMAKE_VS_PLATFORM_TOOLSET_VERSION", "CMAKE_VS_TARGET_FRAMEWORK_IDENTIFIER", 
    "CMAKE_VS_TARGET_FRAMEWORK_TARGETS_VERSION", "CMAKE_VS_TARGET_FRAMEWORK_VERSION", 
    "CMAKE_VS_USE_DEBUG_LIBRARIES", "CMAKE_VS_VERSION_BUILD_NUMBER", "CMAKE_VS_WINDOWS_TARGET_PLATFORM_MIN_VERSION", 
    "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION", "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION_MAXIMUM", 
    "CMAKE_WINDOWS_KMDF_VERSION", "CMAKE_XCODE_BUILD_SYSTEM", "CMAKE_XCODE_PLATFORM_TOOLSET", 
    "<PROJECT-NAME>_BINARY_DIR", "<PROJECT-NAME>_DESCRIPTION", "<PROJECT-NAME>_HOMEPAGE_URL", 
    "<PROJECT-NAME>_IS_TOP_LEVEL", "<PROJECT-NAME>_SOURCE_DIR", "<PROJECT-NAME>_VERSION", 
    "<PROJECT-NAME>_VERSION_MAJOR", "<PROJECT-NAME>_VERSION_MINOR", "<PROJECT-NAME>_VERSION_PATCH", 
    "<PROJECT-NAME>_VERSION_TWEAK", "PROJECT_BINARY_DIR", "PROJECT_DESCRIPTION", "PROJECT_HOMEPAGE_URL", 
    "PROJECT_IS_TOP_LEVEL", "PROJECT_NAME", "PROJECT_SOURCE_DIR", "PROJECT_VERSION", 
    "PROJECT_VERSION_MAJOR", "PROJECT_VERSION_MINOR", "PROJECT_VERSION_PATCH", "PROJECT_VERSION_TWEAK"
]

# Function to check if any information-related variable is present in the reachability string
def contains_information_related_variable(reachability_str):
    return any(var in reachability_str for var in information_related_variables)

# Read the target CSV file specified in the command line argument
def process_csv(file_name):
    total_deps = 0  # Total number of dependencies
    information_related_deps = 0  # Number of dependencies containing information-related variables
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
                    if contains_information_related_variable(reachability):
                        information_related_deps += 1

    # Calculate the percentage of dependencies containing information-related variables
    information_related_percentage = (information_related_deps / total_deps * 100) if total_deps > 0 else 0
    # Calculate the percentage of dependencies with information-related variables among non-empty reachability rows
    information_related_percentage_non_empty = (information_related_deps / reachability_non_empty * 100) if reachability_non_empty > 0 else 0

    # Output the results
    print(f"Total dependencies: {total_deps}")
    print(f"Dependencies with information-related variables: {information_related_deps}")
    print(f"Percentage of total deps: {information_related_percentage:.2f}%")
    print(f"Percentage of deps with reachability not empty: {information_related_percentage_non_empty:.2f}%")

# Main function to execute the script
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)

    # Process the specified CSV file
    process_csv(sys.argv[1])
