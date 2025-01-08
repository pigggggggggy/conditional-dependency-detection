import json
import argparse

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description="Generate CMakeLists.txt from JSON configuration.")
    parser.add_argument('input_file', help="Path to the input JSON file")
    parser.add_argument('output_file', help="Path to the output CMakeLists.txt file")
    return parser.parse_args()

# 从 JSON 文件读取数据
def read_json(input_file):
    with open(input_file, 'r') as file:
        return json.load(file)

# 生成 CMakeLists.txt 脚本
def generate_cmake(data):
    cmake_script = []
    visited = set()

    # 递归处理选项及其间接依赖
    def process_option(option_name, option_data, is_top_level=True):
        if option_name in visited:
            return
        visited.add(option_name)

        # 处理间接选项
        indirect_options = option_data.get("indirect_options", {})
        for indirect_name, indirect_data in indirect_options.items():
            # 处理间接选项，递归调用
            new_option_code = indirect_data.get("new_option_code", None)
            if new_option_code is None:
                print(f"警告：'{indirect_name}' 缺少 'new_option_code' 键，跳过此间接选项。")
                continue

            # 处理 new_reachability 并生成 if 语句
            new_reachability = eval(indirect_data.get("new_reachability", "[]"))
            if new_reachability:
                condition = ' AND '.join(new_reachability)
                cmake_script.append(f"if({condition})")
                cmake_script.append(f"    {new_option_code}")
                cmake_script.append("endif()")
            else:
                # 如果没有 new_reachability，直接输出 new_option_code
                cmake_script.append(new_option_code)

            # 递归处理间接选项的间接选项
            process_option(indirect_name, indirect_data, is_top_level=False)

        # 现在处理当前选项本身
        # 如果是最上层选项，使用 'option_code'，否则使用 'new_option_code'
        option_code = option_data.get("option_code" if is_top_level else "new_option_code", None)
        if option_code is None:
            print(f"警告：'{option_name}' 缺少 'option_code' 或 'new_option_code' 键，跳过此选项。")
            return

        # 处理 reachability 并生成 if 语句
        reachability = eval(option_data.get("reachability", "[]"))  # 解析为列表，默认空列表

        # 如果有 reachability，则将 option_code 放在 if 条件内部
        if reachability:
            condition = ' AND '.join(reachability)
            cmake_script.append(f"if({condition})")
            cmake_script.append(f"    {option_code}")
            cmake_script.append("endif()")
        else:
            # 如果没有 reachability，直接输出 set 语句
            cmake_script.append(option_code)

    # 遍历所有数据并处理
    for key, options in data.items():
        for option in options:
            process_option(option["option_name"], option)

    return "\n".join(cmake_script)

# 主函数
def main():
    args = parse_args()
    
    # 从输入 JSON 文件读取数据
    data = read_json(args.input_file)

    # 生成 CMakeLists.txt 脚本
    cmake_script = generate_cmake(data)

    # 将生成的 CMakeLists.txt 写入输出文件
    with open(args.output_file, 'w') as output_file:
        output_file.write(cmake_script)
    print(f"CMakeLists.txt 文件已生成: {args.output_file}")

if __name__ == "__main__":
    main()
