import csv
import json
import argparse
import re
from extract_options import clean_and_process_reachability  


def contains_cmake_function(code):
    cmake_functions = [
        "set(", "unset(", "list(", "foreach(", "endforeach(", 
        "if(", "else(", "message(", "file(", "option(", 
        "add_definitions(", "include(", "configure_file(", 
        "set_property(", "get_property(", "math(", "string(","find_library(","find_package("
    ]
    
    for func in cmake_functions:
        if func in code:
            return True
    return False


def is_exact_match(option, code):
    if option is None:
        return False
    pattern = r'(?<![a-zA-Z0-9_-])' + re.escape(option) + r'(?![a-zA-Z0-9_-])'
    return re.search(pattern, code) is not None


def load_reachability_data(input_file):
    reachability_data = {}
    
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            dependency_name = row['dependency_name'] 
            related_options = row['related_options']  
 
            if not related_options:
                continue

            options = related_options.split()  
            
            if dependency_name not in reachability_data:
                reachability_data[dependency_name] = []
            
            reachability_data[dependency_name].extend(options)
    
    return reachability_data


def recursive_indirect_options(option, code, reachability, reachability_data, input_file, depth=0):
    if depth >= 3:
        return {}

    cleaned_reachability = clean_and_process_reachability(reachability)
    
    if not cleaned_reachability:
        return {}

    new_option_names = cleaned_reachability.split()  

    indirect_options = {}

    with open(input_file, newline='', encoding='utf-8') as infile2:
        reader2 = csv.DictReader(infile2)

        # 对于每个 cleaned_reachability 中的选项进行处理
        for new_option_name in new_option_names:
            new_option_code = None
            new_reachability = None
            matched_options = []  # 存储所有匹配项

            # 遍历 input_file 中的每一行，寻找匹配项
            for row2 in reader2:
                if is_exact_match(new_option_name, row2['name']):
                    new_option_code = row2['code']
                    new_reachability = row2['reachability']
                    matched_options.append({
                        'new_option_code': new_option_code,
                        'new_reachability': new_reachability
                    })

            # 如果没有匹配项，跳过该选项
            if not matched_options:
                continue

            # 检查每个匹配项的 new_option_code 是否有效
            valid_matched_options = []
            for matched_option in matched_options:
                new_option_code = matched_option['new_option_code']
                if new_option_code and contains_cmake_function(new_option_code):
                    valid_matched_options.append(matched_option)
            
            # 如果没有有效的匹配项，则跳过
            if not valid_matched_options:
                continue

            # 对于每个有效的匹配项进行递归处理
            indirect_options[new_option_name] = {
                'new_option_name': new_option_name,
                'new_option_code_reachabilities': valid_matched_options,  # 保存所有有效的匹配项
                'new_indirect_options': []
            }

            for matched_option in valid_matched_options:
                new_option_code = matched_option['new_option_code']
                new_reachability = matched_option['new_reachability']

                # 递归调用，处理嵌套关系
                indirect_options[new_option_name]['new_indirect_options'].append(
                    recursive_indirect_options(
                        new_option_name, new_option_code, new_reachability, reachability_data, input_file, depth + 1
                    )
                )

    return indirect_options




def search_name_column(input_file, reachability_data):
    result_data = {}
    csv.field_size_limit(100000000)
    
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        for row in reader:
            code = row['code']
            name = row['name']
            reachability = row['reachability']

            if not reachability:
                continue

            if contains_cmake_function(code):
                option_code = code  # 如果包含CMake函数，使用原始代码
            else:
                option_code = None  # 如果不包含CMake函数，设置为None
            
            # 这里确保即使option_code为None，也不会跳过，而是继续处理
            if option_code is None:
                reachability = None  # 如果没有option_code，则reachability也设置为None

            for dependency_name_key, options in reachability_data.items():
                for option in options:
                    if is_exact_match(option, name):
                        indirect_options = recursive_indirect_options(
                            option, option_code, reachability, reachability_data, input_file
                        )
                        
                        if dependency_name_key not in result_data:
                            result_data[dependency_name_key] = []

                        result_data[dependency_name_key].append({
                            'option_name': option,
                            'option_code': option_code,
                            'reachability': reachability,
                            'indirect_options': indirect_options 
                        })
    
    return result_data

def save_to_json(output_file, data):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        json.dump(data, outfile, indent=4, ensure_ascii=False)

# 主函数
def main():
    parser = argparse.ArgumentParser(description='Search name column for reachability options and output results as JSON.')
    parser.add_argument('input_reachability', type=str, help='Input CSV file with first table reachability data')
    parser.add_argument('input_code', type=str, help='Input CSV file with second table code and name columns')
    parser.add_argument('output_json', type=str, help='Output JSON file')
    
    args = parser.parse_args()

    reachability_data = load_reachability_data(args.input_reachability)
    

    result_data = search_name_column(args.input_code, reachability_data)
    

    save_to_json(args.output_json, result_data)

    print(f"Results saved to {args.output_json}")

if __name__ == '__main__':
    main()