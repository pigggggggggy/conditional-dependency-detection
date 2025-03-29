import json
import logging
import os
import shutil
import subprocess
import time
from copy import deepcopy
from pathlib import Path

from tqdm.contrib.concurrent import process_map

# 配置参数
CONFIG = {
    "MAX_WORKERS": int(os.getenv("MAX_WORKERS", "8")),  # 并发线程数
    "MOUNT_POINT": Path(os.getenv("BUISCOUT_MOUNT", "/_BuiScout_mountpoint")),
    "KEEP_ARTIFACTS": os.getenv("KEEP_ARTIFACTS", "false").lower() == "true",
    "TIMEOUT": int(os.getenv("PROCESS_TIMEOUT", "600")),  # 单个任务超时时间(秒)
    "BASE_RESULTS": Path("../results").resolve(),
}

# 路径配置
CPP_REPOS_FILE = Path("cpp_repos_with_commits.json")
CONFIG_FILE = CONFIG["MOUNT_POINT"] / "config.json"
EXTRACT_SCRIPT = Path("extract_dependencies.py").resolve()

# 日志配置Z
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("processing.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def validate_environment():
    """验证环境准备"""
    errors = []

    # 检查挂载点可写
    if not CONFIG["MOUNT_POINT"].exists():
        errors.append(f"挂载点不存在: {CONFIG['MOUNT_POINT']}")
    elif not os.access(CONFIG["MOUNT_POINT"], os.W_OK):
        errors.append(f"挂载点不可写: {CONFIG['MOUNT_POINT']}")

    # 检查关键文件
    required_files = {"仓库数据文件": CPP_REPOS_FILE, "提取脚本": EXTRACT_SCRIPT}
    for name, path in required_files.items():
        if not path.exists():
            errors.append(f"{name}不存在: {path}")

    if errors:
        logger.error("环境验证失败:\n" + "\n".join(errors))
        raise RuntimeError("环境配置错误")


def load_json_safe(file_path: Path):
    """安全加载JSON文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON失败 {file_path}: {str(e)}")
        raise


def process_single_repo(repo_data: dict, base_config: dict) -> bool:
    """处理单个仓库的完整流程"""
    repo_name = repo_data["full_name"]
    logger.info(f"开始处理仓库: {repo_name}")

    # 创建独立配置
    config = deepcopy(base_config)
    project = repo_name.split("/")[-1]

    # 配置路径参数
    relative_path = Path(repo_name.replace("/", "_"))  # 防止路径注入
    output_dir = CONFIG["MOUNT_POINT"] / relative_path

    try:
        # 更新配置
        config.update(
            {
                "RELATIVE_RESULT_PATH": str(relative_path),
                "PROJECT": project,
                "REPOSITORY": f"{repo_data['html_url']}.git",
                "BRANCH": repo_data["default_branch"],
                "COMMITS": [repo_data["latest_commit"]],
            }
        )

        # 保存配置文件
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

        # 执行测试命令
        logger.debug(f"执行scout测试: {repo_name}")
        test_cmd = ["python3", "/BuiScout/scout.py", "test"]
        result = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=CONFIG["TIMEOUT"],
            check=True,
            text=True,
        )
        logger.debug(f"测试输出:\n{result.stdout[:500]}...")  # 截断长日志

        # 构建文件路径
        commit_id = repo_data["latest_commit"][:7]  # 使用短commit ID
        csv_path = (
            output_dir
            / f"{project}_cmake_results/system_global/commits/{commit_id}/data_flow_output/destination_actor_points.csv"
        )
        output_csv = CONFIG["BASE_RESULTS"] / f"{project}.csv"

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV文件未生成: {csv_path}")

        # 执行提取命令
        logger.debug(f"提取依赖数据: {repo_name}")
        extract_cmd = ["python3", str(EXTRACT_SCRIPT), str(csv_path), str(output_csv)]
        subprocess.run(
            extract_cmd,
            check=True,
            timeout=300,
            stdout=subprocess.DEVNULL,  # 避免日志污染
        )

        # 验证输出
        if not output_csv.exists():
            raise RuntimeError("依赖提取未生成输出文件")

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"处理超时: {repo_name}")
        return False
    except Exception as e:
        logger.error(f"处理失败 {repo_name}: {str(e)}", exc_info=True)
        return False
    finally:
        # 清理中间文件
        if not CONFIG["KEEP_ARTIFACTS"] and output_dir.exists():
            logger.debug(f"清理中间文件: {output_dir}")
            shutil.rmtree(output_dir, ignore_errors=True)


def main():
    # 环境验证
    validate_environment()

    # 准备结果目录
    CONFIG["BASE_RESULTS"].mkdir(parents=True, exist_ok=True)

    # 加载数据
    repos = load_json_safe(CPP_REPOS_FILE)
    base_config = load_json_safe(CONFIG_FILE)
    logger.info(f"成功加载 {len(repos)} 个仓库")

    # Define a wrapper function to handle the arguments format for process_map
    def process_repo_wrapper(repo):
        return process_single_repo(repo, base_config)

    # Use process_map with progress bar
    results = process_map(
        process_repo_wrapper,
        repos,
        max_workers=CONFIG["MAX_WORKERS"],
        desc="Processing repositories",
        chunksize=1,
    )

    # Count successful operations
    success_count = sum(results)

    # 生成报告
    logger.info("\n处理完成报告:")
    logger.info(f"总仓库数: {len(repos)}")
    logger.info(f"成功处理: {success_count}")
    logger.info(f"失败数量: {len(repos) - success_count}")
    logger.info(f"结果文件目录: {CONFIG['BASE_RESULTS']}")


if __name__ == "__main__":
    start_time = time.time()
    try:
        main()
    except Exception as e:
        logger.critical(f"主程序异常: {str(e)}", exc_info=True)
        exit(1)
    finally:
        logger.info(f"总运行时间: {time.time() - start_time:.2f}秒")
