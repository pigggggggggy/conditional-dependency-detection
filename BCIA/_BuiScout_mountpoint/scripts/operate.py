import json
import logging
import os
import shutil
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from tqdm.contrib.concurrent import thread_map

# 配置参数
MAX_WORKERS = 8
MOUNT_POINT = Path("/_BuiScout_mountpoint")
KEEP_ARTIFACTS = False
TIMEOUT = 60 * 60

# 路径配置
BUISCOUT_RESULTS_RELATIVE_PATH = "output/buiscout_results"
BUISCOUT_RESULTS_DIR = MOUNT_POINT / BUISCOUT_RESULTS_RELATIVE_PATH
CMAKE_REPO_FILE = MOUNT_POINT / "output" / "repo" / "cmake_repos.json"
CONFIG_FILE = MOUNT_POINT / "config.json"
CONFIG_FOLDER = MOUNT_POINT / "buiscout_config"
EXTRACT_SCRIPT = Path("extract_dependencies.py").resolve()
EXTRACT_RESULTS_DIR = MOUNT_POINT / "output" / "extraction_results"
LOG_DIR = MOUNT_POINT / "log"

# 日志配置
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            f"{LOG_DIR}/{os.path.basename(__file__)}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def validate_environment():
    """验证环境准备"""
    errors = []

    # 检查挂载点可写
    if not MOUNT_POINT.exists():
        errors.append(f"MOUNT_POINT does not exist: {MOUNT_POINT}")
    elif not os.access(MOUNT_POINT, os.W_OK):
        errors.append(f"MOUNT_POINT is not writable: {MOUNT_POINT}")

    # 检查关键文件
    required_files = {
        "CMake Repositories File": CMAKE_REPO_FILE,
        "Config File": CONFIG_FILE,
        "Extract Dependencies Script": EXTRACT_SCRIPT,
    }
    for name, path in required_files.items():
        if not path.exists():
            errors.append(f"{name} does not exist: {path}")

    if errors:
        logger.error("Environment validation failed:\n" + "\n".join(errors))
        raise RuntimeError("Environment validation failed. Please check the logs.")


