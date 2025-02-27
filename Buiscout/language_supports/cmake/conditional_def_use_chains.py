import data_flow_analysis as cm
import pandas as pd
from utils.configurations import (
    PROJECT_SPECIFIC_PATH_RESOLUTION,
    ROOT_PATH,
    EXECUTE_CALLABLES,
    VERBOSE,
)
from utils.exceptions import MissingArgumentsException, DebugException

# CMake Modules based on the official documentation
# https://cmake.org/cmake/help/v3.27/manual/cmake-modules.7.html
with open(ROOT_PATH / "language_supports/cmake/cmake_modules.txt", "r") as f:
    CMAKE_MODULES = list(map(lambda entry: entry.strip("\n"), f.readlines()))

# TODO (HIGH): Look into ${ARGN} logic for arguments.


class ConditionalDefUseChains(cm.ConditionalDefUseChains):
    manual_resolution = PROJECT_SPECIFIC_PATH_RESOLUTION
    exclude_resolutions = CMAKE_MODULES

    def register_new_def_point(
        self,
        def_node_data,
        actor_point,
        def_type="VAR",
        prefix=None,
        suffix=None,
        preferred_name=None,
    ):
        # TODO (High): DELIVERABLES must also be globally defined,
        # but currently, thier name can be a var ref, making them
        # not unique. If we rely on the order of referencing them,
        # different scopes and different reachability conditions
        # can mess with access.
        target_scope = self
        if def_type in ["FUNCTION", "MACRO"]:
            target_scope = self.global_scope

            defined = target_scope.get_definitions_by_name(
                self.ast.get_name(def_node_data)
            )
            if len(defined) > 0:
                node_ids = list(map(lambda point: point.node_data["id"], defined))
                if def_node_data["id"] in node_ids:
                    return None

        def_point = target_scope.Def(
            def_node_data,
            def_type,
            actor_point,
            self.ast,
            prefix=prefix,
            suffix=suffix,
            preferred_name=preferred_name,
            scope=self.scope,
            file=self.ast.file_saved_as,
        )
        actor_point.add_def_point(def_point)
        target_scope.def_points[def_point.node_data["id"]].append(def_point)
        target_scope.defined_names[def_point.name].append(def_point)
        return def_point

    def compare_reachability_conditions(self, def_point, use_point):
        """
        Consumes the def_point (or the def reachability stack) and
        the use_point (or the use reachability stack) objects and returns:
                    "=" (equal reachability condition)
                    "<" (def reachability is subset of use reachability)
                    ">" (use reachability is subset of def reachability)
                    "!" (contradiction exists in reachabilities)
                    "?" (unable to find a concrete relation between)

        The comparison is NAIVE.
        """
        if isinstance(def_point, list) and isinstance(use_point, list):
            def_conditions = set(def_point)
            use_conditions = set(def_point)
        else:
            if def_point.type == "PROPERTY" or use_point.type == "PROPERTY":
                return "?"

            def_conditions = set(def_point.actor_point.reachability)
            use_conditions = set(use_point.actor_point.reachability)

        def_conditions.difference_update({""})
        use_conditions.difference_update({""})

        if def_conditions == use_conditions:
            return "="
        if def_conditions.issubset(use_conditions):
            return "<"
        if use_conditions.issubset(def_conditions):
            return ">"

        if set(map(lambda cond: f"NOT ({cond})", def_conditions)).intersection(
            use_conditions
        ):
            return "!"
        if set(map(lambda cond: f"NOT ({cond})", use_conditions)).intersection(
            def_conditions
        ):
            return "!"

        return "?"

    def get_expected_arguments_node_data(self, command_node_data, command_id):
        """
        Retruns the "arguments" node's node_data (the parent of the list of arguments).
        Throws MissingArgumentsException if the node does not exist.
        """
        arguments_node_data = self.ast.get_data(
            self.ast.get_children_by_type(command_node_data, "arguments")
        )
        if not arguments_node_data:
            raise MissingArgumentsException(
                command_id, self.ast.get_location(command_node_data)
            )
        return arguments_node_data

    def get_sorted_arguments_data_list(self, command_node_data, command_id):
        """
        Returns the list of argument nodes' node_data of the command node, sorted by position.
        """
        # Check for MissingArgumentsException
        arguments_node_data = self.get_expected_arguments_node_data(
            command_node_data, command_id
        )

        # node_data of each argument, positionally sorted
        return sorted(
            self.ast.get_children(arguments_node_data).values(),
            key=lambda argument_node_data: argument_node_data["s_pos"],
        )

    def get_manually_resolved_path(self, file_path_node):
        """
        Returns (success_flag, resolution)
        """
        if len(self.manual_resolution)==0:
            return False, None
        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")

        resolved_path_item = list(
            filter(
                lambda item: (item["caller_file_path"] in [self.ast.file_path, "*"])
                and (item["callee_file_path"] == file_path),
                self.manual_resolution,
            )
        )
        if len(resolved_path_item) == 1:
            return True, resolved_path_item[0]["callee_resolved_path"]
        if len(resolved_path_item) > 1:
            raise Exception(
                "Please make sure you do not provide two PROJECT_SPECIFIC_PATH_RESOLUTION items with the same caller_file_path and callee_file_path."
            )
        return False, None

    def resolve_find_package_module_mode_file_path(self, file_path_node):
        """
        Returns (success_flag, resolution)

        module_mode:
        Find<PackageName>.cmake
        """
        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")
        candidate_path = file_path.split("}")[-1]
        if not candidate_path:
            return False, None
        candidate_path = candidate_path.strip("./")
        candidate_path = "Find" + candidate_path + ".cmake"

        current_directory = (
            self.sysdiff.get_file_directory(self.ast.file_path, self.ast.name).strip(
                "/"
            )
            + "/"
        )
        if current_directory == "/":
            current_directory = ""

        resolution_map = self.sysdiff.file_path_resolution_map[self.ast.name]

        if current_directory + candidate_path in resolution_map:
            return True, [resolution_map[current_directory + candidate_path]]

        if candidate_path in resolution_map:
            return True, [resolution_map[candidate_path]]

        file_keys = list(
            map(
                lambda file_key: ("/" + file_key.strip("/")),
                resolution_map.keys(),
            )
        )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + current_directory + candidate_path
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith("/" + candidate_path),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        return False, None

    def resolve_find_package_config_mode_file_path(self, file_path_node):
        """
        Returns (success_flag, resolution)

        config_mode (multiple package names):
        <PackageName>Config.cmake
        <PackageName>ConfigVersion.cmake
        <lowercasePackageName>-config.cmake
        <lowercasePackageName>-config-version.cmake
        """
        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")
        candidate_path = file_path.split("}")[-1]
        if not candidate_path:
            return False, None
        candidate_path = candidate_path.strip("./")
        candidate_paths = [
            candidate_path + "Config.cmake",
            candidate_path + "ConfigVersion.cmake",
            candidate_path.lower() + "-config.cmake",
            candidate_path.lower() + "-config-version.cmake",
        ]

        current_directory = (
            self.sysdiff.get_file_directory(self.ast.file_path, self.ast.name).strip(
                "/"
            )
            + "/"
        )
        if current_directory == "/":
            current_directory = ""

        resolution_map = self.sysdiff.file_path_resolution_map[self.ast.name]

        success = False
        found_files = []
        for candidate_path in candidate_paths:
            if current_directory + candidate_path in resolution_map:
                success = True
                found_files.append(resolution_map[current_directory + candidate_path])

            if candidate_path in resolution_map:
                success = True
                found_files.append(resolution_map[candidate_path])

            file_keys = list(
                map(
                    lambda file_key: ("/" + file_key.strip("/")),
                    resolution_map.keys(),
                )
            )

            desparate_list = list(
                filter(
                    lambda file_key: file_key.endswith(
                        "/" + current_directory + candidate_path
                    ),
                    file_keys,
                )
            )
            if desparate_list:
                success = True
                found_files = found_files + list(
                    map(
                        lambda file_key: resolution_map[file_key.strip("/")],
                        desparate_list,
                    )
                )

            desparate_list = list(
                filter(
                    lambda file_key: file_key.endswith("/" + candidate_path),
                    file_keys,
                )
            )
            if desparate_list:
                success = True
                found_files = found_files + list(
                    map(
                        lambda file_key: resolution_map[file_key.strip("/")],
                        desparate_list,
                    )
                )

        if success:
            return True, found_files

        return False, None

    def resolve_find_package_fetch_mode_file_path(self, file_path_node):
        """
        Returns (success_flag, resolution)

        fetch_mode:
        <PackageName>.cmake
        """
        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")
        candidate_path = file_path.split("}")[-1]
        if not candidate_path:
            return False, None
        candidate_path = candidate_path.strip("./")
        candidate_path = candidate_path + ".cmake"

        current_directory = (
            self.sysdiff.get_file_directory(self.ast.file_path, self.ast.name).strip(
                "/"
            )
            + "/"
        )
        if current_directory == "/":
            current_directory = ""

        resolution_map = self.sysdiff.file_path_resolution_map[self.ast.name]

        if current_directory + candidate_path in resolution_map:
            return True, [resolution_map[current_directory + candidate_path]]

        if candidate_path in resolution_map:
            return True, [resolution_map[candidate_path]]

        file_keys = list(
            map(
                lambda file_key: ("/" + file_key.strip("/")),
                resolution_map.keys(),
            )
        )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + current_directory + candidate_path
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith("/" + candidate_path),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        return False, None

    def resolve_find_package_file_path(
        self, file_path_node, module_mode=True, confi_mode=True, fetch_mode=True
    ):
        """
        Returns (success_flag, resolution)

        module_mode:
        Find<PackageName>.cmake

        config_mode (multiple package names):
        <lowercasePackageName>-config.cmake
        <PackageName>Config.cmake
        <lowercasePackageName>-config-version.cmake
        <PackageName>ConfigVersion.cmake

        fetch_mode:
        <PackageName>.cmake
        """
        manual_success, resolution = self.get_manually_resolved_path(file_path_node)
        if manual_success:
            return True, list(set(resolution))

        if module_mode:
            (
                m_success,
                m_resolutions,
            ) = self.resolve_find_package_module_mode_file_path(file_path_node)
            if not m_success:
                m_resolutions = []
        else:
            m_success = False
            m_resolutions = []

        if confi_mode:
            (
                c_success,
                c_resolutions,
            ) = self.resolve_find_package_config_mode_file_path(file_path_node)
            if not c_success:
                c_resolutions = []
        else:
            c_success = False
            c_resolutions = []

        if fetch_mode:
            (
                f_success,
                f_resolutions,
            ) = self.resolve_find_package_fetch_mode_file_path(file_path_node)
            if not f_success:
                f_resolutions = []
        else:
            f_success = False
            f_resolutions = []

        return (
            m_success or c_success or f_success,
            list(set(m_resolutions + c_resolutions + f_resolutions)),
        )

    def resolve_include_file_path(self, file_path_node):
        """
        Returns (success_flag, resolution)
        """
        manual_success, resolution = self.get_manually_resolved_path(file_path_node)
        if manual_success:
            return True, resolution

        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")
        candidate_path = file_path.split("}")[-1]
        if not candidate_path:
            return False, None
        candidate_path = candidate_path.strip("./")

        current_directory = (
            self.sysdiff.get_file_directory(self.ast.file_path, self.ast.name).strip(
                "/"
            )
            + "/"
        )
        if current_directory == "/":
            current_directory = ""

        resolution_map = self.sysdiff.file_path_resolution_map[self.ast.name]

        if current_directory + candidate_path in resolution_map:
            return True, [resolution_map[current_directory + candidate_path]]

        if current_directory + candidate_path + ".cmake" in resolution_map:
            return True, [resolution_map[current_directory + candidate_path + ".cmake"]]

        if candidate_path in resolution_map:
            return True, [resolution_map[candidate_path]]

        if candidate_path + ".cmake" in resolution_map:
            return True, [resolution_map[candidate_path + ".cmake"]]

        file_keys = list(
            map(
                lambda file_key: ("/" + file_key.strip("/")),
                resolution_map.keys(),
            )
        )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + current_directory + candidate_path
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + current_directory + candidate_path + ".cmake"
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith("/" + candidate_path),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith("/" + candidate_path + ".cmake"),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        return False, None

    def resolve_add_subdirectory_file_path(self, file_path_node):
        """
        Returns (success_flag, resolution)
        """
        manual_success, resolution = self.get_manually_resolved_path(file_path_node)
        if manual_success:
            return True, resolution

        file_path = self.ast.unparse(file_path_node)
        file_path = file_path.strip('"').strip("'")
        file_path = file_path.replace(" ", "")
        candidate_path = file_path.split("}")[-1]
        if not candidate_path:
            return False, None
        candidate_path = candidate_path.strip("./")

        current_directory = (
            self.sysdiff.get_file_directory(self.ast.file_path, self.ast.name).strip(
                "/"
            )
            + "/"
        )
        if current_directory == "/":
            current_directory = ""

        resolution_map = self.sysdiff.file_path_resolution_map[self.ast.name]

        if current_directory + candidate_path + "/CMakeLists.txt" in resolution_map:
            return True, [
                resolution_map[current_directory + candidate_path + "/CMakeLists.txt"]
            ]

        if candidate_path + "/CMakeLists.txt" in resolution_map:
            return True, [resolution_map[candidate_path + "/CMakeLists.txt"]]

        file_keys = list(
            map(
                lambda file_key: ("/" + file_key.strip("/")),
                resolution_map.keys(),
            )
        )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + current_directory + candidate_path + "/CMakeLists.txt"
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        desparate_list = list(
            filter(
                lambda file_key: file_key.endswith(
                    "/" + candidate_path + "/CMakeLists.txt"
                ),
                file_keys,
            )
        )
        if desparate_list:
            return True, list(
                map(
                    lambda file_key: resolution_map[file_key.strip("/")], desparate_list
                )
            )

        return False, None

    def log_file_path_resolution(self, command, log_type, node_data, found_paths=[]):
        sep = "\n\t\t"
        if VERBOSE:
            if log_type == "EXCLUDE_CMAKE_MODULE":
                print(
                    f"{command} resolution excluded a CMake module for {self.ast.unparse(node_data)} called from {self.ast.file_path}\n\tresolved to {found_paths[0]}"
                )
            elif log_type == "MANUAL_SKIP":
                print(
                    f"{command} resolution skipping manually set for {self.ast.unparse(node_data)} called from {self.ast.file_path}"
                )
            return
        else:
            if log_type == "NOT_FOUND":
                print(
                    f"{command} resolution cannot resolve path for {self.ast.unparse(node_data)} called from {self.ast.file_path}"
                )
            elif log_type == "MULTIPLE_PATH":
                print(
                    f"{command} resolution found multiple paths for {self.ast.unparse(node_data)} called from {self.ast.file_path}\n\tresolved to \n\t\t{sep.join(found_paths)}"
                )
            elif log_type == "PARSER_ERROR":
                print(
                    f"{command} resolution skipping a file with parser error for {self.ast.unparse(node_data)} called from {self.ast.file_path}\n\tresolved to {found_paths[0]}"
                )
            elif log_type == "RECURSION":
                print(
                    f"{command} resolution lead to recursive invocation for {self.ast.unparse(node_data)} called from {self.ast.file_path}\n\tresolved to {found_paths[0]}"
                )
            elif log_type == "ENTRY_POINT":
                print(
                    f"{command} resolution lead to project's entry point for {self.ast.unparse(node_data)} called from {self.ast.file_path}\n\ttresolved to {found_paths[0]}"
                )
            return

    def visit_function_definition(self, node_data, *args, **kwargs):
        """
        #CALLABLE_DEF_SITE_NOTICE:
        We do not process the definition location of a callable.
        Any changes within the definition location will be later
        processed in the call site.
        """
        actor_point = self.register_new_actor_point(node_data)
        def_point = self.register_new_def_point(node_data, actor_point, "FUNCTION")

        # TODO (Medium)
        # return self.process_callable_definition_location(node_data, def_point)
        if VERBOSE:
            print(
                "CALLABLE_DEF_SITE_NOTICE: We do not process the definition location of a FUNCTION callable."
            )
        return

    # def visit_function_header(self, node_data, actor_point, *args, **kwargs):
    #     arguments_node = self.ast.get_children_by_type(node_data, "arguments")
    #     if arguments_node:
    #         arguments = self.ast.get_children(
    #             self.ast.get_data(arguments_node)
    #         ).values()
    #         list(
    #             map(
    #                 lambda argument: self.register_new_def_point(
    #                     argument, actor_point, "VARIABLE"
    #                 ),
    #                 arguments,
    #             )
    #         )
    #     return

    def visit_endfunction_clause(self, node_data, *args, **kwargs):
        return

    def visit_macro_definition(self, node_data, *args, **kwargs):
        """
        #CALLABLE_DEF_SITE_NOTICE:
        We do not process the definition location of a callable.
        Any changes within the definition location will be later
        processed in the call site.
        """
        actor_point = self.register_new_actor_point(node_data)
        def_point = self.register_new_def_point(node_data, actor_point, "MACRO")

        # # TODO (Medium)
        # # return self.process_callable_definition_location(node_data, def_point)
        if VERBOSE:
            print(
                "CALLABLE_DEF_SITE_NOTICE: We do not process the definition location of a MACRO callable."
            )
        return

    # def visit_macro_header(self, node_data, actor_point, *args, **kwargs):
    #     arguments_node = self.ast.get_children_by_type(node_data, "arguments")
    #     if arguments_node:
    #         arguments = self.ast.get_children(
    #             self.ast.get_data(arguments_node)
    #         ).values()
    #         list(
    #             map(
    #                 lambda argument: self.register_new_def_point(
    #                     argument, actor_point, "VARIABLE"
    #                 ),
    #                 arguments,
    #             )
    #         )
    #     return

    def visit_endmacro_clause(self, node_data, *args, **kwargs):
        return

    def process_callable_definition_location(self, node_data, def_point):
        """
        This method can be implemented to analyze the definition of a function/macro
        so that changes to a callable that has never been used also get analyzed.
        #CALLABLE_DEF_SITE_NOTICE:
        We do not process the definition location of a callable.
        Any changes within the definition location will be later
        processed in the call site.
        """
        # def_site_scope = self.sysdiff.CallableConditionalDefUseChains(
        #     self.ast,
        #     self.sysdiff,
        #     self.scope + "/" + node_data["id"],
        #     self,
        #     self.global_scope,
        #     def_point,
        # )
        # def_site_scope.analyze()
        return

    def process_callable_call_location(self, node_data, def_point, actor_point):
        if self.is_recursive_call(node_data):
            self.generic_visit(node_data, actor_point)
            return

        # Calls have an impact on the reachability of the content.
        if node_data["operation"] in ["added", "deleted"]:
            self.add_condition_to_reachability_stack(node_data, actor_point)
        self.global_scope.add_callable_to_current_call_stack(
            self.ast.get_name(node_data)
        )
        def_ast = def_point.ast
        callable = self.sysdiff.CallableConditionalDefUseChains(
            def_ast,
            self.sysdiff,
            self.scope + "/" + node_data["id"],
            self,
            self.global_scope,
            def_point,
            actor_point,
        )
        callable.analyze()
        # Remove from reachability condition
        if node_data["operation"] in ["added", "deleted"]:
            self.remove_condition_from_reachability_stack()
        self.global_scope.remove_callable_from_current_call_stack()

    def visit_block_definition(self, node_data, *args, **kwargs):
        header_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "block_header")
        )
        arguments = sorted(
            self.ast.get_children(
                self.ast.get_data(
                    self.ast.get_children_by_type(header_data, "arguments")
                )
            ).values(),
            key=lambda argument_node_data: argument_node_data["s_pos"],
        )
        body_data = self.ast.get_data(self.ast.get_children_by_type(node_data, "body"))

        new_scope = False

        if len(arguments) == 0:
            new_scope = True
        if self.ast.unparse(arguments[0]).upper() != "SCOPE_FOR":
            new_scope = True
        for argument in arguments:
            if self.ast.unparse(argument).upper() == "VARIABLES":
                new_scope = True
                break

        if new_scope:
            child_scope = self.sysdiff.ConditionalDefUseChains(
                self.ast,
                self.sysdiff,
                scope=self.scope + "/" + node_data["id"],
                parent_scope=self,
                global_scope=self.global_scope,
            )
            self.children.append(child_scope)
            self.sysdiff.append_to_chains(child_scope)

            child_scope.visit(body_data)

            for i, argument in enumerate(arguments):
                if self.ast.unparse(argument).upper() == "PROPAGATE":
                    for arg in arguments[i + 1 :]:
                        var_name = self.ast.get_name(arg)
                        def_points = child_scope.get_definitions_by_name(
                            var_name, False
                        )
                        for def_point in def_points:
                            self.defined_names[var_name].append(def_point)
                            self.def_points[def_point.node_data["id"]].append(def_point)
                            self.actor_points[
                                def_point.actor_point.node_data["id"]
                            ].append(def_point.actor_point)

        else:
            return self.generic_visit(node_data, *args, **kwargs)

    def visit_endblock(self, node_data, *args, **kwargs):
        return

    def visit_if_statement(self, node_data, *args, **kwargs):
        stacked_condition_count = (
            len(list(self.ast.get_children_by_type(node_data, "elseif_clause").keys()))
            + len(list(self.ast.get_children_by_type(node_data, "else_clause").keys()))
            + 1  # For the if_clause
        )
        self.generic_visit(node_data, *args, **kwargs)
        self.remove_condition_from_reachability_stack(
            last_n=stacked_condition_count, was_comparative=True
        )

    def visit_if_clause(self, node_data, *args, **kwargs):
        condition_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "condition")
        )
        self.visit_conditional_expression(condition_node_data)

        body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "body")
        )
        if body_node_data:
            return self.generic_visit(body_node_data, *args, **kwargs)

    def visit_elseif_clause(self, node_data, *args, **kwargs):
        condition_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "condition")
        )
        self.visit_conditional_expression(
            condition_node_data, negate_last_condition=True
        )

        body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "body")
        )
        if body_node_data:
            return self.generic_visit(body_node_data)

    def visit_else_clause(self, node_data, *args, **kwargs):
        condition_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "condition")
        )
        self.visit_conditional_expression(
            condition_node_data, negate_last_condition=True
        )

        body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "body")
        )
        if body_node_data:
            return self.generic_visit(body_node_data)

    def visit_endif_clause(self, node_data, *args, **kwargs):
        return

    def visit_while_statement(self, node_data, *args, **kwargs):
        self.generic_visit(node_data, *args, **kwargs)
        self.remove_condition_from_reachability_stack(last_n=1, was_comparative=True)
        return

    def visit_while_clause(self, node_data, *args, **kwargs):
        condition_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "condition")
        )
        self.visit_conditional_expression(condition_node_data)

        body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "body")
        )
        if body_node_data:
            return self.generic_visit(body_node_data, *args, **kwargs)

    def visit_endwhile_clause(self, node_data, *args, **kwargs):
        return

    def visit_conditional_expression(self, node_data, negate_last_condition=False):
        actor_point = self.register_new_actor_point(node_data)
        if negate_last_condition:
            self.negate_last_condition_in_reachability_stack(negation_symbol="NOT")

        operators = [
            "(",
            ")",
            "AND",
            "COMMAND",
            "DEFINED",
            "EQUAL",
            "EXISTS",
            "GREATER",
            "IS_ABSOLUTE",
            "IS_DIRECTORY",
            "IS_NEWER_THAN",
            "IS_SYMLINK",
            "LESS",
            "MATCHES",
            "NOT",
            "OR",
            "POLICY",
            "STREQUAL",
            "STRGREATER",
            "STRLESS",
            "TARGET",
            "VERSION_EQUAL",
            "VERSION_GREATER",
            "VERSION_LESS",
        ]

        arguments = sorted(
            self.ast.get_children(node_data).values(),
            key=lambda data: data["s_pos"],
        )
        # See https://cmake.org/cmake/help/latest/command/if.html#:~:text=if(DEFINED%20%3Cname%3E%7CCACHE%7B%3Cname%3E%7D%7CENV%7B%3Cname%3E%7D)
        skip = False
        for i, argument in enumerate(arguments):
            if skip:
                skip = False
                continue
            unparsed_argument = self.ast.unparse(argument).upper()
            if unparsed_argument == "DEFINED":
                name = self.ast.get_name(arguments[i + 1])
                if name.upper().startswith(("ENV{", "CACHE{")):
                    skip = True
                    self.register_new_use_point(
                        argument,
                        actor_point,
                        "VARIABLE",
                        preferred_name="}".join(
                            "{".join(name.split("{")[1:]).split("}")[:-1]
                        ),
                    )
            if not unparsed_argument in operators:
                if argument["type"] == "unquoted_argument":
                    self.register_new_use_point(argument, actor_point, "VARIABLE")

        self.generic_visit(node_data, actor_point)

        self.add_condition_to_reachability_stack(
            node_data, actor_point, is_comparative=True
        )

    def visit_foreach_clause(self, node_data, *args, **kwargs):
        """
        # TODO (High): Look into the scoping. Must work fine.
        """
        actor_point = self.register_new_actor_point(node_data)
        condition_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "condition")
        )
        body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(node_data, "body")
        )
        arguments = sorted(
            filter(
                lambda argument_data: argument_data["type"] not in ["(", ")"],
                self.ast.get_children(condition_node_data).values(),
            ),
            key=lambda data: data["s_pos"],
        )
        def_node = arguments.pop(0)
        def_point = self.register_new_def_point(def_node, actor_point, "VARIABLE")

        if arguments:
            if self.ast.unparse(arguments[0]).upper() == "IN":
                if self.ast.unparse(arguments[1]).upper() == "LISTS":
                    for arg in arguments[2:]:
                        self.register_new_use_point(
                            arg, actor_point, use_type="VARIABLE"
                        )

        self.generic_visit(condition_node_data, actor_point)
        self.generic_visit(body_node_data, *args, **kwargs)

        def_point.lock = True

    def visit_endforeach_clause(self, node_data, *args, **kwargs):
        return

    def visit_normal_command(self, node_data, *args, **kwargs):
        command_identifier = self.ast.unparse(
            self.ast.get_data(self.ast.get_children_by_type(node_data, "identifier"))
        ).upper()
        method = f"visit_{command_identifier}"
        visitor = getattr(self, method, self.visit_user_defined_normal_command)
        return visitor(node_data)

    def visit_user_defined_normal_command(self, node_data):
        actor_point = self.register_new_actor_point(
            node_data,
            preferred_type="user_defined",
        )
        use_point, def_points = self.register_new_use_point(
            node_data, actor_point, "USER_DEFINED_CALLABLE"
        )
        self.generic_visit(node_data, actor_point)
        # self.parent_names_available = temp_flag
        if len(def_points) > 0:
            if EXECUTE_CALLABLES:
                list(
                    map(
                        lambda def_point: self.process_callable_call_location(
                            node_data, def_point, actor_point
                        ),
                        def_points,
                    )
                )
            else:
                modified_call_site_nodes = filter(
                    lambda nd: (nd["operation"] != "no-op"),
                    self.ast.get_subtree_nodes(node_data).values(),
                )
                for _ in modified_call_site_nodes:
                    list(
                        map(
                            lambda def_point: self.process_callable_call_location(
                                node_data, def_point, actor_point
                            ),
                            def_points,
                        )
                    )
                    return
                self.generic_visit(node_data, actor_point)
        return

    ############################
    ###### CMake Commands ######
    ############################

    """ All functions are designed based on current latest
    release of CMake, documentations available at:
    https://cmake.org/cmake/help/v3.27/manual/cmake-commands.7.html"""

    ########## Scripting Commands:

    def visit_BREAK(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_CMAKE_HOST_SYSTEM_INFORMATION(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "CMAKE_HOST_SYSTEM_INFORMATION"
        )

        self.register_new_def_point(arguments[1], actor_point, "VARIABLE")

    def visit_CMAKE_LANGUAGE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "CMAKE_LANGUAGE")

        operation = self.ast.unparse(arguments[0]).upper()

        if operation == "GET_MESSAGE_LOG_LEVEL":
            self.register_new_def_point(arguments[1], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() in [
                "ID_VAR",
                "GET_CALL_IDS",
                "GET_CALL",
            ]:
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                continue
            if self.ast.unparse(argument).upper() == "CALL":
                if VERBOSE:
                    print(
                        f"Support needed for command arguments for CALL keyword in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
                    )
                continue

    def visit_CMAKE_MINIMUM_REQUIRED(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_CMAKE_PARSE_ARGUMENTS(self, node_data):
        if VERBOSE:
            print(f"CMAKE_PARSE_ARGUMENTS called in a non-callable scope.")

    def visit_CMAKE_PATH(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "CMAKE_PATH")

        operation = self.ast.unparse(arguments[0]).upper()

        current_target_operations = ["COMPARE", "CONVERT"]
        if not operation in current_target_operations:
            self.register_new_use_point(arguments[1], actor_point, "VARIABLE")

        if operation == "CONVERT":
            self.register_new_def_point(arguments[3], actor_point, "VARIABLE")
            return self.generic_visit(node_data, actor_point)

        current_target_operations = [
            "GET",
            "HAS_ROOT_NAME",
            "HAS_ROOT_DIRECTORY",
            "HAS_ROOT_PATH",
            "HAS_FILENAME",
            "HAS_EXTENSION",
            "HAS_STEM",
            "HAS_RELATIVE_PART",
            "HAS_PARENT_PATH",
            "IS_ABSOLUTE",
            "IS_RELATIVE",
            "NATIVE_PATH",
            "HASH",
        ]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")
            return self.generic_visit(node_data, actor_point)

        current_target_operations = [
            "APPEND",
            "APPEND_STRING",
            "REMOVE_FILENAME",
            "REPLACE_FILENAME",
            "REMOVE_EXTENSION",
            "REPLACE_EXTENSION",
            "NORMAL_PATH",
            "RELATIVE_PATH",
            "ABSOLUTE_PATH",
        ]
        if operation in current_target_operations:
            for i, argument in enumerate(arguments):
                if self.ast.unparse(argument).upper() == "OUTPUT_VARIABLE":
                    self.register_new_def_point(
                        arguments[i + 1], actor_point, "VARIABLE"
                    )
                    break

    def visit_CMAKE_POLICY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "CMAKE_POLICY")

        operation = self.ast.unparse(arguments[0]).upper()

        if operation == "GET":
            self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")

    def visit_CONFIGURE_FILE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_CONTINUE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_EXECUTE_PROCESS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "EXECUTE_PROCESS")

        current_target_keywords = [
            "RESULT_VARIABLE",
            "RESULTS_VARIABLE",
            "OUTPUT_VARIABLE",
            "ERROR_VARIABLE",
        ]

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() in current_target_keywords:
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")

    def visit_FILE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FILE")

        operation = self.ast.unparse(arguments[0]).upper()

        current_target_operations = ["GLOB", "GLOB_RECURSE", "RELATIVE_PATH"]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[1], actor_point, "VARIABLE")
            return self.generic_visit(node_data, actor_point)

        current_target_operations = [
            "READ",
            "STRINGS",
            "TIMESTAMP",
            "SIZE",
            "READ_SYMLINK",
            "REAL_PATH",
            "TO_CMAKE_PATH",
            "TO_NATIVE_PATH",
            "MD5",
            "SHA1",
            "SHA224",
            "SHA256",
            "SHA384",
            "SHA512",
            "SHA3_224",
            "SHA3_256",
            "SHA3_384",
            "SHA3_512",
        ]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[2], actor_point, "VARIABLE")

    def visit_FIND_FILE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FIND_FILE")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_FIND_LIBRARY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FIND_LIBRARY")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_FIND_PACKAGE(self, node_data):
        # 注册 actor point
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FIND_PACKAGE")

        self.register_new_def_point(
            arguments[0], actor_point, "VARIABLE", suffix="_FOUND"
        )

        if self.sysdiff.analysis_mode == "change_location":
            return

        module_mode = True
        config_mode = True

        # 处理 find_package 的关键字和扩展关键字
        basic_sig_keywords = [
            "BYPASS_PROVIDER", "COMPONENTS", "EXACT", "GLOBAL", "MODULE", 
            "OPTIONAL_COMPONENTS", "QUIET", "REGISTRY_VIEW", "REQUIRED", "NO_POLICY_SCOPE",
        ]
        full_sig_extra_keywords = [
            "CMAKE_FIND_ROOT_PATH_BOTH", "CONFIG", "CONFIGS", "HINTS", "NAMES", 
            "ONLY_CMAKE_FIND_ROOT_PATH", "PATHS", "PATH_SUFFIXES", "NO_CMAKE_BUILDS_PATH", 
            "NO_CMAKE_ENVIRONMENT_PATH", "NO_CMAKE_FIND_ROOT_PATH", "NO_CMAKE_INSTALL_PREFIX",
            "NO_CMAKE_PACKAGE_REGISTRY", "NO_CMAKE_PATH", "NO_CMAKE_SYSTEM_PACKAGE_REGISTRY", 
            "NO_CMAKE_SYSTEM_PATH", "NO_DEFAULT_PATH", "NO_MODULE", "NO_PACKAGE_ROOT_PATH", 
            "NO_SYSTEM_ENVIRONMENT_PATH",
        ]
        keywords = basic_sig_keywords + full_sig_extra_keywords

        resolution_fetched = False

        for i, argument in enumerate(arguments):

            if self.ast.unparse(argument).upper() == "MODULE":
                module_mode = True
                config_mode = False

                (
                    resolution_success,
                    found_files,
                ) = self.resolve_find_package_file_path(
                    arguments[0], module_mode=module_mode, confi_mode=config_mode
                )
                resolution_fetched = True
                break

            if self.ast.unparse(argument).upper() == "NAMES":
                module_mode = False
                config_mode = True
                path_name_nodes = []
                for arg in arguments[i + 1:]:
                    if self.ast.unparse(arg).upper() in keywords:
                        break
                    path_name_nodes.append(arg)

                all_resolution_success = False
                all_found_files = []
                for path_name_node in path_name_nodes:
                    (
                        resolution_success,
                        found_files,
                    ) = self.resolve_find_package_file_path(
                        path_name_node, module_mode=module_mode, confi_mode=config_mode
                    )
                    if resolution_success:
                        all_resolution_success = (
                            all_resolution_success or resolution_success
                        )
                        all_found_files = all_found_files + found_files
                resolution_success = all_resolution_success
                found_files = list(set(all_found_files))
                resolution_fetched = True

            if self.ast.unparse(argument).upper() in full_sig_extra_keywords:
                module_mode = False
                config_mode = True

        if not resolution_fetched:
            return 

        if not resolution_success or not found_files:

            actor_point.type = "built_in(integrated)"
            self.actor_points[actor_point.node_data["id"]].append(actor_point)
            return  

        if isinstance(found_files, str):
            if found_files.upper() == "SKIP":
                return
            else:
                raise Exception("File path resolution cannot be a string other than SKIP.")

        for resolution in found_files:
            if resolution == self.ast.file_path or (
                node_data["id"]
                in self.sysdiff.file_data[resolution]["language_specific_info"]["importers"]
            ):
                continue 
        
            self.ast = getattr(self.sysdiff.file_data[resolution]["diff"], self.ast.name)
            self.generic_visit(self.ast.get_data(self.ast.root))
            self.sysdiff.set_data_flow_file_analysis(self.ast.file_path, self.ast.name)

        self.ast = self.ast_stack.pop()

        if node_data["operation"] in ["added", "deleted"]:
            self.remove_condition_from_reachability_stack()

    def visit_FIND_PATH(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FIND_PATH")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_FIND_PROGRAM(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FIND_PROGRAM")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_GET_CMAKE_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "GET_CMAKE_PROPERTY")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")
        self.register_new_use_point(arguments[1], actor_point, "PROPERTY")

    def visit_GET_DIRECTORY_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "GET_DIRECTORY_PROPERTY"
        )

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "DEFINITION":
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                return

        self.register_new_use_point(arguments[-1], actor_point, "PROPERTY")

    def visit_GET_FILENAME_COMPONENT(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "GET_FILENAME_COMPONENT"
        )

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "PROGRAM_ARGS":
                if VERBOSE:
                    print(
                        f"Support needed for command arguments for PROGRAM_ARGS keyword in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
                    )

    def visit_GET_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "GET_PROPERTY")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            keyword = self.ast.unparse(argument).upper()
            if keyword in ["TARGET", "TARGET_DIRECTORY"]:
                self.register_new_use_point(
                    arguments[i + 1], actor_point, "DELIVERABLE"
                )
            elif keyword == "TEST":
                self.register_new_use_point(arguments[i + 1], actor_point, "TEST")
            elif keyword == "PROPERTY":
                self.register_new_use_point(arguments[i + 1], actor_point, "PROPERTY")
            elif keyword == "CACHE":
                self.register_new_use_point(arguments[i + 1], actor_point, "VARIABLE")

    def visit_INCLUDE(self, node_data):
        # Because this command imoprts other commands at this location,
        # the actor must be taken as a reachability condition.
        # This happens when the resolution is successful and right before
        # the analysis of the resolved file. The condition is removed from
        # the reachability stack after the resolved file is processed.
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "INCLUDE")

        for i, argument in enumerate(arguments[1:]):
            if self.ast.unparse(argument).upper() == "RESULT_VARIABLE":
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                break

        # For file-level analysis (No system provided)
        if self.sysdiff.analysis_mode == "change_location":
            return

        included_file_path = self.ast.unparse(arguments[0])

        (
            resolution_success,
            included_files,
        ) = self.resolve_include_file_path(arguments[0])

        if not resolution_success:
            # Exclude CMake module
            # Done after unsuccessful resoltuion attempt
            # to allow files with the same name as CMake modules
            if included_file_path in self.exclude_resolutions:
                self.log_file_path_resolution(
                    "INCLUDE",
                    "EXCLUDE_CMAKE_MODULE",
                    node_data,
                    found_paths=[included_file_path],
                )
                return

            # For files that do not exist in the project
            # or files that are refered to using a variable
            if included_files is None:
                self.log_file_path_resolution("INCLUDE", "NOT_FOUND", node_data)
                return

        # Successful resolution
        if isinstance(included_files, str):
            # For manaully skipped files
            if included_files.upper() == "SKIP":
                self.log_file_path_resolution("INCLUDE", "MANUAL_SKIP", node_data)
                return
            else:
                raise Exception(
                    "File path resolution cannot be a string other than SKIP."
                )

        # For reporting multiple resolutions
        if len(included_files) > 1:
            self.log_file_path_resolution(
                "INCLUDE", "MULTIPLE_PATH", node_data, found_paths=included_files
            )

        if node_data["operation"] in ["added", "deleted"]:
            self.add_condition_to_reachability_stack(node_data, actor_point)
        self.ast_stack.append(self.ast)

        for resolution in included_files:
            # For files with GumTree error
            if self.sysdiff.file_data[resolution]["diff"] is None:
                self.log_file_path_resolution(
                    "INCLUDE", "PARSER_ERROR", node_data, found_paths=[resolution]
                )
                continue

            # Recursive resolution
            if (resolution == self.ast.file_path) or (
                node_data["id"]
                in self.sysdiff.file_data[resolution]["language_specific_info"][
                    "importers"
                ]
            ):
                self.log_file_path_resolution(
                    "INCLUDE", "RECURSION", node_data, found_paths=[resolution]
                )
                continue

            # Resolving to entry point
            if resolution == self.sysdiff.current_entry_file:
                self.log_file_path_resolution(
                    "INCLUDE", "ENTRY_POINT", node_data, found_paths=[resolution]
                )
                continue

            # Resolution is valid
            self.sysdiff.file_data[resolution]["language_specific_info"][
                "importers"
            ].append(node_data["id"])
            self.ast = getattr(
                self.sysdiff.file_data[resolution]["diff"], self.ast.name
            )

            # Working on included file
            self.generic_visit(self.ast.get_data(self.ast.root))
            self.sysdiff.set_data_flow_file_analysis(self.ast.file_path, self.ast.name)
            # Finished working on included file

        self.ast = self.ast_stack.pop()
        if node_data["operation"] in ["added", "deleted"]:
            self.remove_condition_from_reachability_stack()

    def visit_INCLUDE_GUARD(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_LIST(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "LIST")

        operation = self.ast.unparse(arguments[0]).upper()

        self.register_new_use_point(arguments[1], actor_point, "VARIABLE")

        current_target_operations = ["LENGTH", "GET", "JOIN", "SUBLIST", "FIND"]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")

        current_target_operations = [
            "POP_BACK",
            "POP_FRONT",
        ]
        if operation in current_target_operations:
            if len(arguments) > 2:
                for def_node in arguments[2:]:
                    self.register_new_def_point(def_node, actor_point, "VARIABLE")

        current_target_operations = [
            "APPEND",
            "FILTER",
            "INSERT",
            "PREPEND",
            "REMOVE_ITEM",
            "REMOVE_AT",
            "REMOVE_DUPLICATES",
            "TRANSFORM",
            "REVERSE",
            "SORT",
        ]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[1], actor_point, "VARIABLE")

    def visit_MARK_AS_ADVANCED(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "MARK_AS_ADVANCED")

        keywords = ["CLEAR", "FORCE"]
        start_index = 0
        if self.ast.unparse(arguments[0]).upper() in keywords:
            start_index = 1

        for argument in arguments[start_index:]:
            self.register_new_use_point(argument, actor_point, "VARIABLE")
            self.register_new_def_point(argument, actor_point, "VARIABLE")

    def visit_MATH(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "MATH")

        self.register_new_def_point(arguments[1], actor_point, "VARIABLE")

    def visit_MESSAGE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_OPTION(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "OPTION")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_RETURN(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        try:
            arguments = self.get_sorted_arguments_data_list(node_data, "RETURN")
        except MissingArgumentsException:
            return

        if VERBOSE:
            print(
                f"Support needed for PROPAGATE keyword in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

        # for i, argument in enumerate(arguments):
        #     if self.ast.unparse(argument).upper() == "PROPAGATE":
        #         for arg in argument[i + 1 :]:
        #             self.register_new_use_point(arg, actor_point, "VARIABLE")
        #             self.register_new_def_point(arg, actor_point, "VARIABLE")

    def visit_SEPARATE_ARGUMENTS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "SEPARATE_ARGUMENTS")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for argument in arguments:
            if self.ast.unparse(argument).upper() == "PROGRAM":
                if VERBOSE:
                    print(
                        f"Support needed for command arguments for PROGRAM keyword in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
                    )

    def visit_SET(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "SET")

        def_point = self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        if self.ast.unparse(arguments[-1]).upper() == "PARENT_SCOPE":
            self.register_def_point_to_parent_scope(def_point)

    def visit_SET_DIRECTORY_PROPERTIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "SET_DIRECTORY_PROPERTIES"
        )

        for i, argument in enumerate(arguments):
            if (i % 2) == 1:
                self.register_new_def_point(argument, actor_point, "PROPERTY")

    def visit_SET_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "SET_PROPERTY")

        keywords = [
            "GLOBAL",
            "DIRECTORY",
            "TARGET",
            "SOURCE",
            "TARGET_DIRECTORY",
            "INSTALL",
            "TEST",
            "CACHE",
            "APPEND",
            "APPEND_STRING",
            "PROPERTY",
        ]

        for i, argument in enumerate(arguments):
            unparsed_argument = self.ast.unparse(argument).upper()
            if unparsed_argument == "TARGET":
                for arg in arguments[i + 1 :]:
                    if self.ast.unparse(arg).upper() not in keywords:
                        self.register_new_use_point(arg, actor_point, "DELIVERABLE")
                        self.register_new_def_point(arg, actor_point, "DELIVERABLE")
                    else:
                        break
            elif unparsed_argument == "TEST":
                for arg in arguments[i + 1 :]:
                    if self.ast.unparse(arg).upper() not in keywords:
                        self.register_new_use_point(arg, actor_point, "TEST")
                        self.register_new_def_point(arg, actor_point, "TEST")
                    else:
                        break
            if unparsed_argument == "CACHE":
                for arg in arguments[i + 1 :]:
                    if self.ast.unparse(arg).upper() not in keywords:
                        self.register_new_use_point(arg, actor_point, "VARIABLE")
                        self.register_new_def_point(arg, actor_point, "VARIABLE")
                    else:
                        break
            elif unparsed_argument == "PROPERTY":
                self.register_new_def_point(arguments[i + 1], actor_point, "PROPERTY")

    def visit_SITE_NAME(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "SITE_NAME")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

    def visit_STRING(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "STRING")

        operation = self.ast.unparse(arguments[0]).upper()

        if operation == "REGEX":
            sub_operation = self.ast.unparse(arguments[1])
            if sub_operation == "REPLACE":
                self.register_new_def_point(arguments[4], actor_point, "VARIABLE")
            else:
                self.register_new_def_point(arguments[3], actor_point, "VARIABLE")
            return

        if operation == "JSON":
            self.register_new_def_point(arguments[1], actor_point, "VARIABLE")
            if self.ast.unparse(arguments[2]).upper() == "ERROR_VARIABLE":
                self.register_new_def_point(arguments[3], actor_point, "VARIABLE")
            return

        current_target_operations = [
            "APPEND",
            "PREPEND",
            "CONCAT",
            "TIMESTAMP",
            "UUID",
            "MD5",
            "SHA1",
            "SHA224",
            "SHA256",
            "SHA384",
            "SHA512",
            "SHA3_224",
            "SHA3_256",
            "SHA3_384",
            "SHA3_512",
        ]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[1], actor_point, "VARIABLE")
            return

        current_target_operations = ["JOIN", "CONFIGURE"]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[2], actor_point, "VARIABLE")
            return

        current_target_operations = ["FIND", "REPLACE"]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[3], actor_point, "VARIABLE")
            return

        current_target_operations = [
            "TOLOWER",
            "TOUPPER",
            "LENGTH",
            "SUBSTRING",
            "STRIP",
            "GENEX_STRIP",
            "REPEAT",
            "COMPARE",
            "ASCII",
            "HEX",
            "MAKE_C_IDENTIFIER",
            "RANDOM",
        ]
        if operation in current_target_operations:
            self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")
            return

    def visit_UNSET(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "UNSET")

        self.register_new_use_point(arguments[0], actor_point, "VARIABLE")
        def_point = self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        if self.ast.unparse(arguments[-1]).upper() == "PARENT_SCOPE":
            self.register_def_point_to_parent_scope(def_point)

    def visit_VARIABLE_WATCH(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "VARIABLE_WATCH")

        self.register_new_use_point(arguments[0], actor_point, "VARIABLE")
        if len(arguments) == 2:
            self.register_new_use_point(arguments[-1], actor_point, "COMMAND")

    ########## Project Commands:

    def visit_ADD_COMPILE_DEFINITIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "ADD_COMPILE_DEFINITIONS"
        )

        # NOTE from documentations: Definitions are specified using the syntax VAR or VAR=value
        if VERBOSE:
            print(
                f"Support needed for definitions in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_ADD_COMPILE_OPTIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_ADD_CUSTOM_COMMAND(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_CUSTOM_COMMAND")

        if self.ast.unparse(arguments[0]).upper() == "TARGET":
            self.register_new_use_point(arguments[1], actor_point, "DELIVERABLE")
            self.register_new_def_point(arguments[1], actor_point, "DELIVERABLE")

        if VERBOSE:
            print(
                f"Support needed for depndencies and command arguments in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

        # keywords = [
        #     "APPEND",
        #     "ARGS",
        #     "BYPRODUCTS",
        #     "COMMAND",
        #     "COMMAND_EXPAND_LISTS",
        #     "COMMENT",
        #     "DEPENDS",
        #     "DEPENDS_EXPLICIT_ONLY",
        #     "DEPFILE",
        #     "IMPLICIT_DEPENDS",
        #     "JOB_POOL",
        #     "MAIN_DEPENDENCY",
        #     "OUTPUT",
        #     "POST_BUILD",
        #     "PRE_BUILD",
        #     "PRE_LINK",
        #     "USES_TERMINAL",
        #     "VERBATIM",
        #     "WORKING_DIRECTORY",
        # ]
        # for i, argument in enumerate(arguments):
        #     if self.ast.unparse(argument).upper() == "DEPENDS":
        #         for arg in arguments[i + 1]:
        #             if self.ast.unparse(arg).upper() in keywords:
        #                 break
        #             defined_names = self.get_definitions_by_name(arg)
        #             if list(
        #                 filter(
        #                     lambda def_point: def_point.type == "DELIVERABLE", defined_names
        #                 )
        #             ):
        #                 self.register_new_use_point(arg,actor_point, "DELIVERABLE")

    def visit_ADD_CUSTOM_TARGET(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_CUSTOM_TARGET")

        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        if VERBOSE:
            print(
                f"Support needed for depndencies and command arguments in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_ADD_DEFINITIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        # try:
        #     arguments = self.get_sorted_arguments_data_list(
        #         node_data, "ADD_DEFINITIONS"
        #     )
        # except MissingArgumentsException:
        #     pass

        if VERBOSE:
            print(
                f"Support needed for definitions in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_ADD_DEPENDENCIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_DEPENDENCIES")

        for argument in arguments:
            self.register_new_use_point(argument, actor_point, "DELIVERABLE")

        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_ADD_EXECUTABLE(self, node_data):
        """
        Documentation: https://cmake.org/cmake/help/v3.0/command/add_executable.html
        NOTE: Not adding sources as use points because they are either file names
        or will be variable_ref which will be caught when running generic_visit
        on node_data at the end.
        """
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_EXECUTABLE")

        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        try:
            operation = self.ast.unparse(arguments[1]).upper()
        except IndexError:
            return

        if operation == "IMPORTED":
            pass
        elif operation == "ALIAS":
            assert len(arguments) == 3
            self.register_new_use_point(arguments[-1], actor_point, "DELIVERABLE")

    def visit_ADD_LIBRARY(self, node_data):
        """
        NOTE: Not adding sources as use points because they are either file names
        or will be variable_ref which will be caught when running generic_visit
        on node_data at the end.
        TODO: See object library and check object reference
        TODO: See imported library and check global with scoping
        """
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_LIBRARY")

        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        try:
            operation = self.ast.unparse(arguments[1]).upper()
        except IndexError:
            return

        if operation == "ALIAS":
            assert len(arguments) == 3
            self.register_new_use_point(arguments[-1], actor_point, "DELIVERABLE")

    def visit_ADD_LINK_OPTIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_ADD_SUBDIRECTORY(self, node_data):
        """
        Use example:
            https://cmake.org/pipermail/cmake/2007-November/017897.html
            https://stackoverflow.com/a/6891527
            https://stackoverflow.com/a/49989597
            https://stackoverflow.com/a/48510440
        """
        # Because this command imoprts other commands at this location,
        # the actor must be taken as a reachability condition.
        # This happens when the resolution is successful and right before
        # the analysis of the resolved file. The condition is removed from
        # the reachability stack after the resolved file is processed.
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_SUBDIRECTORY")

        # For file-level analysis (No system provided)
        if self.sysdiff.analysis_mode == "change_location":
            return

        (
            resolution_success,
            added_files,
        ) = self.resolve_add_subdirectory_file_path(arguments[0])

        if not resolution_success:
            # For files that do not exist in the project
            # or files that are refered to using a variable
            if added_files is None:
                self.log_file_path_resolution(
                    "ADD_SUBDIRECTORY", "NOT_FOUND", node_data
                )
                return

        if isinstance(added_files, str):
            # For manaully skipped files
            if added_files.upper() == "SKIP":
                self.log_file_path_resolution(
                    "ADD_SUBDIRECTORY", "MANUAL_SKIP", node_data
                )
                return
            else:
                raise Exception(
                    "File path resolution cannot be a string other than SKIP."
                )

        # For reporting multiple resolutions
        if len(added_files) > 1:
            self.log_file_path_resolution(
                "ADD_SUBDIRECTORY", "MULTIPLE_PATH", node_data, found_paths=added_files
            )

        # Add to reachability stack
        if node_data["operation"] in ["added", "deleted"]:
            self.add_condition_to_reachability_stack(node_data, actor_point)

        for resolution in added_files:
            # For files with GumTree error
            if self.sysdiff.file_data[resolution]["diff"] is None:
                self.log_file_path_resolution(
                    "ADD_SUBDIRECTORY",
                    "PARSER_ERROR",
                    node_data,
                    found_paths=[resolution],
                )
                continue

            # Recursive resolution
            if (resolution == self.ast.file_path) or (
                node_data["id"]
                in self.sysdiff.file_data[resolution]["language_specific_info"][
                    "importers"
                ]
            ):
                self.log_file_path_resolution(
                    "ADD_SUBDIRECTORY", "RECURSION", node_data, found_paths=[resolution]
                )
                continue

            # Resolving to entry point
            if resolution == self.sysdiff.current_entry_file:
                self.log_file_path_resolution(
                    "ADD_SUBDIRECTORY",
                    "ENTRY_POINT",
                    node_data,
                    found_paths=[resolution],
                )
                continue

            # Resolution is valid
            self.sysdiff.file_data[resolution]["language_specific_info"][
                "importers"
            ].append(node_data["id"])

            target_ast = getattr(
                self.sysdiff.file_data[resolution]["diff"], self.ast.name
            )
            child_scope = self.sysdiff.ConditionalDefUseChains(
                target_ast,
                self.sysdiff,
                scope=self.scope + "/" + node_data["id"],
                parent_scope=self,
                global_scope=self.global_scope,
            )
            self.children.append(child_scope)
            self.sysdiff.append_to_chains(child_scope)

            # Working on added file
            child_scope.analyze()
            self.sysdiff.set_data_flow_file_analysis(
                child_scope.ast.file_path, child_scope.ast.name
            )
            # Finished working on added file

        # Remove from reachability stack
        if node_data["operation"] in ["added", "deleted"]:
            self.remove_condition_from_reachability_stack()

    def visit_ADD_TEST(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "ADD_TEST")

        if self.ast.unparse(arguments[0]).upper() == "NAME":
            self.register_new_def_point(arguments[1], actor_point, "TEST")
        else:
            self.register_new_def_point(arguments[0], actor_point, "TEST")

        if VERBOSE:
            print(
                f"Support needed for command arguments in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_AUX_SOURCE_DIRECTORY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "AUX_SOURCE_DIRECTORY"
        )

        self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")

    def visit_BUILD_COMMAND(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "BUILD_COMMAND")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "TARGET":
                self.register_new_use_point(
                    arguments[i + 1], actor_point, "DELIVERABLE"
                )
                break

    def visit_CMAKE_FILE_API(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_CREATE_TEST_SOURCELIST(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "CREATE_TEST_SOURCELIST"
        )

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for argument in arguments[2:]:
            if self.ast.unparse(argument).upper() in ["EXTRA_INCLUDE", "FUNCTION"]:
                self.register_new_use_point(argument, actor_point, "TEST")

    def visit_DEFINE_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "DEFINE_PROPERTY")

        self.register_new_def_point(arguments[2], actor_point, "PROPERTY")

        if self.ast.unparse(arguments[-2]).upper() == "INITIALIZE_FROM_VARIABLE":
            self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")

    def visit_ENABLE_LANGUAGE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_ENABLE_TESTING(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_EXPORT(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "EXPORT")

        operation = self.ast.unparse(arguments[0]).upper()

        keywords = [
            "NAMESPACE",
            "APPEND",
            "FILE",
            "EXPORT_LINK_INTERFACE_LIBRARIES",
            "CXX_MODULES_DIRECTORY",
            "ANDROID_MK",
        ]
        if operation == "TARGETS":
            for argument in arguments[1:]:
                if self.ast.unparse(argument).upper() in keywords:
                    break
                else:
                    self.register_new_use_point(argument, actor_point, "DELIVERABLE")

        if operation in ["EXPORT", "PACKAGE"]:
            if VERBOSE:
                print(
                    f"Support needed for PACKAGE & EXPORT keywords in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
                )

    def visit_FLTK_WRAP_UI(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "FLTK_WRAP_UI")

        self.register_new_def_point(
            arguments[0], actor_point, "VARIABLE", suffix="_FLTK_UI_SRCS"
        )

    def visit_GET_SOURCE_FILE_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "GET_SOURCE_FILE_PROPERTY"
        )

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")
        self.register_new_use_point(arguments[-1], actor_point, "PROPERTY")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "TARGET_DIRECTORY":
                self.register_new_use_point(
                    arguments[i + 1], actor_point, "DELIVERABLE"
                )
                break

    def visit_GET_TARGET_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "GET_TARGET_PROPERTY"
        )

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")
        self.register_new_use_point(arguments[1], actor_point, "DELIVERABLE")
        self.register_new_use_point(arguments[-1], actor_point, "PROPERTY")

    def visit_GET_TEST_PROPERTY(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "GET_TEST_PROPERTY")

        self.register_new_use_point(arguments[0], actor_point, "TEST")
        self.register_new_use_point(arguments[1], actor_point, "PROPERTY")
        self.register_new_def_point(arguments[-1], actor_point, "VARIABLE")

    def visit_INCLUDE_DIRECTORIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_INCLUDE_EXTERNAL_MSPROJECT(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "INCLUDE_EXTERNAL_MSPROJECT"
        )

        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        keywrods = ["GUID", "PLATFORM", "TYPE"]

        i = 2
        while True:
            if len(arguments) > i:
                if self.ast.unparse(arguments[i]).upper() in keywrods:
                    i += 2
                else:
                    for arg in arguments[i:]:
                        self.register_new_use_point(arg, actor_point, "DELIVERABLE")
                    break

    def visit_INCLUDE_REGULAR_EXPRESSION(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_INSTALL(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "INSTALL")

        all_keywords = [  # Alphabetically ordered
            "ALL_COMPONENTS",
            "ARCHIVE",
            "BUNDLE",
            "CODE",
            "COMPONENT",
            "CONFIGURATIONS",
            "CXX_MODULES_BMI",
            "CXX_MODULES_DIRECTORY",
            "DESTINATION",
            "DIRECTORIES",
            "DIRECTORY",
            "DIRECTORY_PERMISSIONS",
            "EXCLUDE",
            "EXCLUDE_FROM_ALL",
            "EXPORT",
            "EXPORT_ANDROID_MK",
            "EXPORT_LINK_INTERFACE_LIBRARIES",
            "FILE",
            "FILES_MATCHING",
            "FILE_PERMISSIONS",
            "FILE_SET",
            "FRAMEWORK",
            "IMPORTED_RUNTIME_ARTIFACTS",
            "INCLUDES DESTINATION",
            "LIBRARY",
            "MESSAGE_NEVER",
            "NAMELINK_COMPONENT",
            "NAMELINK_ONLY",
            "NAMELINK_SKIP",
            "NAMESPACE",
            "OBJECTS",
            "OPTIONAL",
            "PATTERN",
            "PERMISSIONS",
            "POST_EXCLUDE_FILES",
            "POST_EXCLUDE_REGEXES",
            "POST_INCLUDE_FILES",
            "POST_INCLUDE_REGEXES",
            "PRE_EXCLUDE_REGEXES",
            "PRE_INCLUDE_REGEXES",
            "PRIVATE_HEADER",
            "PUBLIC_HEADER",
            "REGEX",
            "RENAME",
            "RESOURCE",
            "RUNTIME",
            "RUNTIME_DEPENDENCIES",
            "RUNTIME_DEPENDENCY_SET",
            "SCRIPT",
            "TARGETS",
            "TYPE",
            "USE_SOURCE_PERMISSIONS",
        ]

        target_keywords = ["TARGETS", "IMPORTED_RUNTIME_ARTIFACTS"]
        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() in target_keywords:
                for arg in arguments[i + 1 :]:
                    if self.ast.unparse(arg).upper() in all_keywords:
                        break
                    self.register_new_use_point(arg, actor_point, "DELIVERABLE")

        if VERBOSE:
            print(
                f"Support needed (partial) for {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_LINK_DIRECTORIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_LINK_LIBRARIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        # arguments = self.get_sorted_arguments_data_list(node_data, "LINK_LIBRARIES")

        if VERBOSE:
            print(
                f"Support needed for {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_LOAD_CACHE(self, node_data):
        """
        No support for the old and discouraged signature.
        see: https://cmake.org/cmake/help/v3.27/command/load_cache.html
        """
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "LOAD_CACHE")

        for i, argument in enumerate(arguments):
            unparsed_argument = self.ast.unparse(argument).upper()
            if unparsed_argument == "READ_WITH_PREFIX":
                prefix = self.ast.unparse(arguments[i + 1])
                for arg in arguments[i + 2 :]:
                    self.register_new_use_point(arg, actor_point, "VARIABLE")
                    self.register_new_def_point(
                        arg, actor_point, "VARIABLE", prefix=prefix
                    )
                break

    def visit_PROJECT(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_REMOVE_DEFINITIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        # arguments = self.get_sorted_arguments_data_list(node_data, "REMOVE_DEFINITIONS")

        if VERBOSE:
            print(
                f"Support needed for definitions in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_SET_SOURCE_FILES_PROPERTIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "SET_SOURCE_FILES_PROPERTIES"
        )

        current_target_keywords = [
            "DIRECTORY",
            "TARGET_DIRECTORY",
            "PROPERTIES",
        ]

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "TARGET_DIRECTORY":
                for arg in arguments[i + 1 :]:
                    if self.ast.unparse(arg).upper() in current_target_keywords:
                        break
                    self.register_new_use_point(arg, actor_point, "DELIVERABLE")
            elif self.ast.unparse(argument).upper() == "PROPERTIES":
                j = i + 1
                while True:
                    if len(arguments) > j:
                        self.register_new_def_point(
                            arguments[j], actor_point, "PROPERTY"
                        )
                        j += 2
                    else:
                        break
                break

    def visit_SET_TARGET_PROPERTIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "SET_TARGET_PROPERTIES"
        )

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() != "PROPERTIES":
                self.register_new_use_point(argument, actor_point, "DELIVERABLE")
                self.register_new_def_point(argument, actor_point, "DELIVERABLE")
            else:
                j = i + 1
                while True:
                    if len(arguments) > j:
                        self.register_new_def_point(
                            arguments[j], actor_point, "PROPERTY"
                        )
                        j += 2
                    else:
                        break
                break

    def visit_SET_TESTS_PROPERTIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "SET_TESTS_PROPERTIES"
        )

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() != "PROPERTIES":
                self.register_new_use_point(argument, actor_point, "TEST")
                self.register_new_def_point(argument, actor_point, "TEST")
            else:
                j = i + 1
                while True:
                    if len(arguments) > j:
                        self.register_new_def_point(
                            arguments[j], actor_point, "PROPERTY"
                        )
                        j += 2
                    else:
                        break
                break

    def visit_SOURCE_GROUP(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

    def visit_TARGET_COMPILE_DEFINITIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_COMPILE_DEFINITIONS"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        if VERBOSE:
            print(
                f"Support needed for definitions in {self.ast.unparse(node_data)}, called from {self.ast.file_path}"
            )

    def visit_TARGET_COMPILE_FEATURES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_COMPILE_FEATURES"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TARGET_COMPILE_OPTIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_COMPILE_OPTIONS"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TARGET_INCLUDE_DIRECTORIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_INCLUDE_DIRECTORIES"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TARGET_LINK_DIRECTORIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_LINK_DIRECTORIES"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TARGET_LINK_LIBRARIES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_LINK_LIBRARIES"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        keywords = [
            "PRIVATE",
            "PUBLIC",
            "INTERFACE",
            "LINK_PRIVATE",
            "LINK_PUBLIC",
            "LINK_INTERFACE_LIBRARIES",
        ]

        for i, argument in enumerate(arguments):
            if i == 0:
                continue
            if not self.ast.unparse(argument).upper() in keywords:
                defined_names = self.get_definitions_by_name(argument)
                if list(
                    filter(
                        lambda def_point: def_point.type == "DELIVERABLE", defined_names
                    )
                ):
                    self.register_new_use_point(argument, actor_point, "DELIVERABLE")

    def visit_TARGET_LINK_OPTIONS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_LINK_OPTIONS"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TARGET_PRECOMPILE_HEADERS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(
            node_data, "TARGET_PRECOMPILE_HEADERS"
        )

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

        if self.ast.unparse(arguments[1]).upper() == "REUSE_FROM":
            self.register_new_use_point(arguments[2], actor_point, "DELIVERABLE")

    def visit_TARGET_SOURCES(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "TARGET_SOURCES")

        self.register_new_use_point(arguments[0], actor_point, "DELIVERABLE")
        self.register_new_def_point(arguments[0], actor_point, "DELIVERABLE")

    def visit_TRY_COMPILE(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "TRY_COMPILE")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "TARGET":
                self.register_new_use_point(
                    arguments[i + 1], actor_point, "DELIVERABLE"
                )
                continue
            if self.ast.unparse(argument).upper() == "SOURCE_FROM_VAR":
                self.register_new_use_point(arguments[i + 2], actor_point, "VARIABLE")
                continue
            if self.ast.unparse(argument).upper() == "OUTPUT_VARIABLE":
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                continue
            if self.ast.unparse(argument).upper() == "COPY_FILE_ERROR":
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                continue

    def visit_TRY_RUN(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "TRY_RUN")

        self.register_new_def_point(arguments[0], actor_point, "VARIABLE")
        self.register_new_def_point(arguments[1], actor_point, "VARIABLE")

        current_target_keywords = [
            "COMPILE_OUTPUT_VARIABLE",
            "COPY_FILE_ERROR",
            "OUTPUT_VARIABLE",
            "RUN_OUTPUT_VARIABLE",
            "RUN_OUTPUT_STDOUT_VARIABLE",
            "RUN_OUTPUT_STDERR_VARIABLE",
        ]

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() in [
                "SOURCE_FROM_VAR",
                "WORKING_DIRECTORY",
            ]:
                self.register_new_use_point(arguments[i + 2], actor_point, "VARIABLE")
                continue
            if self.ast.unparse(argument).upper() in current_target_keywords:
                self.register_new_def_point(arguments[i + 1], actor_point, "VARIABLE")
                continue

    ########## CTesgt Commands:

    def visit_CTEST_BUILD(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_CONFIGURE(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_COVERAGE(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_EMPTY_BINARY_DIRECTORY(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_MEMCHECK(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_READ_CUSTOM_FILES(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_RUN_SCRIPT(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_SLEEP(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_START(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_SUBMIT(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_TEST(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_UPDATE(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_UPLOAD(self, node_data):
        self.visit_CTEST_CMDs(node_data)

    def visit_CTEST_CMDs(self, node_data):
        """
        All CTEST_* commands are redirected to this method.
        """
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        try:
            arguments = self.get_sorted_arguments_data_list(node_data, "CTEST_BUILD")
        except MissingArgumentsException:
            arguments = []

        current_target_keywords = [
            "NUMBER_ERRORS",
            "NUMBER_WARNINGS",
            "RETURN_VALUE",
            "CAPTURE_CMAKE_ERROR",
            "DEFECT_COUNT",
            "BUILD_ID",
        ]

        for i, argument in enumerate(arguments):
            if self.ast.unparse(argument).upper() == "TARGET":
                self.register_new_use_point(
                    arguments[i + 1], actor_point, "DELIVERABLE"
                )
                continue
            if self.ast.unparse(argument).upper() in current_target_keywords:
                try:
                    self.register_new_def_point(
                        arguments[i + 1], actor_point, "VARIABLE"
                    )
                except IndexError:
                    pass
                continue

    ############################
    #### CMake Commands End ####
    ############################

    def visit_bracket_argument(self, node_data, *args, **kwargs):
        # NOTE: No generic_visit required
        # as the inner scape sequnces, regex,
        # and variable refs are not evaluated.
        # self.generic_visit(node_data, actor_point)
        return

    def visit_quoted_argument(self, node_data, *args, **kwargs):
        self.generic_visit(node_data, *args, **kwargs)

    def visit_unquoted_argument(self, node_data, *args, **kwargs):
        self.generic_visit(node_data, *args, **kwargs)

    def visit_variable_ref(self, node_data, actor_point):
        self.generic_visit(node_data, actor_point)
        self.register_new_use_point(node_data, actor_point, "VARIABLE")
        # For nested variable references

    #############################
    ##### Propagation Slice #####
    #############################

    def get_propagation_slice(self):
        """
        This method must be implemented in the language support subclass. As the result,
        Def/Use/Actor objects that are affected have their .is_in_propagation_slice attribute set to True.
        """
        if VERBOSE:
            print(f"QUERY scope in process: {self.scope}")
        # Downward Slicing is transitive
        self.slice_downwards()
        # Upward Slicing is not transitive
        self.slice_upwards()
        return self.propagation_slice

    def update_propagation_rules(self, entries):
        if not entries:
            return
        new_propagation_rules = pd.DataFrame(entries)
        self.propagation_slice = pd.concat(
            [self.propagation_slice, new_propagation_rules], ignore_index=True
        )
        # else:
        #     self.propagation_slice = new_propagation_rules

        self.propagation_slice.drop_duplicates(ignore_index=True, inplace=True)

    def get_all_non_processed_actor_points(self):
        return list(
            filter(
                lambda point: (not point.is_processed_for_propagation)
                and (point.is_in_propagation_slice),
                self.get_all_actor_points(),
            )
        )

    def get_all_non_processed_def_points(self):
        return list(
            filter(
                lambda point: (not point.is_processed_for_propagation)
                and (point.is_in_propagation_slice),
                self.get_all_def_points(),
            )
        )

    def get_all_non_processed_use_points(self):
        return list(
            filter(
                lambda point: (not point.is_processed_for_propagation)
                and (point.is_in_propagation_slice),
                self.get_all_use_points(),
            )
        )

    def slice_downwards_actor_points(self):
        importer_actors = {
            "<CMD>ADD_SUBDIRECTORY",
            "<CMD>INCLUDE",
            "<CMD>FIND_PACKAGE",
            "<CMD>SUBDIRS",
        }
        non_processed_actors = self.get_all_non_processed_actor_points()

        #################################################### actor.is_modified
        actor_points = filter(
            lambda point: point.is_modified,
            non_processed_actors,
        )

        # THE IN_LINE IMPACT EFFECT:
        # If it's a built-in command with modified arguments or it is modified itself
        # it'll set the Def points to modified, but the Use points don't matter
        for actor_point in actor_points:
            #################################################### built-in actor
            if actor_point.type == "built_in":
                self.update_propagation_rules(
                    list(
                        map(
                            lambda def_point: {
                                "subject_id": actor_point.id,
                                "subject_type": "actor",
                                "propagation_rule": "defines"
                                + ("" if def_point.set_is_modified() else ""),
                                "object_id": def_point.id,
                                "object_type": "def",
                            },
                            filter(
                                lambda point: (not point.is_modified),
                                actor_point.def_points,
                            ),
                        )
                    )
                )
            #################################################### user-defined or importer actor
            if (actor_point.type == "user_defined") or (
                actor_point.name in importer_actors
            ):
                self.process_reachability_propagation(actor_point)
            actor_point.set_is_processed_for_propagation()

        #################################################### actor.is_reach_affected
        actor_points = filter(
            lambda point: (not point.is_modified) and (point.is_reach_affected),
            non_processed_actors,
        )

        for actor_point in actor_points:
            #################################################### built-in actor
            self.update_propagation_rules(
                list(
                    map(
                        lambda def_point: {
                            "subject_id": actor_point.id,
                            "subject_type": "actor",
                            "propagation_rule": "defines"
                            + ("" if def_point.set_is_reach_affected() else ""),
                            "object_id": def_point.id,
                            "object_type": "def",
                        },
                        filter(
                            lambda point: (not point.is_modified),
                            actor_point.def_points,
                        ),
                    )
                )
            )
            self.update_propagation_rules(
                list(
                    map(
                        lambda use_point: {
                            "subject_id": actor_point.id,
                            "subject_type": "actor",
                            "propagation_rule": "uses"
                            + ("" if use_point.set_is_reach_affected() else ""),
                            "object_id": use_point.id,
                            "object_type": "use",
                        },
                        filter(
                            lambda point: (not point.is_modified),
                            actor_point.use_points,
                        ),
                    )
                )
            )

            #################################################### user-defined or importer actor
            # is_import_reach_affected is handled as scopes in process_reachability_propagation
            if (not actor_point.is_import_reach_affected) and (
                (actor_point.type == "user_defined")
                or (actor_point.name in importer_actors)
            ):
                self.process_reachability_propagation(actor_point)

            actor_point.set_is_processed_for_propagation()

        #################################################### actor.is_value affected Actors
        # This case is not possible. Even for Callables, this will affect their use point
        return

    def slice_downwards_def_points(self):
        non_processed_defs = self.get_all_non_processed_def_points()
        #################################################### is_modified/is_value_affected
        def_points = filter(
            lambda point: (point.is_modified or point.is_value_affected),
            non_processed_defs,
        )

        for def_point in def_points:
            #################################################### built-in actor
            self.update_propagation_rules(
                list(
                    map(
                        lambda use_point: {
                            "subject_id": def_point.id,
                            "subject_type": "def",
                            "propagation_rule": "is_directly_used_at"
                            + ("" if use_point.set_is_value_affected() else ""),
                            "object_id": use_point.id,
                            "object_type": "use",
                        },
                        filter(
                            lambda point: (not point.is_modified), def_point.use_points
                        ),
                    )
                )
            )
            #################################################### user-defined actor
            self.update_propagation_rules(
                list(
                    map(
                        lambda use_point: {
                            "subject_id": def_point.id,
                            "subject_type": "def",
                            "propagation_rule": "is_passed_as_argument"
                            + ("" if use_point.set_is_value_affected() else ""),
                            "object_id": use_point.id,
                            "object_type": "use",
                        },
                        filter(
                            lambda point: (not point.is_modified),
                            def_point.callable_arguments,
                        ),
                    )
                )
            )
            def_point.set_is_processed_for_propagation()

        #################################################### is_reach_affected
        def_points = filter(
            lambda point: (
                (not point.is_modified)
                and (not point.is_value_affected)
                and point.is_reach_affected
            ),
            non_processed_defs,
        )

        for def_point in def_points:
            actor = def_point.actor_point
            if actor.type == "built_in":
                if actor.is_import_reach_affected:
                    #################################################### actor.is_import_reach_affected
                    self.update_propagation_rules(
                        list(
                            map(
                                lambda use_point: {
                                    "subject_id": def_point.id,
                                    "subject_type": "def",
                                    "propagation_rule": "is_directly_used_at"
                                    + ("" if use_point.set_is_value_affected() else ""),
                                    "object_id": use_point.id,
                                    "object_type": "use",
                                },
                                filter(
                                    lambda point: (
                                        (not point.is_modified)
                                        and (
                                            not point.scope.startswith(def_point.scope)
                                        )
                                    ),
                                    def_point.use_points,
                                ),
                            )
                        )
                    )
                else:
                    #################################################### ~actor.is_import_reach_affected
                    self.update_propagation_rules(
                        list(
                            map(
                                lambda use_point: {
                                    "subject_id": def_point.id,
                                    "subject_type": "def",
                                    "propagation_rule": "is_directly_used_at"
                                    + ("" if use_point.set_is_value_affected() else ""),
                                    "object_id": use_point.id,
                                    "object_type": "use",
                                },
                                filter(
                                    lambda point: (
                                        (not point.is_modified)
                                        and (
                                            (
                                                not point.scope.startswith(
                                                    def_point.scope
                                                )
                                            )
                                            or (
                                                len(
                                                    set(
                                                        def_point.actor_point.reachability_actor_ids
                                                    ).difference(
                                                        set(
                                                            point.actor_point.reachability_actor_ids
                                                        )
                                                    )
                                                )
                                                != 0
                                            )
                                        )
                                    ),
                                    def_point.use_points,
                                ),
                            )
                        )
                    )
            else:
                pass

    def slice_downwards_use_points(self):
        non_processed_uses = self.get_all_non_processed_use_points()
        #################################################### is_modified
        use_points = filter(
            lambda point: (point.is_modified),
            non_processed_uses,
        )

        for use_point in use_points:
            #################################################### is_modified intra-statement non-modified Defs
            actor = use_point.actor_point
            if actor.type == "built_in":
                self.update_propagation_rules(
                    list(
                        map(
                            lambda def_point: {
                                "subject_id": use_point.id,
                                "subject_type": "use",
                                "propagation_rule": "is_used_in_definition_of"
                                + ("" if not def_point.set_is_modified() else ""),
                                "object_id": def_point.id,
                                "object_type": "def",
                            },
                            filter(
                                lambda point: (not point.is_modified), actor.def_points
                            ),
                        )
                    )
                )
            else:
                # Handled nested arguments in ExtendedProcessor
                # Handled KW args in CDU construction (check_for_parsed_arguments_updates)
                pass

            #################################################### is_modified Reachability
            if actor.node_data["type"] in (self.ast.node_actors.reach_impacting_types):
                self.process_reachability_propagation(use_point)

            use_point.set_is_processed_for_propagation()

        #################################################### is_value_affected
        use_points = filter(
            lambda point: ((not point.is_modified) & point.is_value_affected),
            non_processed_uses,
        )

        for use_point in use_points:
            #################################################### is_value_affected intra-statement non-modified Defs
            actor = use_point.actor_point
            actor = use_point.actor_point
            if actor.type == "built_in":
                self.update_propagation_rules(
                    list(
                        map(
                            lambda def_point: {
                                "subject_id": use_point.id,
                                "subject_type": "use",
                                "propagation_rule": "is_used_in_definition_of"
                                + ("" if not def_point.set_is_value_affected() else ""),
                                "object_id": def_point.id,
                                "object_type": "def",
                            },
                            filter(
                                lambda point: (not point.is_modified), actor.def_points
                            ),
                        )
                    )
                )
            else:
                self.update_propagation_rules(
                    list(
                        map(
                            lambda def_point: {
                                "subject_id": use_point.id,
                                "subject_type": "use",
                                "propagation_rule": "is_used_in_definition_of"
                                + ("" if not def_point.set_is_value_affected() else ""),
                                "object_id": def_point.id,
                                "object_type": "def",
                            },
                            filter(
                                lambda point: (
                                    (not point.is_modified)
                                    and (
                                        point.node_data["s_pos"]
                                        <= use_point.node_data["s_pos"]
                                    )
                                    and (
                                        point.node_data["e_pos"]
                                        >= use_point.node_data["e_pos"]
                                    )
                                ),
                                actor.def_points,
                            ),
                        )
                    )
                )

            #################################################### is_value_affected Reachability
            if use_point.actor_point.node_data["type"] in (
                self.ast.node_actors.reach_impacting_types
            ):
                self.process_reachability_propagation(use_point)

            use_point.set_is_processed_for_propagation()

        #################################################### is_reach_affected
        # Nothing to be done bc:
        # 1. If actor is built-in command, it is also reach affected.
        # 2. If actor is user-defined command, it is also reach affected which affects the body.
        # 3. If actor is reach-impacting, it and its body is also reach affected.
        return

    def process_reachability_propagation(self, point):
        if isinstance(point, self.Use):
            actor_id = point.actor_point.id
            point_type = "use"
            is_conditional = True
        elif isinstance(point, self.Actor):
            actor_id = point.id
            point_type = "actor"
            is_conditional = False

        reach_affected_actor_points = filter(
            lambda point: (
                (actor_id in point.reachability_actor_ids) and (not point.is_modified)
            ),
            self.get_all_actor_points(),
        )
        if is_conditional:
            self.update_propagation_rules(
                list(
                    map(
                        lambda actor_point: {
                            "subject_id": point.id,
                            "subject_type": point_type,
                            "propagation_rule": "affects_reachability_of"
                            + ("" if not actor_point.set_is_reach_affected() else ""),
                            "object_id": actor_point.id,
                            "object_type": "actor",
                        },
                        reach_affected_actor_points,
                    )
                )
            )
        else:
            self.update_propagation_rules(
                list(
                    map(
                        lambda actor_point: {
                            "subject_id": point.id,
                            "subject_type": point_type,
                            "propagation_rule": "affects_reachability_of"
                            + (
                                ""
                                if not actor_point.set_is_import_reach_affected()
                                else ""
                            ),
                            "object_id": actor_point.id,
                            "object_type": "actor",
                        },
                        reach_affected_actor_points,
                    )
                )
            )
            children = list(
                filter(
                    lambda cdu: (actor_id in cdu.reachability_actor_id_stack),
                    self.children,
                )
            )
            while children:
                next_children = []
                for child_chain in children:
                    self.update_propagation_rules(
                        list(
                            map(
                                lambda actor_point: {
                                    "subject_id": point.id,
                                    "subject_type": point_type,
                                    "propagation_rule": "affects_reachability_of"
                                    + (
                                        ""
                                        if not actor_point.set_is_import_reach_affected()
                                        else ""
                                    ),
                                    "object_id": actor_point.id,
                                    "object_type": "actor",
                                },
                                filter(
                                    lambda point: (not point.is_modified),
                                    child_chain.get_all_actor_points(),
                                ),
                            )
                        )
                    )
                    next_children += child_chain.children
                children = next_children

    def slice_downwards(self):
        previous_propagation_rules_length = len(self.propagation_slice)
        self.slice_downwards_actor_points()
        self.slice_downwards_def_points()
        self.slice_downwards_use_points()
        if len(self.propagation_slice) != previous_propagation_rules_length:
            self.slice_downwards()

    def slice_upwards(self):
        # def_points = filter(lambda point: point.is_modified, self.get_all_def_points())

        # for def_point in def_points:
        #     actor = def_point.actor_point
        #     if actor.type == "built_in":
        #         self.update_propagation_rules(
        #             list(
        #                 map(
        #                     lambda use_point: {
        #                         "subject_id": use_point.id,
        #                         "subject_type": "use",
        #                         "propagation_rule": "is_used_in_definition_of"
        #                         + ("" if use_point.set_is_upstream() else ""),
        #                         "object_id": def_point.id,
        #                         "object_type": "def",
        #                     },
        #                     filter(
        #                         lambda use_point: use_point.name == def_point.name,
        #                         actor.use_points,
        #                     ),
        #                 )
        #             )
        #         )
        #     elif actor.type == "user_defined":
        #         self.update_propagation_rules(
        #             list(
        #                 map(
        #                     lambda use_point: {
        #                         "subject_id": use_point.id,
        #                         "subject_type": "use",
        #                         "propagation_rule": "is_used_in_definition_of"
        #                         + ("" if not def_point.set_is_value_affected() else ""),
        #                         "object_id": def_point.id,
        #                         "object_type": "def",
        #                     },
        #                     filter(
        #                         lambda point: (
        #                             (
        #                                 def_point.node_data["s_pos"]
        #                                 <= point.node_data["s_pos"]
        #                             )
        #                             and (
        #                                 def_point.node_data["e_pos"]
        #                                 >= point.node_data["e_pos"]
        #                             )
        #                         ),
        #                         actor.use_points,
        #                     ),
        #                 )
        #             )
        #         )

        use_points = filter(
            lambda point: point.is_modified or point.is_upstream,
            self.get_all_use_points(),
        )

        chain = self

        while chain:
            for use_point in use_points:
                self.update_propagation_rules(
                    list(
                        map(
                            lambda def_point: {
                                "subject_id": def_point.id,
                                "subject_type": "def",
                                "propagation_rule": "is_directly_used_at"
                                + ("" if def_point.set_is_upstream() else ""),
                                "object_id": use_point.id,
                                "object_type": "use",
                            },
                            filter(
                                lambda def_point: use_point in def_point.use_points,
                                chain.get_all_def_points(),
                            ),
                        )
                    )
                )
            chain = chain.parent_scope

    ####################################
    #### CMake Depricatred Commands ####
    ####################################

    def visit_SUBDIRS(self, node_data):
        """
        Support for deprecated command for vxl project:
        https://cmake.org/cmake/help/latest/command/subdirs.html
        """
        # Because this command imoprts other commands at this location,
        # the actor must be taken as a reachability condition.
        # This happens when the resolution is successful and right before
        # the analysis of the resolved file. The condition is removed from
        # the reachability stack after the resolved file is processed.
        actor_point = self.register_new_actor_point(node_data)
        self.generic_visit(node_data, actor_point)

        arguments = self.get_sorted_arguments_data_list(node_data, "SUBDIRS")

        # For file-level analysis (No system provided)
        if self.sysdiff.analysis_mode == "change_location":
            return

        for argument in arguments:
            if self.ast.unparse(argument).upper() in ["EXCLUDE_FROM_ALL", "PREORDER"]:
                break
            (
                resolution_success,
                added_files,
            ) = self.resolve_add_subdirectory_file_path(argument)

            if not resolution_success:
                # For files that do not exist in the project
                # or files that are refered to using a variable
                if added_files is None:
                    self.log_file_path_resolution("SUBDIRS", "NOT_FOUND", node_data)
                    return

            if isinstance(added_files, str):
                # For manaully skipped files
                if added_files.upper() == "SKIP":
                    self.log_file_path_resolution("SUBDIRS", "MANUAL_SKIP", node_data)
                    return
                else:
                    raise Exception(
                        "File path resolution cannot be a string other than SKIP."
                    )

            # For reporting multiple resolutions
            if len(added_files) > 1:
                self.log_file_path_resolution(
                    "SUBDIRS", "MULTIPLE_PATH", node_data, found_paths=added_files
                )

            # Add to reachability stack
            if node_data["operation"] in ["added", "deleted"]:
                self.add_condition_to_reachability_stack(node_data, actor_point)

            for resolution in added_files:
                # For files with GumTree error
                if self.sysdiff.file_data[resolution]["diff"] is None:
                    self.log_file_path_resolution(
                        "SUBDIRS", "PARSER_ERROR", node_data, found_paths=[resolution]
                    )
                    continue

                # Recursive resolution
                if (resolution == self.ast.file_path) or (
                    node_data["id"]
                    in self.sysdiff.file_data[resolution]["language_specific_info"][
                        "importers"
                    ]
                ):
                    self.log_file_path_resolution(
                        "SUBDIRS", "RECURSION", node_data, found_paths=[resolution]
                    )
                    continue

                # Resolving to entry point
                if resolution == self.sysdiff.current_entry_file:
                    self.log_file_path_resolution(
                        "SUBDIRS", "ENTRY_POINT", node_data, found_paths=[resolution]
                    )
                    continue

                # Resolution is valid
                self.sysdiff.file_data[resolution]["language_specific_info"][
                    "importers"
                ].append(node_data["id"])

                target_ast = getattr(
                    self.sysdiff.file_data[resolution]["diff"], self.ast.name
                )
                child_scope = self.sysdiff.ConditionalDefUseChains(
                    target_ast,
                    self.sysdiff,
                    scope=self.scope + "/" + node_data["id"],
                    parent_scope=self,
                    global_scope=self.global_scope,
                )
                self.children.append(child_scope)
                self.sysdiff.append_to_chains(child_scope)

                # Working on added file
                child_scope.analyze()
                self.sysdiff.set_data_flow_file_analysis(
                    child_scope.ast.file_path, child_scope.ast.name
                )
                # Finished working on added file

            # Remove from reachability stack
            if node_data["operation"] in ["added", "deleted"]:
                self.remove_condition_from_reachability_stack()


class CallableConditionalDefUseChains(ConditionalDefUseChains):

    def __init__(
        self,
        def_ast,
        sysdiff,
        scope,
        caller_scope,
        global_scope,
        callable_def_point,
        caller_actor_point=None,
    ):
        if caller_actor_point is None:
            self.is_call_site = False
        else:
            self.is_call_site = True

        if self.is_call_site:
            self.caller_scope = caller_scope
            self.callable_type = callable_def_point.type
            if self.callable_type == "FUNCTION":
                super().__init__(
                    def_ast,
                    sysdiff,
                    scope,
                    caller_scope,
                    global_scope,
                )
                self.parent_scope.children.append(self)
                self.sysdiff.append_to_chains(self)

            elif self.callable_type == "MACRO":
                self.ast = def_ast
                self.scope = caller_scope.scope
                self.global_scope = global_scope
                # The ConditionalDefUseChains object of the parent scope
                self.parent_scope = caller_scope.parent_scope
                self.parent_names_available = True
                # A list of ConditionalDefUseChains objects of the children scopes
                self.children = caller_scope.children
                self.ast_stack = caller_scope.ast_stack
                self.sysdiff = sysdiff
                # Store current reachability conditions based on conditional statements
                self.reachability_stack = caller_scope.reachability_stack.copy()
                self.reachability_actor_id_stack = (
                    caller_scope.reachability_actor_id_stack.copy()
                )
                self.def_points = caller_scope.def_points
                self.use_points = caller_scope.use_points
                self.actor_points = caller_scope.actor_points
                self.defined_names = caller_scope.defined_names
                self.used_names = caller_scope.used_names
                self.undefined_names = caller_scope.undefined_names
                self.current_call_stack = caller_scope.current_call_stack
                self.propagation_slice = caller_scope.propagation_slice

            else:
                raise DebugException(
                    f"CallableConditionalDefUseChains initialized for a command that is neither a FUNCTION nor a MACRO, but is a {callable_def_point.type}"
                )
        else:
            """
            #CALLABLE_DEF_SITE_NOTICE:
            We do not process the definition location of a callable.
            Any changes within the definition location will be later
            processed in the call site.
            """
            pass
            # super().__init__(
            #     def_ast,
            #     sysdiff,
            #     scope,
            #     caller_scope,
            #     global_scope,
            # )
            # self.parent_names_available = False
            # self.parent_scope.children.append(self)
            # self.sysdiff.append_to_chains(self)

        self.caller_actor = caller_actor_point

        self.header_node_type = f"{self.callable_type.lower()}_header"

        self.callable_def_point = callable_def_point

        self.callable_header_node_data = self.ast.get_data(
            self.ast.get_children_by_type(
                self.callable_def_point.node_data, self.header_node_type
            )
        )

        self.callable_body_node_data = self.ast.get_data(
            self.ast.get_children_by_type(self.callable_def_point.node_data, "body")
        )

        # The following names, when assigned to use points,
        # have no def point, but are connected to arguments.
        self.required_arguments_names = {}
        self.accessable_aggregate_names = {
            "ARGC": [],
            "ARGV": [],
            "ARGN": [],
        }
        self.accessable_names = {}
        self.parsed_args_prefix = None
        self.prefixed_parsed_names = {}

    def analyze(self):
        if self.is_call_site:
            self.analyze_call_site()
        else:
            self.analyze_def_site()

    def analyze_call_site(self):
        if self.callable_body_node_data:
            try:
                self.passed_values = self.caller_scope.get_sorted_arguments_data_list(
                    self.caller_actor.node_data, "user_defined_callable"
                )
            except MissingArgumentsException:
                self.passed_values = []

            try:
                self.required_arguments = self.get_sorted_arguments_data_list(
                    self.callable_header_node_data, self.header_node_type
                )
            except MissingArgumentsException:
                self.required_arguments = []

            self.set_up_mappings()

            self.visit(self.callable_body_node_data)

            if self.parsed_args_prefix:
                self.check_for_parsed_arguments_updates()

    def analyze_def_site(self):
        """
        #CALLABLE_DEF_SITE_NOTICE:
        We do not process the definition location of a callable.
        Any changes within the definition location will be later
        processed in the call site.
        """
        pass

    def set_up_mappings(self):
        locational_passed_def_points = []
        required_arguments_names = list(
            map(
                lambda node_data: self.ast.get_name(node_data),
                self.required_arguments,
            )
        )
        for i, node_data in enumerate(self.passed_values):
            # Each argument is a def point
            # TODO (High): Make it so that only required args are defined here and
            # the keyword args are defined when cmake_parse_arguments is called.
            # TODO (High): Does not apply here but make use the extended processor
            # to set the node actions to updated for keyword args and called
            # functions/macros
            # TODO (High): Needs extensive work but make sure you modify all built-in
            # commands such that when the value for a keyword arg changes
            # the extended processor sets the operation for the keyword arg
            # to updated
            def_point = self.caller_scope.register_new_def_point(
                node_data, self.caller_actor, def_type="VARIABLE"
            )
            locational_passed_def_points.append(def_point)

            # To register any internal use points
            self.caller_scope.visit(node_data, self.caller_actor)

            # Set up name mapping
            # ARGV# names
            self.accessable_names[f"ARGV{str(i)}"] = def_point
            # Required argument names
            if i < len(self.required_arguments):
                self.required_arguments_names[required_arguments_names[i]] = def_point

        # Aggregate ARG? names
        self.accessable_aggregate_names["ARGC"] = locational_passed_def_points
        self.accessable_aggregate_names["ARGV"] = locational_passed_def_points
        if len(locational_passed_def_points) > len(self.required_arguments):
            self.accessable_aggregate_names["ARGN"] = locational_passed_def_points[
                len(self.required_arguments) :
            ]
        else:
            self.accessable_aggregate_names["ARGN"] = []

    def map_required_argument_name(self, use_point):
        def_point = self.required_arguments_names[use_point.name]
        def_point.add_callable_argument(use_point)
        return [def_point]

    def map_accessable_aggregate_names(self, use_point):
        def_points = self.accessable_aggregate_names[use_point.name]
        list(
            map(
                lambda def_point: def_point.add_callable_argument(use_point),
                def_points,
            )
        )
        return def_points

    def map_accessable_names(self, use_point):
        def_point = self.accessable_names[use_point.name]
        def_point.add_callable_argument(use_point)
        return [def_point]

    def map_prefixed_parsed_names(self, use_point):
        if self.parsed_args_prefix:
            name = use_point.name
            if name in self.prefixed_parsed_names:
                def_points = self.prefixed_parsed_names[name]
                list(
                    map(
                        lambda def_point: def_point.add_callable_argument(use_point),
                        def_points,
                    )
                )
                return def_points

            def_name = name[len(self.parsed_args_prefix) :]
            def_points = list(
                filter(
                    lambda def_point: def_point.name == def_name,
                    self.accessable_aggregate_names["ARGV"],
                )
            )
            if def_points:
                self.prefixed_parsed_names[name] = def_points
                list(
                    map(
                        lambda def_point: def_point.add_callable_argument(use_point),
                        def_points,
                    )
                )
                return def_points
        return []

    def check_for_parsed_arguments_updates(self):
        if self.parsed_args_prefix:
            parsed_arg = None
            for def_point in self.accessable_aggregate_names["ARGV"]:
                if (
                    self.parsed_args_prefix + def_point.name
                    in self.prefixed_parsed_names
                ):
                    parsed_arg = def_point
                elif parsed_arg:
                    if parsed_arg.is_modified:
                        pass
                    elif def_point.is_modified:
                        parsed_arg.ast.update_node_operation(
                            parsed_arg.node_data, "updated"
                        )
                        parsed_arg.set_is_modified()
                    list(
                        map(
                            lambda use_point: def_point.add_callable_argument(
                                use_point
                            ),
                            parsed_arg.callable_arguments,
                        )
                    )

    def register_new_use_point(
        self, use_node_data, actor_point, use_type="VAR", preferred_name=None
    ):
        use_point = self.Use(
            use_node_data,
            use_type,
            actor_point,
            self.ast,
            preferred_name,
            scope=self.scope,
            file=self.ast.file_saved_as,
        )
        registered_to = []
        actor_point.add_use_point(use_point)
        self.use_points[use_point.node_data["id"]].append(use_point)
        self.used_names[use_point.name].append(use_point)

        # Check mappings first
        name = use_point.name
        if name in self.required_arguments_names:
            registered_to = self.map_required_argument_name(use_point)
        elif name in self.accessable_aggregate_names:
            registered_to = self.map_accessable_aggregate_names(use_point)
        elif name in self.accessable_names:
            registered_to = self.map_accessable_names(use_point)
        elif self.parsed_args_prefix:
            if use_point.name.startswith(self.parsed_args_prefix):
                registered_to = self.map_prefixed_parsed_names(use_point)

        if not registered_to:
            defined_names = self.get_definitions_by_name(use_point.node_data)
            if defined_names:
                reachability_checker = getattr(
                    self, "compare_reachability_conditions", None
                )
                if reachability_checker is None:
                    list(
                        map(
                            lambda def_point: def_point.add_use_point(use_point),
                            defined_names,
                        )
                    )
                    registered_to = defined_names.copy()
                    return use_point, registered_to
                for def_point in reversed(defined_names):
                    reachability_status = reachability_checker(def_point, use_point)
                    if reachability_status in ["=", "<"]:
                        def_point.add_use_point(use_point)
                        registered_to.append(def_point)
                        break
                    if reachability_status in ["!"]:
                        continue
                    if reachability_status in [">", "?"]:
                        def_point.add_use_point(use_point)
                        registered_to.append(def_point)
                        continue
            else:
                self.undefined_names[use_point.name].append(use_point)

        return use_point, registered_to

    def visit_CMAKE_PARSE_ARGUMENTS(self, node_data):
        actor_point = self.register_new_actor_point(node_data)
        arguments = self.get_sorted_arguments_data_list(
            node_data, "CMAKE_PARSE_ARGUMENTS"
        )
        self.parsed_args_prefix = self.ast.unparse(arguments[0]).strip('"')
        if self.parsed_args_prefix.upper() == "PARSE_ARGV":
            self.parsed_args_prefix = self.ast.unparse(arguments[2]).strip('"')
            for arg in arguments:
                self.visit(arg, actor_point)
        else:
            for arg in arguments[:-1]:
                self.visit(arg, actor_point)
        self.parsed_args_prefix = self.parsed_args_prefix + "_"
        self.accessable_aggregate_names[
            self.parsed_args_prefix + "UNPARSED_ARGUMENTS"
        ] = self.accessable_aggregate_names["ARGN"]
