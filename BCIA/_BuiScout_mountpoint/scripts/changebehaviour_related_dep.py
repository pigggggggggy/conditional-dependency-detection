import csv
import sys

# List of variables that change behavior
behavior_changing_variables = [
    "BUILD_SHARED_LIBS", "CMAKE_ABSOLUTE_DESTINATION_FILES", "CMAKE_ADD_CUSTOM_COMMAND_DEPENDS_EXPLICIT_ONLY",
    "CMAKE_APPBUNDLE_PATH", "CMAKE_BUILD_TYPE", "CMAKE_CLANG_VFS_OVERLAY", "CMAKE_CODEBLOCKS_COMPILER_ID",
    "CMAKE_CODEBLOCKS_EXCLUDE_EXTERNAL_FILES", "CMAKE_CODELITE_USE_TARGETS", "CMAKE_COLOR_DIAGNOSTICS",
    "CMAKE_COLOR_MAKEFILE", "CMAKE_CONFIGURATION_TYPES", "CMAKE_DEPENDS_IN_PROJECT_ONLY",
    "CMAKE_DISABLE_FIND_PACKAGE_<PackageName>", "CMAKE_ECLIPSE_GENERATE_LINKED_RESOURCES",
    "CMAKE_ECLIPSE_GENERATE_SOURCE_PROJECT", "CMAKE_ECLIPSE_MAKE_ARGUMENTS", "CMAKE_ECLIPSE_RESOURCE_ENCODING",
    "CMAKE_ECLIPSE_VERSION", "CMAKE_ERROR_DEPRECATED", "CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION",
    "CMAKE_EXECUTE_PROCESS_COMMAND_ECHO", "CMAKE_EXPORT_BUILD_DATABASE", "CMAKE_EXPORT_COMPILE_COMMANDS",
    "CMAKE_EXPORT_PACKAGE_REGISTRY", "CMAKE_EXPORT_NO_PACKAGE_REGISTRY", "CMAKE_FIND_APPBUNDLE", "CMAKE_FIND_FRAMEWORK",
    "CMAKE_FIND_LIBRARY_CUSTOM_LIB_SUFFIX", "CMAKE_FIND_LIBRARY_PREFIXES", "CMAKE_FIND_LIBRARY_SUFFIXES",
    "CMAKE_FIND_NO_INSTALL_PREFIX", "CMAKE_FIND_PACKAGE_PREFER_CONFIG", "CMAKE_FIND_PACKAGE_RESOLVE_SYMLINKS",
    "CMAKE_FIND_PACKAGE_TARGETS_GLOBAL", "CMAKE_FIND_PACKAGE_WARN_NO_MODULE", "CMAKE_FIND_ROOT_PATH",
    "CMAKE_FIND_ROOT_PATH_MODE_INCLUDE", "CMAKE_FIND_ROOT_PATH_MODE_LIBRARY", "CMAKE_FIND_ROOT_PATH_MODE_PACKAGE",
    "CMAKE_FIND_ROOT_PATH_MODE_PROGRAM", "CMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH", "CMAKE_FIND_USE_CMAKE_PATH",
    "CMAKE_FIND_USE_CMAKE_SYSTEM_PATH", "CMAKE_FIND_USE_INSTALL_PREFIX", "CMAKE_FIND_USE_PACKAGE_REGISTRY",
    "CMAKE_FIND_USE_PACKAGE_ROOT_PATH", "CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH", "CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY",
    "CMAKE_FRAMEWORK_PATH", "CMAKE_IGNORE_PATH", "CMAKE_IGNORE_PREFIX_PATH", "CMAKE_INCLUDE_DIRECTORIES_BEFORE",
    "CMAKE_INCLUDE_DIRECTORIES_PROJECT_BEFORE", "CMAKE_INCLUDE_PATH", "CMAKE_INSTALL_DEFAULT_COMPONENT_NAME",
    "CMAKE_INSTALL_DEFAULT_DIRECTORY_PERMISSIONS", "CMAKE_INSTALL_MESSAGE", "CMAKE_INSTALL_PREFIX",
    "CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT", "CMAKE_KATE_FILES_MODE", "CMAKE_KATE_MAKE_ARGUMENTS",
    "CMAKE_LIBRARY_PATH", "CMAKE_LINK_DIRECTORIES_BEFORE", "CMAKE_LINK_LIBRARIES_ONLY_TARGETS", "CMAKE_MAXIMUM_RECURSION_DEPTH",
    "CMAKE_MESSAGE_CONTEXT", "CMAKE_MESSAGE_CONTEXT_SHOW", "CMAKE_MESSAGE_INDENT", "CMAKE_MESSAGE_LOG_LEVEL",
    "CMAKE_MFC_FLAG", "CMAKE_MODULE_PATH", "CMAKE_POLICY_DEFAULT_CMP<NNNN>", "CMAKE_POLICY_WARNING_CMP<NNNN>",
    "CMAKE_PREFIX_PATH", "CMAKE_PROGRAM_PATH", "CMAKE_PROJECT_INCLUDE", "CMAKE_PROJECT_INCLUDE_BEFORE",
    "CMAKE_PROJECT_<PROJECT-NAME>_INCLUDE", "CMAKE_PROJECT_<PROJECT-NAME>_INCLUDE_BEFORE", "CMAKE_PROJECT_TOP_LEVEL_INCLUDES",
    "CMAKE_REQUIRE_FIND_PACKAGE_<PackageName>", "CMAKE_SKIP_INSTALL_ALL_DEPENDENCY", "CMAKE_SKIP_TEST_ALL_DEPENDENCY",
    "CMAKE_STAGING_PREFIX", "CMAKE_SUBLIME_TEXT_2_ENV_SETTINGS", "CMAKE_SUBLIME_TEXT_2_EXCLUDE_BUILD_TREE",
    "CMAKE_SUPPRESS_REGENERATION", "CMAKE_SYSROOT", "CMAKE_SYSROOT_COMPILE", "CMAKE_SYSROOT_LINK", "CMAKE_SYSTEM_APPBUNDLE_PATH",
    "CMAKE_SYSTEM_FRAMEWORK_PATH", "CMAKE_SYSTEM_IGNORE_PATH", "CMAKE_SYSTEM_IGNORE_PREFIX_PATH", "CMAKE_SYSTEM_INCLUDE_PATH",
    "CMAKE_SYSTEM_LIBRARY_PATH", "CMAKE_SYSTEM_PREFIX_PATH", "CMAKE_SYSTEM_PROGRAM_PATH", "CMAKE_TLS_CAINFO",
    "CMAKE_TLS_VERIFY", "CMAKE_TLS_VERSION", "CMAKE_USER_MAKE_RULES_OVERRIDE", "CMAKE_WARN_DEPRECATED",
    "CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION", "CMAKE_XCODE_GENERATE_SCHEME", "CMAKE_XCODE_GENERATE_TOP_LEVEL_PROJECT_ONLY",
    "CMAKE_XCODE_LINK_BUILD_PHASE_MODE", "CMAKE_XCODE_SCHEME_ADDRESS_SANITIZER", "CMAKE_XCODE_SCHEME_ADDRESS_SANITIZER_USE_AFTER_RETURN",
    "CMAKE_XCODE_SCHEME_DEBUG_DOCUMENT_VERSIONING", "CMAKE_XCODE_SCHEME_DISABLE_MAIN_THREAD_CHECKER", "CMAKE_XCODE_SCHEME_DYNAMIC_LIBRARY_LOADS",
    "CMAKE_XCODE_SCHEME_DYNAMIC_LINKER_API_USAGE", "CMAKE_XCODE_SCHEME_ENABLE_GPU_API_VALIDATION", "CMAKE_XCODE_SCHEME_ENABLE_GPU_FRAME_CAPTURE_MODE",
    "CMAKE_XCODE_SCHEME_ENABLE_GPU_SHADER_VALIDATION", "CMAKE_XCODE_SCHEME_ENVIRONMENT", "CMAKE_XCODE_SCHEME_GUARD_MALLOC",
    "CMAKE_XCODE_SCHEME_LAUNCH_CONFIGURATION", "CMAKE_XCODE_SCHEME_LAUNCH_MODE", "CMAKE_XCODE_SCHEME_MAIN_THREAD_CHECKER_STOP",
    "CMAKE_XCODE_SCHEME_MALLOC_GUARD_EDGES", "CMAKE_XCODE_SCHEME_MALLOC_SCRIBBLE", "CMAKE_XCODE_SCHEME_MALLOC_STACK",
    "CMAKE_XCODE_SCHEME_THREAD_SANITIZER", "CMAKE_XCODE_SCHEME_THREAD_SANITIZER_STOP", "CMAKE_XCODE_SCHEME_UNDEFINED_BEHAVIOUR_SANITIZER",
    "CMAKE_XCODE_SCHEME_UNDEFINED_BEHAVIOUR_SANITIZER_STOP", "CMAKE_XCODE_SCHEME_WORKING_DIRECTORY", "CMAKE_XCODE_SCHEME_ZOMBIE_OBJECTS",
    "CMAKE_XCODE_XCCONFIG", "<PackageName>_ROOT"
]

