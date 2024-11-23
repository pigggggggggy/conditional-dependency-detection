import json
import csv
import sys
from pathlib import Path

def json_to_csv(json_file_path):
    """将 JSON 文件转换为 CSV 文件，并添加统计信息"""
    # 确定 CSV 文件输出路径
    json_path = Path(json_file_path)
    output_csv_path = json_path.with_suffix('.csv')

    # 读取 JSON 文件
    with open(json_file_path, 'r', encoding='utf-8') as jsonfile:
        data = json.load(jsonfile)

    # 统计所有依赖项中 reachability 不为空的数量
    non_empty_count = sum(1 for entry in data if entry.get('reachability', '').strip())

    # 计算非空 reachability 在所有依赖项中的占比
    total_count = len(data)
    non_empty_percentage = (non_empty_count / total_count * 100) if total_count > 0 else 0

    # 打开 CSV 文件并写入数据
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # 写入 CSV 表头
        writer.writerow(['num', 'name', 'reachability', 'type', 'non_empty_count', 'non_empty_percentage'])

        # 写入统计数据行
        writer.writerow(['', '', '', '', non_empty_count, f"{non_empty_percentage:.2f}%"])

        # 遍历 JSON 数据并写入每一条记录
        for i, entry in enumerate(data, start=1):
            name = ', '.join(entry['name']) if isinstance(entry['name'], list) else entry['name']
            reachability = entry.get('reachability', '')
            dep_type = entry.get('type', '')

            # 写入依赖项的具体信息
            writer.writerow([i, name, reachability, dep_type, '', ''])

    print(f"CSV 文件已保存至：{output_csv_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python json_to_csv.py <path_to_json_file>")
        sys.exit(1)

    json_to_csv(sys.argv[1])
