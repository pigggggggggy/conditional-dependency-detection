import csv
import os
from collections import defaultdict

def extract_and_count_files(input_files):
    option_file_counter = defaultdict(set)  # 用字典来存储每个选项的文件集合
    
    for file in input_files:
        if os.path.exists(file):
            with open(file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reachability = row.get('related_options', '')
                    if reachability:
                        options = reachability.split()
                        for option in options:
                            option_file_counter[option].add(file)  # 将文件名添加到选项的集合中
    
    # 将每个选项的文件集合大小作为它的统计值
    option_count = {option: len(files) for option, files in option_file_counter.items()}
    
    return option_count

def write_count_to_csv(output_file, option_count):
    sorted_options = sorted(option_count.items(), key=lambda x: x[1], reverse=True)
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['option_name', 'file_count'])  # 修改列名为file_count
        for option, count in sorted_options:
            writer.writerow([option, count])

# 主函数
def main():
    input_files = [
        'options_extract/ceph_dep_opt.csv',  
        'options_extract/clementine_dep_opt.csv', 
        'options_extract/deepdetect_dep_opt.csv',
        'options_extract/etlegacy_dep_opt.csv',
        'options_extract/freecad_dep_opt.csv',
        'options_extract/lnav_dep_opt.csv',
        'options_extract/natron_dep_opt.csv',
        'options_extract/scylladb_dep_opt.csv',
        'options_extract/tomahawk_dep_opt.csv',
        'options_extract/wireshark_dep_opt.csv',
    ]
    output_file = 'empirical_study_tools/option_file_count_output.csv'  # 输出的文件路径
    
    option_count = extract_and_count_files(input_files)
    write_count_to_csv(output_file, option_count)
    print(f"saved to {output_file}")

if __name__ == '__main__':
    main()
