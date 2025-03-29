import json
import subprocess
import os
import shutil

cpp_repos_file = "cpp_repos_with_commits.json"
config_file = "/_BuiScout_mountpoint/config.json"
extract_dependencies_script = "extract_dependencies.py"


def load_json(file_path):
    """读取 JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, file_path):
    """保存 JSON 文件"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_and_run(repos, config_template):
    """逐个更新 config.json 并执行 scout test"""
    for repo in repos:
        full_name = repo["full_name"]
        project_name = full_name.split("/")[-1]
        repo_url = repo["html_url"] + ".git"
        branch = repo["default_branch"]
        commit = [repo["latest_commit"]]

        config_template["RELATIVE_RESULT_PATH"] = full_name
        config_template["PROJECT"] = project_name
        config_template["REPOSITORY"] = repo_url
        config_template["BRANCH"] = branch
        config_template["COMMITS"] = commit

        save_json(config_template, config_file)

        print(f"Running: scout test for {full_name}")
        subprocess.run(["python3", "/BuiScout/scout.py", "test"])

        relative_result_path = config_template["RELATIVE_RESULT_PATH"]
        project = config_template["PROJECT"]
        commit_id = config_template["COMMITS"][0]

        command = [
            "python3",
            extract_dependencies_script,
            f"/_BuiScout_mountpoint/{relative_result_path}/{project}_cmake_results/system_global/commits/{commit_id}/data_flow_output/destination_actor_points.csv",
            f"../results/{project}.csv",
        ]

        print(f"Running: {command}")
        subprocess.run(command)

        folder_to_delete = f"/_BuiScout_mountpoint/{relative_result_path}"
        if os.path.exists(folder_to_delete):
            print(f"Deleting folder: {folder_to_delete}")
            shutil.rmtree(folder_to_delete)
        else:
            print(f"Folder {folder_to_delete} does not exist, skipping deletion.")


if __name__ == "__main__":
    repos_data = load_json(cpp_repos_file)
    config_data = load_json(config_file)

    update_and_run(repos_data, config_data)
