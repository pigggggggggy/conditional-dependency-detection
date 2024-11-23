import pandas as pd
import requests
import json
import time
import argparse

def fetch_with_retry(url, headers, retries=3, delay=5, timeout=10):
    """
    带重试和超时机制的请求函数
    """
    for attempt in range(retries):
        try:
            # 添加超时机制
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 503:
                print(f"服务器暂时不可用，重试 {attempt + 1}/{retries} 次...")
                time.sleep(delay)
            else:
                print(f"请求失败，状态码: {response.status_code}")
                break
        except requests.exceptions.Timeout:
            print(f"请求超时，重试 {attempt + 1}/{retries} 次...")
            time.sleep(delay)
        except Exception as e:
            print(f"请求错误: {e}")
            time.sleep(delay)
    return None

def check_vulnerabilities(input_file, output_file):
    try:
        dependencies = pd.read_csv(input_file)
    except Exception as e:
        print(f"无法读取输入文件: {e}")
        return

    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0?keyword="
    api_key = "cd900c57-7deb-4cb6-bbec-b26665db6fb5  "  # 替换为你的 API Key
    headers = {"apikey": api_key}

    results = []

    for index, row in dependencies.iterrows():
        num = row['num']
        name = row['name']
        reachability = row['reachability']

        # 检查是否为空值
        if pd.isna(name):
            print(f"依赖名称为空，跳过: num={num}")
            continue
        
        print(f"正在查询依赖: {name} (num: {num})")
        
        # 查询 NVD API
        response = fetch_with_retry(base_url + str(name), headers, timeout=10)
        if response and response.status_code == 200:
            data = response.json()
            vulnerabilities = data.get('vulnerabilities', [])
            if vulnerabilities:
                cve_ids = [vul['cve']['id'] for vul in vulnerabilities]
                results.append({
                    "num": num,
                    "name": name,
                    "reachability": reachability,
                    "is_vulnerable": True,
                    "cve_ids": cve_ids
                })
            else:
                results.append({
                    "num": num,
                    "name": name,
                    "reachability": reachability,
                    "is_vulnerable": False,
                    "cve_ids": []
                })
        else:
            print(f"跳过查询：{name}，原因可能是超时或服务不可用")
            results.append({
                "num": num,
                "name": name,
                "reachability": reachability,
                "is_vulnerable": "Error",
                "cve_ids": []
            })

        time.sleep(3)  # 延迟以避免频繁请求

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"结果已保存到 {output_file}")
    except Exception as e:
        print(f"无法保存输出文件: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检测依赖是否是漏洞依赖")
    parser.add_argument('input_file', type=str, help="输入 CSV 文件路径")
    parser.add_argument('output_file', type=str, help="输出 JSON 文件路径")
    args = parser.parse_args()

    check_vulnerabilities(args.input_file, args.output_file)
