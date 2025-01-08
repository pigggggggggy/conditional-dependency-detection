import re
import csv
from collections import defaultdict

# 二元测试关键字列表
BINARY_TESTS = [
    "EQUAL", "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL", "STREQUAL",
    "STRLESS", "STRLESS_EQUAL", "STRGREATER", "STRGREATER_EQUAL",
    "VERSION_EQUAL", "VERSION_LESS", "VERSION_LESS_EQUAL", "VERSION_GREATER",
    "VERSION_GREATER_EQUAL", "PATH_EQUAL", "IN_LIST", "IS_NEWER_THAN", "MATCHES"
]

# 定义删除的正则
REMOVE_KEYWORDS = [
    "COMMAND", "POLICY", "TARGET", "TEST", "EXISTS", "IS_READABLE", "IS_WRITABLE", "IS_EXECUTABLE",
    "IS_DIRECTORY", "IS_SYMLINK", "IS_ABSOLUTE", "DEFINED", "NOT", "AND", "OR"
]

# 匹配数字（包括小数和版本号）
# 数字：整数或小数
# 版本号：例如1.11.1
number_pattern = r'^[+-]?\d*\.?\d+$'  # 适用于数字和小数
version_pattern = r'^\d+(\.\d+)+$'  # 匹配版本号格式，如 1.11.1

def clean_and_process_reachability(reachability):
    # 如果 reachability 为 None，则返回空字符串
    if reachability is None:
        return ""

    # 确保 reachability 是字符串
    if not isinstance(reachability, str):
        reachability = str(reachability)

    # 执行正则替换和其他清理操作
    reachability = re.sub(r'"[^"]*"', '', reachability)  # 移除引号中的内容
    reachability = reachability.replace("'", "")  # 移除单引号
    reachability = re.sub(r'\[|\]', '', reachability)  # 移除方括号
    reachability = re.sub(r'\(', '', reachability)  # 移除左圆括号
    reachability = re.sub(r'\)', '', reachability)  # 移除右圆括号

    # 移除 REMOVE_KEYWORDS 中的关键字
    for keyword in REMOVE_KEYWORDS:
        reachability = re.sub(r'\b' + re.escape(keyword) + r'\b', '', reachability)

    # 移除逗号
    reachability = reachability.replace(",", "")
    # 移除多余的空格
    reachability = re.sub(r'\s+', ' ', reachability).strip()

    # 遍历每个二元测试关键字
    for test in BINARY_TESTS:
        # 正则表达式：匹配二元测试关键字和它前后的操作数
        pattern = r'(\S+)\s+' + re.escape(test) + r'\s+(\S+)'
        
        matches = re.findall(pattern, reachability)
        
        for match in matches:
            left_operand, right_operand = match
            
            # 检查操作数是否是数字（包括小数）、版本号（如 1.11.1）或双引号中的字符串
            if re.match(number_pattern, left_operand) or re.match(version_pattern, left_operand) or re.match(r'^".*?"$', left_operand):
                # 如果是数字、小数、版本号或双引号中的内容，删除该操作数
                reachability = re.sub(r'\b' + re.escape(left_operand) + r'\b', '', reachability)

            if re.match(number_pattern, right_operand) or re.match(version_pattern, right_operand) or re.match(r'^".*?"$', right_operand):
                # 如果是数字、小数、版本号或双引号中的内容，删除该操作数
                reachability = re.sub(r'\b' + re.escape(right_operand) + r'\b', '', reachability)

            # 删除二元操作符本身
            reachability = re.sub(r'\b' + re.escape(test) + r'\b', '', reachability)

    # 将结果拆分为选项并去重
    options = reachability.split(' ')
    options = list(dict.fromkeys(options))  # 去重并保持顺序

    # 返回处理后的选项列表
    return ' '.join(options)

def extract_options(input_file, output_file):
    with open(input_file, newline='', encoding='utf-8') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = ['package_name', 'reachability']
        writer = csv.DictWriter(outfile, fieldnames=['num', 'dependency_name', 'related_options', 'original_reachability'])

        writer.writeheader()

        data = defaultdict(lambda: {'num': None, 'related_options': [], 'original_reachability': []})

        num_counter = 1

        for row in reader:
            clean_row = {key: row[key] for key in fieldnames}

            # 获取原始的 reachability
            original_reachability = clean_row['reachability']  

            # 清理 reachability 列并处理二元操作数
            if original_reachability:
                options = clean_and_process_reachability(original_reachability)
                clean_row['reachability'] = options
            else:
                clean_row['reachability'] = ''

            # 获取 dependency_name 并检查是否包含 $、\ 或 "
            dependency_name = clean_row['package_name']
            if any(char in dependency_name for char in ['$','\\','"']): 
                continue  # 如果包含特殊字符，跳过此行

            # 将依赖项相关信息合并
            if data[dependency_name]['num'] is None:
                data[dependency_name]['num'] = num_counter
                num_counter += 1

            data[dependency_name]['related_options'].append(clean_row['reachability'])
            data[dependency_name]['original_reachability'].append(original_reachability)

        # 将合并后的数据写入输出文件
        for dependency_name, values in data.items():
            # Check if any of the original_reachability values is '[]'
            if '[]' in values['original_reachability']:
                related_options = ''  # If there's a '[]', set related_options to empty
            else:
                related_options = ' '.join(values['related_options'])

            clean_row = {
                'num': values['num'],
                'dependency_name': dependency_name,
                'related_options': related_options,
                'original_reachability': ' or '.join(values['original_reachability']),
            }
            writer.writerow(clean_row)

    print(f"输出已写入 {output_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='提取并清理 CSV 文件中 reachability 列的选项。')
    parser.add_argument('input', type=str, help='输入 CSV 文件')
    parser.add_argument('output', type=str, help='输出 CSV 文件')
    args = parser.parse_args()
    
    extract_options(args.input, args.output)

if __name__ == '__main__':
    main()
