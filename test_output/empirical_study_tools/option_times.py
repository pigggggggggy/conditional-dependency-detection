import csv
import os
from collections import Counter

def extract_and_count_options(input_files):
    option_counter = Counter() 
    

    for file in input_files:
        if os.path.exists(file):
            with open(file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reachability = row.get('reachability', '')
                    if reachability:  
                        options = reachability.split() 
                        option_counter.update(options)  
    
    return option_counter

def write_count_to_csv(output_file, option_counter):

    sorted_options = option_counter.most_common()
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['option_name', 'times']) 
        for option, count in sorted_options:
            writer.writerow([option, count])  

# 主函数
def main():
    input_files = [
        'options_extract\ceph_dep_opt.csv',  
        'options_extract\clementine_dep_opt.csv', 
        'options_extract\deepdetect_dep_opt.csv',
        'options_extract\etlegacy_dep_opt.csv',
        'options_extract/freecad_dep_opt.csv',
        'options_extract\lnav_dep_opt.csv',
        'options_extract/natron_dep_opt.csv',
        'options_extract\scylladb_dep_opt.csv',
        'options_extract/tomahawk_dep_opt.csv',
        'options_extract\wireshark_dep_opt.csv',
    ]
    output_file = 'empirical_study_tools\option_count_output.csv'  
    
    option_counter = extract_and_count_options(input_files)
    write_count_to_csv(output_file, option_counter)
    print(f"saved to {output_file}")


if __name__ == '__main__':
    main()
