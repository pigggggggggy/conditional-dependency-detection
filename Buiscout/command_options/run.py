def run_BuiScout():
    from multiprocessing import Process
    from pydriller import Repository
    from pydriller.git import Git
    from tqdm import tqdm
    import pandas as pd
    import gc, shutil, importlib
    from datetime import datetime
    from utils.exceptions import DebugException
    from utils.helpers import (
        create_csv_files,
        file_is_target,
        clear_existing_data,
        clear_repo_location,
    )
    from utils.configurations import (
        RESOURCE_CONTROL,
        COMMIT_SERIES,
        AST_DIFFS_REUSE,
        PROGRESS_RESET,
        ROOT_PATH,
        SAVE_PATH,
        CLEAN_TRACES,
        REPOSITORY,
        PROJECT,
        BRANCH,
        COMMITS,
        EXCLUDED_COMMITS,
        LANGUAGES,
        ENTRY_FILES,
        PATTERN_SETS,
        PATTERNS_FLATTENED,
        FILTERING,
        PROJECT_MODEL,
        DATA_FLOW_ANALYSIS_MODE,
    )

    SAVE_PATH = (
        SAVE_PATH
        / f"system_{DATA_FLOW_ANALYSIS_MODE.lower()}{'_series' if COMMIT_SERIES else ''}"
    )
    COMMITS_SAVE_PATH = SAVE_PATH / "commits"
    COMMITS_SAVE_PATH.mkdir(parents=True, exist_ok=True)

    if COMMIT_SERIES:
        from system_commit_model import SystemDiffSeries as SystemDiffModel

        # Clear existing code and gumtree outputs
        clear_existing_data(SAVE_PATH)
    elif AST_DIFFS_REUSE:
        from system_commit_model import SystemDiffShortcut as SystemDiffModel
    else:
        from system_commit_model import SystemDiff as SystemDiffModel
    # Overwrite if project specific models are actiavted and exist
    if PROJECT_MODEL:
        project_specific_support_path = ROOT_PATH / "project_specific_support" / PROJECT
        if project_specific_support_path.exists():
            if COMMIT_SERIES:
                SystemDiffModel = importlib.import_module(
                    f"project_specific_support.{PROJECT}"
                ).SystemDiffSeries
                # Clear existing code and gumtree outputs
                clear_existing_data(SAVE_PATH)
            elif AST_DIFFS_REUSE:
                SystemDiffModel = importlib.import_module(
                    f"project_specific_support.{PROJECT}"
                ).SystemDiffShortcut
            else:
                SystemDiffModel = importlib.import_module(
                    f"project_specific_support.{PROJECT}"
                ).SystemDiff

    def analyze_commit(
        REPOSITORY,
        repo,
        git_repo,
        BRANCH,
        commit,
        ENTRY_FILES,
        LANGUAGE,
        PATTERNS,
        ROOT_PATH,
        SAVE_PATH,
    ):
        diff = SystemDiffModel(
            REPOSITORY,
            repo,
            git_repo,
            BRANCH,
            commit,
            ENTRY_FILES,
            LANGUAGE,
            PATTERNS,
            ROOT_PATH,
            SAVE_PATH,
        )

        diff.export_csv(propagation_slice_mode=True)

        commit_build_files_df = pd.DataFrame(list(diff.file_data.values()))
        commit_build_files_df.drop(
            labels=["diff", "language_specific_info"],
            axis=1,
            inplace=True,
        )
        commit_build_files_df.to_csv(
            SAVE_PATH / "all_build_files.csv", mode="a", header=False, index=False
        )

        del diff
        gc.collect()

    if PROGRESS_RESET:
        create_csv_files(SAVE_PATH)
        completed_commits = []
    else:
        try:
            completed_commits = pd.read_csv(SAVE_PATH / "all_commits.csv")
            completed_commits = list(completed_commits.commit_hash.unique())
        except:
            completed_commits = []
            create_csv_files(SAVE_PATH)

    repo = Repository(
        REPOSITORY,
        only_modifications_with_file_types=(
            PATTERNS_FLATTENED["include"] if FILTERING else None
        ),  # See EXCEPTION_HANDLING_GitPython in comments within code
        only_commits=COMMITS,
        only_in_branch=BRANCH,
        # order="reverse",  # Orders commits from newest to oldest, default behaviour is desired (oldest to newest)
    )
    git_repo = Git(REPOSITORY)

    all_commits_start = datetime.now()

    # Run tool on commits
    chronological_commit_order = 0
    for commit in tqdm(repo.traverse_commits()):
        print(f"Commit in process: {commit.hash}")
        if commit.hash in completed_commits:
            print("Commit previously analyzed.")
            chronological_commit_order += 1
            continue
        # Commit-level attributes that show whether the commit
        # has affected build/non-build files
        has_build = False
        has_nonbuild = False

        # Start analysis of the commit
        commit_start = datetime.now()

        # EXCEPTION_HANDLING_GitPython
        # Error handling for missing commits
        # GitPython, and consequently PyDriller,
        # do not handle this well.
        # Although PyDriller offers the
        # only_modifications_with_file_types option,
        # using such filtering throws an error if the
        # commit is missing as GitPython attempts an access
        # to the commit when iterating over the commits.
        # In practice, this does not provide any
        # performance improvements either, as the
        # traversal takes place by iterating over
        # all the commits and just skipping the ones
        # filtered based on user's specifications.
        # This is why use of
        # "INITIALIZE_WITH_BUILD_COMMITS": "NO" is recommended
        # in the configurations.
        try:
            # This will throw an error if the commit is missing
            commit.modified_files
        except AttributeError:
            # Clear existing code and gumtree outputs
            if COMMIT_SERIES:
                clear_existing_data(SAVE_PATH)
            if not (commit.hash in EXCLUDED_COMMITS):
                raise DebugException(
                    f"Submodule commit {commit.hash} must be excluded from analysis."
                )
            continue
        except ValueError:
            # Clear existing code and gumtree outputs
            if COMMIT_SERIES:
                clear_existing_data(SAVE_PATH)
            if not (commit.hash in EXCLUDED_COMMITS):
                raise DebugException(
                    f"Missing commit {commit.hash} must be excluded from analysis."
                )
            continue

        # Identify if the commit has non-build modifications
        for modified_file in commit.modified_files:
            if not file_is_target(modified_file, PATTERNS_FLATTENED):
                has_nonbuild = True
                break

        # Iterate over the languages and file naming conventions
        # supported by the build system
        for LANGUAGE in LANGUAGES:
            has_current_build = False
            PATTERNS = PATTERN_SETS[LANGUAGE]
            has_build = True
            has_current_build = True

            if has_current_build:
                # Save time by skipping
                if commit.hash in EXCLUDED_COMMITS:
                    to_remove = SAVE_PATH / "commits" / commit.hash
                    if to_remove.exists():
                        shutil.rmtree(to_remove)
                    continue

                if RESOURCE_CONTROL:
                    analyzer = Process(
                        target=analyze_commit,
                        args=[
                            REPOSITORY,
                            repo,
                            git_repo,
                            BRANCH,
                            commit,
                            ENTRY_FILES,
                            LANGUAGE,
                            PATTERNS,
                            ROOT_PATH,
                            SAVE_PATH,
                        ],
                    )
                    analyzer.start()
                    analyzer.join()
                else:
                    analyze_commit(
                        REPOSITORY,
                        repo,
                        git_repo,
                        BRANCH,
                        commit,
                        ENTRY_FILES,
                        LANGUAGE,
                        PATTERNS,
                        ROOT_PATH,
                        SAVE_PATH,
                    )
                    gc.collect()

        # Don't log if excluded
        if commit.hash in EXCLUDED_COMMITS:
            continue

        chronological_commit_order += 1
        # Log all changes
        commit_data_df = pd.DataFrame(
            {
                "commit_hash": [commit.hash],
                "chronological_commit_order": [chronological_commit_order],
                "commit_parents": [commit.parents],
                "has_build": [has_build],
                "has_nonbuild": [has_nonbuild],
                "is_missing": [False],
                "elapsed_time": [datetime.now() - commit_start],
            }
        )
        commit_data_df.to_csv(
            SAVE_PATH / "all_commits.csv", mode="a", header=False, index=False
        )

    # Checkout to head once done.
    # This is currently disabled in
    # system_commit_mode/sustem_diff_mode.py/SystemDiff()
    # for performance improvement.
    git_repo.checkout(BRANCH)

    # Clear existing code and gumtree outputs
    if COMMIT_SERIES:
        clear_existing_data(SAVE_PATH)

    if CLEAN_TRACES:
        clear_repo_location(REPOSITORY)

    print(f"Finished processing in {datetime.now()-all_commits_start}")
