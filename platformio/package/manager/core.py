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

base_pack_dir = ProjectConfig.get_instance().get("platformio", "packages_dir")

def get_installed_core_packages():
    result = []
    pm = ToolPackageManager()
    for name, requirements in get_core_dependencies(base_pack_dir).items(): # pylint: disable=no-member
        spec = PackageSpec(owner="platformio", name=name, requirements=requirements)
        pkg = pm.get_package(spec)
        if pkg:
            result.append(pkg)
    return result


def _download_and_extract(url, target_folder):
    tarball_name = os.path.basename(url)
    target_path = join(base_pack_dir, tarball_name)
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    with request.urlopen(request.Request(url), timeout=15.0) as response:
        if response.status == 200:
            with open(target_path, "wb") as f:
                f.write(response.read())
    with tarfile.open(target_path) as tar:
        tar.extractall(target_folder)


def get_core_package_dir(name, spec=None, auto_install=True):
    # pylint: disable=unused-argument
    pm = ToolPackageManager()
    custom_packages = get_core_dependencies(base_pack_dir)

    if name in custom_packages and not os.path.exists(custom_packages[name]["folder"]):
        _download_and_extract(
            custom_packages[name]["url"],
            custom_packages[name]["folder"],
        )

    try:
        if name in custom_packages:
            pkg = pm.get_package(name)
            if pkg:
                pkg_dir = pkg.path
                if auto_install:
                    assert pm.install(name)
                return pkg_dir
    except Exception: # pylint: disable=broad-except
        print(
            "Maybe missing entry(s) in platformio.ini ?\n"
            "Please add  \"check_tool = cppcheck\" to use code check tool.\n"
            "In all cases please restart VSC/PlatformIO to try to auto fix issues."
        )
        return None

    return None


def update_core_packages():
    return True


def remove_unnecessary_core_packages(dry_run=False):
    candidates = []
    pm = ToolPackageManager()
    best_pkg_versions = {}

    for name, requirements in get_core_dependencies(base_pack_dir).items(): # pylint: disable=no-member
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
