import re
import csv
import sys
import os

# 定义匹配包名的正则表达式
FIND_PACKAGE_REGEX = re.compile(r'find_package\s*\(\s*([^\s\)]+)', re.IGNORECASE)
PKG_CHECK_MODULES_REGEX = re.compile(r'pkg_check_modules\s*\(\s*([^\s\)]+)', re.IGNORECASE)
CONAN_CMAKE_REGEX = re.compile(r'conan_cmake_(run|configure)\s*\(\s*([^\s\)]+)', re.IGNORECASE)
FIND_LIBRARY_REGEX = re.compile(r'find_library\s*\(\s*([^\s\)]+)\s*(?:NAMES\s+([^\s\$\)]+))?', re.IGNORECASE)
CHECK_LIBRARY_EXISTS_REGEX = re.compile(r'check_library_exists\s*\(\s*([^\s\)]+)', re.IGNORECASE)

def extract_package_name(code):
    """ 从给定的 CMake 代码中提取包名 """
    # 试图从不同的命令中提取包名
    match = FIND_PACKAGE_REGEX.search(code)
    if match:
        return match.group(1)
    
    match = PKG_CHECK_MODULES_REGEX.search(code)
    if match:
        return match.group(1)
    
    match = CONAN_CMAKE_REGEX.search(code)
    if match:
        return match.group(2)
    
    # 对于 find_library 进行更细的匹配
    match = FIND_LIBRARY_REGEX.search(code)
    if match:
        if match.group(2):  # 如果有 NAMES 参数
            return match.group(2).split()[0]  # 提取第一个库名
        return match.group(1)  # 没有 NAMES 时，提取第二个参数
    
    # 对于 check_library_exists 进行匹配
    match = CHECK_LIBRARY_EXISTS_REGEX.search(code)
    if match:
        return match.group(1)

    return None

def process_csv(input_file, output_file):
    """ 处理 CSV 文件，提取包名并生成新文件 """
    with open(input_file, mode='r', encoding='utf-8') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['package_name']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        
        # 写入表头
        writer.writeheader()
        
        # 遍历每一行，提取包名并写入新文件
        for row in reader:
            code = row.get('code', '')
            package_name = extract_package_name(code)
            if package_name:
                row['package_name'] = package_name
                writer.writerow(row)

if __name__ == "__main__":
    # 获取输入输出文件路径
    if len(sys.argv) != 3:
        print("Usage: python extract_package_names.py <input_csv> <output_csv>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.isfile(input_file):
        print(f"Input file {input_file} does not exist.")
        sys.exit(1)
    
    # 处理 CSV 文件
    process_csv(input_file, output_file)
    print(f"Package names extracted and saved to {output_file}")
