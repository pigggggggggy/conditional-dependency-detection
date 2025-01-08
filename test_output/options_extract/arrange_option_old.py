import csv
import json
import argparse
import re
from extract_options import clean_reachability  # 导入 clean_reachability 函数

# 检查代码行是否包含特定的 CMake 函数
def contains_cmake_function(code):
    cmake_functions = [
        "set(", "unset(", "list(", "foreach(", "endforeach(", 
        "if(", "else(", "message(", "file(", "option(", 
        "add_definitions(", "include(", "configure_file(", 
        "set_property(", "get_property(", "math(", "string("
    ]
    
    for func in cmake_functions:
        if func in code:
            return True
    return False

# 判断是否为精确匹配，且不允许有字母、数字或下划线跟随关键字
def is_exact_match(option, code):
    if option is None:  # Skip if option is None
        return False
    # 使用负向前瞻和负向后顾，确保 option 不是与字母、数字或下划线连接的部分
    pattern = r'(?<![a-zA-Z0-9_])' + re.escape(option) + r'(?![a-zA-Z0-9_])'
    return re.search(pattern, code) is not None

# 加载第一个表格的数据（reachability）
def load_reachability_data(input_file):
    reachability_data = {}
    
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            dependency_name = row['dependency_name']  # Use 'dependency_name' instead of 'name'
            related_options = row['related_options']  # Use 'related_options' instead of 'reachability'
            
            # 跳过 related_options 为空的行
            if not related_options:
                continue
            
            # 按空格拆分 related_options 字段为多个选项
            options = related_options.split()  
            
            if dependency_name not in reachability_data:
                reachability_data[dependency_name] = []
            
            # 将每个选项清理并加入到字典中
            reachability_data[dependency_name].extend([clean_reachability(option) for option in options])
    
    return reachability_data

# 搜索第二个表格中的 code 列，只保留包含 CMake 命令的行
def search_name_column(input_file, reachability_data):
    result_data = {}
    csv.field_size_limit(100000000)
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        
        for row in reader:
            code = row['code']
            name = row['name']  # 在目标表格中搜索 name 列

            # 只保留包含 CMake 命令的代码行
            if contains_cmake_function(code):
                # 遍历第一个表格的 dependency_name 和 related_options 数据
                for dependency_name_key, options in reachability_data.items():
                    # 遍历 related_options 中的每个选项
                    for option in options:
                        # 如果选项匹配目标表格的 name 列，则添加匹配信息
                        if is_exact_match(option, name):
                            # 清理并提取 reachability 列
                            cleaned_reachability = clean_reachability(row['reachability'])
                            
                            # 确保依赖项名在结果数据中
                            if dependency_name_key not in result_data:
                                result_data[dependency_name_key] = []

                            # 将结果保存到字典中，保持原始的 tpl 名（例如 ZLIB）
                            result_data[dependency_name_key].append({
                                'option_name': name,  # Changed 'name' to 'option_name'
                                'option_code': code,  # Changed 'code' to 'option_code'
                                'reachability': row['reachability'],  # 原始的 reachability
                                'indirect_options': cleaned_reachability  # 清理后的 related_options
                            })
    
    return result_data

# 保存结果为 JSON 文件
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
    
    # 加载第一个表格的 reachability 数据
    reachability_data = load_reachability_data(args.input_reachability)
    
    # 在第二个表格的 code 列中进行搜索，保留包含 CMake 命令的行
    result_data = search_name_column(args.input_code, reachability_data)
    
    # 将结果保存为 JSON 文件
    save_to_json(args.output_json, result_data)

    print(f"Results saved to {args.output_json}")

if __name__ == '__main__':
    main()