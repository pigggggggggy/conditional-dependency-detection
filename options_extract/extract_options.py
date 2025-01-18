import re
import csv
from collections import defaultdict

BINARY_TESTS = [
    "EQUAL", "LESS", "LESS_EQUAL", "GREATER", "GREATER_EQUAL", "STREQUAL",
    "STRLESS", "STRLESS_EQUAL", "STRGREATER", "STRGREATER_EQUAL",
    "VERSION_EQUAL", "VERSION_LESS", "VERSION_LESS_EQUAL", "VERSION_GREATER",
    "VERSION_GREATER_EQUAL", "PATH_EQUAL", "IN_LIST", "IS_NEWER_THAN", "MATCHES"
]

REMOVE_KEYWORDS = [
    "COMMAND", "POLICY", "TARGET", "TEST", "EXISTS", "IS_READABLE", "IS_WRITABLE", "IS_EXECUTABLE",
    "IS_DIRECTORY", "IS_SYMLINK", "IS_ABSOLUTE", "DEFINED", "NOT", "AND", "OR"
]

number_pattern = r'^[+-]?\d*\.?\d+$'  
version_pattern = r'^\d+(\.\d+)+$'  

def clean_and_process_reachability(reachability):
    if reachability is None:
        return ""

    if not isinstance(reachability, str):
        reachability = str(reachability)

    reachability = re.sub(r'"[^"]*"', '', reachability)
    reachability = reachability.replace("'", "")  
    reachability = re.sub(r'\[|\]', '', reachability) 
    reachability = re.sub(r'\(', '', reachability) 
    reachability = re.sub(r'\)', '', reachability)  

    for keyword in REMOVE_KEYWORDS:
        reachability = re.sub(r'\b' + re.escape(keyword) + r'\b', '', reachability)

    reachability = reachability.replace(",", "")
    reachability = re.sub(r'\s+', ' ', reachability).strip()


    for test in BINARY_TESTS:
        
        pattern = r'(\S+)\s+' + re.escape(test) + r'\s+(\S+)'
        
        matches = re.findall(pattern, reachability)
        
        for match in matches:
            left_operand, right_operand = match
            
            if re.match(number_pattern, left_operand) or re.match(version_pattern, left_operand) or re.match(r'^".*?"$', left_operand):
                reachability = re.sub(r'\b' + re.escape(left_operand) + r'\b', '', reachability)

            if re.match(number_pattern, right_operand) or re.match(version_pattern, right_operand) or re.match(r'^".*?"$', right_operand):
                reachability = re.sub(r'\b' + re.escape(right_operand) + r'\b', '', reachability)
            reachability = re.sub(r'\b' + re.escape(test) + r'\b', '', reachability)

    options = reachability.split(' ')
    options = list(dict.fromkeys(options))

    return ' '.join(options)

def extract_options(input_file, output_file):
    with open(input_file, newline='', encoding='utf-8') as infile, open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = ['package_name', 'reachability', 'id']  # Adding 'id' to the fieldnames
        writer = csv.DictWriter(outfile, fieldnames=['num', 'dependency_name', 'related_options', 'original_reachability', 'actor_id'])  # Added 'actor_id'

        writer.writeheader()

        data = defaultdict(lambda: {'num': None, 'related_options': [], 'original_reachability': [], 'actor_id': None})

        num_counter = 1

        for row in reader:
            clean_row = {key: row[key] for key in fieldnames}

            original_reachability = clean_row['reachability']  

            if original_reachability:
                options = clean_and_process_reachability(original_reachability)
                clean_row['reachability'] = options
            else:
                clean_row['reachability'] = ''

            dependency_name = clean_row['package_name']
            if any(char in dependency_name for char in ['$','\\','"']): 
                continue 

            if data[dependency_name]['num'] is None:
                data[dependency_name]['num'] = num_counter
                num_counter += 1

            # Extract actor_id from 'id' field
            actor_id_match = re.search(r'(\d+)$', clean_row['id'])
            actor_id = actor_id_match.group(1) if actor_id_match else ''  # Extract last number after "_" or return empty if not found
            data[dependency_name]['actor_id'] = actor_id

            data[dependency_name]['related_options'].append(clean_row['reachability'])
            data[dependency_name]['original_reachability'].append(original_reachability)

        for dependency_name, values in data.items():
            if '[]' in values['original_reachability']:
                related_options = '' 
            else:
                related_options = ' '.join(values['related_options'])

            clean_row = {
                'num': values['num'],
                'dependency_name': dependency_name,
                'related_options': related_options,
                'original_reachability': ' or '.join(values['original_reachability']),
                'actor_id': values['actor_id']  # Adding actor_id to the final output
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