# Function to check if any behavior-changing variable is present in the reachability string
def contains_behavior_changing_variable(reachability_str):
    return any(var in reachability_str for var in behavior_changing_variables)

# Read the target CSV file specified in the command line argument
def process_csv(file_name):
    total_deps = 0  # Total number of dependencies
    behavior_changing_deps = 0  # Number of dependencies containing behavior-changing variables
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
                    if contains_behavior_changing_variable(reachability):
                        behavior_changing_deps += 1

    # Calculate the percentage of dependencies containing behavior-changing variables
    behavior_changing_percentage = (behavior_changing_deps / total_deps * 100) if total_deps > 0 else 0
    # Calculate the percentage of dependencies with behavior-changing variables among non-empty reachability rows
    behavior_changing_percentage_non_empty = (behavior_changing_deps / reachability_non_empty * 100) if reachability_non_empty > 0 else 0

    # Output the results
    print(f"Total dependencies: {total_deps}")
    print(f"Dependencies with behavior-changing variables: {behavior_changing_deps}")
    print(f"Percentage of total deps: {behavior_changing_percentage:.2f}%")
    print(f"Percentage of deps with reachability not empty: {behavior_changing_percentage_non_empty:.2f}%")

# Main function to execute the script
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)

    # Process the specified CSV file
    process_csv(sys.argv[1])
