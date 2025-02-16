import re
import csv
import sys
import os


FIND_PACKAGE_REGEX = re.compile(r'find_package\s*\(\s*([^\s\)]+)', re.IGNORECASE)
PKG_CHECK_MODULES_REGEX = re.compile(r'pkg_check_modules\s*\(\s*([^\s\)]+)', re.IGNORECASE)
CONAN_CMAKE_REGEX = re.compile(r'conan_cmake_(run|configure)\s*\(\s*([^\s\)]+)', re.IGNORECASE)
FIND_LIBRARY_REGEX = re.compile(r'find_library\s*\(\s*([^\s\)]+)\s*(?:NAMES\s+([^\s\$\)]+))?', re.IGNORECASE)
CHECK_LIBRARY_EXISTS_REGEX = re.compile(r'check_library_exists\s*\(\s*([^\s\)]+)', re.IGNORECASE)

def extract_package_name(code):

    match = FIND_PACKAGE_REGEX.search(code)
    if match:
        return match.group(1)
    
    match = PKG_CHECK_MODULES_REGEX.search(code)
    if match:
        return match.group(1)
    
    match = CONAN_CMAKE_REGEX.search(code)
    if match:
        return match.group(2)
    

    match = FIND_LIBRARY_REGEX.search(code)
    if match:
        if match.group(2): 
            return match.group(2).split()[0] 
        return match.group(1)  
    

    match = CHECK_LIBRARY_EXISTS_REGEX.search(code)
    if match:
        return match.group(1)

    return None

def process_csv(input_file, output_file):

    with open(input_file, mode='r', encoding='utf-8') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['package_name']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()
        
        for row in reader:
            code = row.get('code', '')
            package_name = extract_package_name(code)
            if package_name:
                row['package_name'] = package_name
                writer.writerow(row)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_package_names.py <input_csv> <output_csv>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.isfile(input_file):
        print(f"Input file {input_file} does not exist.")
        sys.exit(1)

    process_csv(input_file, output_file)
    print(f"Package names extracted and saved to {output_file}")
