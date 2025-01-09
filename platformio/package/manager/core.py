# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import tarfile

from urllib import request
from os.path import join

from platformio.dependencies import get_core_dependencies
from platformio.package.manager.tool import ToolPackageManager
from platformio.project.config import ProjectConfig
from platformio.package.meta import PackageSpec


def get_installed_core_packages():
    result = []
    pm = ToolPackageManager()
    for name, requirements in get_core_dependencies().items(): # pylint: disable=no-member
        spec = PackageSpec(owner="platformio", name=name, requirements=requirements)
        pkg = pm.get_package(spec)
        if pkg:
            result.append(pkg)
    return result


def get_core_package_dir(name, spec=None, auto_install=True):
    # pylint: disable=unused-argument
    pm = ToolPackageManager()
    pkg_dir = None
    base_pack_dir = ProjectConfig.get_instance().get("platformio", "packages_dir")

    if name in ("tool-scons") and not os.path.exists(join(base_pack_dir, "tool-scons")):
        url = (
            "https://github.com/pioarduino/scons/releases/"
            "download/4.8.1/scons-local-4.8.1.tar.gz"
        )
        target_path = join(base_pack_dir, "tool-scons.tar.gz")
        extract_folder = join(base_pack_dir, "tool-scons")
        with request.urlopen(request.Request(url), timeout=15.0) as response:
            if response.status == 200:
                with open(target_path, "wb") as f:
                    f.write(response.read())
        with tarfile.open(target_path) as tar:
            tar.extractall(extract_folder)

    try:
        if "tool-scons" in name:
            pkg_dir = pm.get_package("tool-scons").path
            assert pm.install("tool-scons")
    except Exception: # pylint: disable=broad-except
        print(
            "Maybe missing entry(s) in platformio.ini ?\n"
            "Please add  \"check_tool = cppcheck\" to use code check tool.\n"
            "In all cases please restart VSC/PlatformIO to try to auto fix issues."
        )
    return pkg_dir


def update_core_packages():
    return True


def remove_unnecessary_core_packages(dry_run=False):
    candidates = []
    pm = ToolPackageManager()
    best_pkg_versions = {}

    for name, requirements in get_core_dependencies().items(): # pylint: disable=no-member
        spec = PackageSpec(owner="platformio", name=name, requirements=requirements)
        pkg = pm.get_package(spec)
        if not pkg:
            continue
        # pylint: disable=no-member
        best_pkg_versions[pkg.metadata.name] = pkg.metadata.version

    for pkg in pm.get_installed():
        skip_conds = [
            os.path.isfile(os.path.join(pkg.path, ".piokeep")),
            pkg.metadata.spec.owner != "platformio",
            pkg.metadata.name not in best_pkg_versions,
            pkg.metadata.name in best_pkg_versions
            and pkg.metadata.version == best_pkg_versions[pkg.metadata.name],
        ]
        if not any(skip_conds):
            candidates.append(pkg)

    if dry_run:
        return candidates

    for pkg in candidates:
        pm.uninstall(pkg)

    return candidates