def load_json_safe(file_path: Path):
    """安全加载JSON文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON file: {file_path}: {str(e)}")
        raise


def process_single_repo(repo_data: dict, base_config: dict) -> bool:
    """处理单个仓库的完整流程"""
    repo_name = repo_data["full_name"]
    logger.info(f"Processing repository: {repo_name}")

    # 创建独立配置
    config = deepcopy(base_config)
    repo_name_path = repo_name.replace("/", "_")

    # 配置路径参数
    relative_path = f"{BUISCOUT_RESULTS_RELATIVE_PATH}/{repo_name_path}"
    output_dir = MOUNT_POINT / relative_path

    try:
        # 更新配置
        config.update(
            {
                "RELATIVE_RESULT_PATH": str(relative_path),
                "PROJECT": repo_name_path,
                "REPOSITORY": f"{repo_data['html_url']}.git",
                "BRANCH": repo_data["default_branch"],
            }
        )

        # 保存配置文件
        repo_config_path = CONFIG_FOLDER / f"{repo_name_path}.json"
        with open(repo_config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.debug(f"Configuration saved for {repo_name}: {repo_config_path}")

        # 执行 scount run 命令
        logger.debug(f"Executing scout run for {repo_name}")
        cmd = [
            "python3",
            "/BuiScout/scout.py",
            "run",
            f"-c={repo_config_path}",
        ]
        logger.debug(f"Scout run command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT,
            check=True,
            text=True,
        )
        logger.debug("Scout run output:")
        logger.debug(result.stdout)

        # 构建文件路径
        cmake_results_dir = (
            output_dir / f"{repo_name_path}_cmake_results" / "system_global" / "commits"
        )
        commit_ids = [
            d
            for d in os.listdir(cmake_results_dir)
            if os.path.isdir(cmake_results_dir / d)
        ]
        commit_id = next((commit for commit in commit_ids if len(commit) == 40), None)
        if not commit_id:
            raise RuntimeError(f"No valid commit ID found in {cmake_results_dir}")
        logger.debug(f"Using commit ID: {commit_id}")

        csv_path = (
            output_dir
            / f"{repo_name_path}_cmake_results/system_global/commits/{commit_id}/data_flow_output/destination_actor_points.csv"
        )
        output_csv = EXTRACT_RESULTS_DIR / f"{repo_name_path}.csv"

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # 执行提取命令
        logger.debug(f"Extracting dependencies for {repo_name}")
        extract_cmd = ["python3", str(EXTRACT_SCRIPT), str(csv_path), str(output_csv)]
        subprocess.run(
            extract_cmd,
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,  # 避免日志污染
        )

        # 验证输出
        if not output_csv.exists():
            raise RuntimeError("Extraction failed, output file not found.")

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout expired for {repo_name}")
        return False
    except Exception as e:
        logger.error(f"Error processing {repo_name}: {str(e)}", exc_info=True)
        return False
    finally:
        # 清理中间文件
        if not KEEP_ARTIFACTS and output_dir.exists():
            logger.debug(f"Cleaning up artifacts for {repo_name}")
            shutil.rmtree(output_dir, ignore_errors=True)


def main():
    # 环境验证
    validate_environment()

    # 准备结果目录
    BUISCOUT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)
    EXTRACT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 加载数据
    repos = load_json_safe(CMAKE_REPO_FILE)
    base_config = load_json_safe(CONFIG_FILE)
    logger.info(f"Loaded {len(repos)} repositories")

    # 并行处理
    logger.info(f"Processing {len(repos)} repositories with {MAX_WORKERS} workers")

    # Define a wrapper function to pass to thread_map
    def process_repo(repo):
        try:
            return process_single_repo(repo, base_config)
        except Exception as e:
            logger.error(
                f"Task exception for {repo['full_name']}: {str(e)}", exc_info=True
            )
            return False

    # Use thread_map with tqdm progress bar
    results = thread_map(
        process_repo,
        repos,
        max_workers=MAX_WORKERS,
        desc="Processing repositories",
        unit="repo",
    )

    # Count successful operations
    success_count = sum(1 for result in results if result)

    # Generate report
    logger.info("\nProcessing Completion Report:")
    logger.info(f"Total repositories: {len(repos)}")
    logger.info(f"Successfully processed: {success_count}")
    logger.info(f"Failed: {len(repos) - success_count}")
    logger.info(f"Results directory: {EXTRACT_RESULTS_DIR}")


if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logger.critical(f"Main program exception: {str(e)}", exc_info=True)
        exit(1)
    finally:
        logger.info(f"Total execution time: {time.time() - start_time:.2f} seconds")


# def update_and_run(repos, config_template):
#     """逐个更新 config.json 并执行 scout test"""
#     for repo in repos:
#         full_name = repo["full_name"]
#         project_name = full_name.split("/")[-1]
#         repo_url = repo["html_url"] + ".git"
#         branch = repo["default_branch"]
#         commit = [repo["latest_commit"]]

#         config_template["RELATIVE_RESULT_PATH"] = results_dir + full_name.replace(
#             "/", "_"
#         )
#         config_template["PROJECT"] = project_name
#         config_template["REPOSITORY"] = repo_url
#         config_template["BRANCH"] = branch
#         config_template["COMMITS"] = commit

#         save_json(config_template, config_file)

#         print(f"Running: scout run for {full_name}")
#         subprocess.run(["python3", "/BuiScout/scout.py", "run"])

#         relative_result_path = config_template["RELATIVE_RESULT_PATH"]
#         project = full_name.replace(
#             "/", "_"
#         )
#         commit_id = config_template["COMMITS"][0]

#         command = [
#             "python3",
#             extract_dependencies_script,
#             f"/_BuiScout_mountpoint/{relative_result_path}/{project_name}_cmake_results/system_global/commits/{commit_id}/data_flow_output/destination_actor_points.csv",
#             f"/_BuiScout_mountpoint/output/extraction_results/{project}.csv",
#         ]

#         print(f"Running: {command}")
#         subprocess.run(command)

#         # folder_to_delete = f"/_BuiScout_mountpoint/{relative_result_path}"
#         # if os.path.exists(folder_to_delete):
#         #     print(f"Deleting folder: {folder_to_delete}")
#         #     shutil.rmtree(folder_to_delete)
#         # else:
#         #     print(f"Folder {folder_to_delete} does not exist, skipping deletion.")


# if __name__ == "__main__":
#     repos_data = load_json(cpp_repos_file)
#     config_data = load_json(config_file)

#     update_and_run(repos_data, config_data)
