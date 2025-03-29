import json
import time
from datetime import datetime

import requests
from tqdm.contrib.concurrent import thread_map

# Configuration
GITHUB_TOKEN = ""
BASE_URL = "https://api.github.com/search/repositories"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
MAX_REPOS = 1000
MAX_WORKERS = 10  # 并发线程数
OUTPUT_DIR = "../output/repo"  # 输出目录

# 查询参数
QUERY = "stars:>100 language:C++ language:C fork:false"
PARAMS_TEMPLATE = {
    "q": QUERY,
    "sort": "stars",
    "order": "desc",
    "per_page": 100,
    "page": 1,
}


def safe_request(url, headers, params=None, json_data=None, max_retries=3):
    """带速率限制处理和重试的请求函数"""
    for _ in range(max_retries):
        try:
            if json_data:
                response = requests.post(
                    url, json=json_data, headers=headers, timeout=10
                )
            else:
                response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                return response

            # 处理速率限制
            if response.status_code == 403:
                reset_time = int(
                    response.headers.get("X-RateLimit-Reset", time.time() + 60)
                )
                sleep_time = max(reset_time - time.time(), 10)
                print(f"Rate limited. Sleeping {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                continue

            # 处理其他错误
            print(f"Request failed: {response.status_code} - {response.text}")
            time.sleep(2)

        except Exception as e:
            print(f"Request error: {str(e)}")
            time.sleep(5)

    return None


def fetch_repositories():
    """获取仓库列表"""
    repositories = []
    params = PARAMS_TEMPLATE.copy()

    while len(repositories) < MAX_REPOS:
        # 动态调整每页数量
        remaining = MAX_REPOS - len(repositories)
        params["per_page"] = min(100, remaining)

        response = safe_request(BASE_URL, HEADERS, params=params)
        if not response:
            break

        data = response.json()
        for item in data.get("items", []):
            repositories.append(
                {
                    "full_name": item["full_name"],
                    "html_url": item["html_url"],
                    "default_branch": item["default_branch"],
                    "stars": item["stargazers_count"],
                    "fork": item["fork"],
                    "languages_url": item["languages_url"],
                }
            )

        # 分页控制
        if "next" not in response.links:
            break
        params["page"] += 1

    return repositories[:MAX_REPOS]


def process_repository(repo):
    """处理单个仓库"""
    # 检查CMakeLists.txt
    cmake_url = (
        f"https://api.github.com/repos/{repo['full_name']}/contents/CMakeLists.txt"
    )
    response = safe_request(cmake_url, HEADERS)
    has_cmake = response.status_code == 200 if response else False

    # 获取最新commit
    commit_url = f"https://api.github.com/repos/{repo['full_name']}/commits/{repo['default_branch']}"
    response = safe_request(commit_url, HEADERS)
    commit_hash = response.json()["sha"] if response else None

    # 获取语言信息（二次验证）
    lang_response = safe_request(repo["languages_url"], HEADERS)
    languages = lang_response.json().keys() if lang_response else []

    return {
        **repo,
        "has_cmake": has_cmake,
        "latest_commit": commit_hash,
        "languages": list(languages),
        "is_valid": has_cmake and ("C" in languages or "C++" in languages),
    }


def main():
    # 获取仓库列表
    print("Fetching repository list...")
    repositories = fetch_repositories()
    print(f"Total repositories found: {len(repositories)}")

    # 并行处理仓库
    print("Processing repositories...")

    results = list(
        thread_map(
            process_repository,
            repositories,
            max_workers=MAX_WORKERS,
            desc="Processing repos",
            unit="repo",
        )
    )

    # 分类结果
    valid_repos = [r for r in results if r["is_valid"]]
    excluded_repos = [r for r in results if not r["is_valid"]]

    # 添加时间戳
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # 保存结果
    with open(f"{OUTPUT_DIR}/cmake_repos.json", "w") as f:
        json.dump(valid_repos, f, indent=2)

    with open(f"{OUTPUT_DIR}/excluded_repos.json", "w") as f:
        json.dump(excluded_repos, f, indent=2)

    # 输出统计
    print("\nResults:")
    print(f"Valid repositories: {len(valid_repos)}")
    print(f"Excluded repositories: {len(excluded_repos)}")
    print(f"Output files saved with timestamp: {timestamp}")


if __name__ == "__main__":
    main()
