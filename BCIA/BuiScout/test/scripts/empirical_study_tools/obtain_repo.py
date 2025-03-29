import requests
import json
import time

BASE_URL = "https://api.github.com/search/repositories"
GITHUB_TOKEN = ""  
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

QUERY = "stars:>100 language:C++ language:C"
PARAMS = {
    "q": QUERY,
    "sort": "stars",
    "order": "desc",
    "per_page": 100,  
    "page": 1  
}


MAX_REPOS = 30
repositories = []
excluded_repositories = []  


def get_latest_commit_hash(repo, branch="main"):
    """
    获取指定 GitHub 仓库的最新 commit hash
    """
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        return response.json()["sha"]  
    else:
        print(f"Failed to fetch commit for {repo}: {response.status_code} - {response.text}")
        return None


def has_cmakelists(repo):
    """
    检查仓库是否包含 CMakeLists.txt
    """
    url = f"https://api.github.com/repos/{repo}/contents/CMakeLists.txt"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        return True  
    elif response.status_code == 404:
        return False 
    else:
        print(f"Failed to check CMakeLists.txt for {repo}: {response.status_code} - {response.text}")
        return False



while len(repositories) < MAX_REPOS:
    print(f"Fetching page {PARAMS['page']} ...")
    response = requests.get(BASE_URL, params=PARAMS, headers=HEADERS)
    
    if response.status_code != 200:
        print("Error:", response.json())
        break

    data = response.json()
    if "items" in data:
        for repo in data["items"]:
            repo_info = {
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "default_branch": repo["default_branch"],
                "latest_commit": None  
            }
            repositories.append(repo_info)

    if len(data["items"]) < 100:
        break
    

    PARAMS["page"] += 1


    if len(repositories) >= MAX_REPOS:
        break


repositories = repositories[:MAX_REPOS]

filtered_repositories = []  


for repo in repositories:
    time.sleep(1)  
    
    if has_cmakelists(repo["full_name"]):
        repo["latest_commit"] = get_latest_commit_hash(repo["full_name"], repo["default_branch"])
        filtered_repositories.append(repo)
    else:
        excluded_repositories.append(repo)


with open("cpp_repos_with_commits.json", "w", encoding="utf-8") as f:
    json.dump(filtered_repositories, f, indent=4)

with open("excluded.json", "w", encoding="utf-8") as f:
    json.dump(excluded_repositories, f, indent=4)

print(f"Total repositories checked: {len(repositories)}")
print(f"Repositories with CMakeLists.txt: {len(filtered_repositories)}")
print(f"Repositories without CMakeLists.txt: {len(excluded_repositories)}")
