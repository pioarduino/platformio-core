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

# pylint: disable=unused-argument

import os

from platformio import fs
from platformio.package.commands.install import package_install_cmd
from platformio.package.commands.uninstall import package_uninstall_cmd
from platformio.package.exception import UnknownPackageError
from platformio.package.manager.library import LibraryPackageManager
from platformio.package.manager.platform import PlatformPackageManager
from platformio.package.manager.tool import ToolPackageManager
from platformio.project.config import ProjectConfig

PROJECT_CONFIG_TPL = """
[env]
platform = platformio/atmelavr@^3.4.0
lib_deps = milesburton/DallasTemperature@^3.9.1

[env:devkit]
framework = arduino
board = attiny88
"""


def pkgs_to_names(pkgs):
    return [pkg.metadata.name for pkg in pkgs]


def test_custom_project_tools(
    clirunner, validate_cliresult, func_isolated_pio_core, tmp_path
):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "platformio.ini").write_text(PROJECT_CONFIG_TPL)
    spec = "platformio/tool-openocd@^2"
    result = clirunner.invoke(
        package_install_cmd,
        ["-d", str(project_dir), "-e", "devkit", "-t", spec],
    )
    validate_cliresult(result)
    with fs.cd(str(project_dir)):
        config = ProjectConfig()
        assert pkgs_to_names(ToolPackageManager().get_installed()) == ["tool-openocd"]
        assert not LibraryPackageManager(
            os.path.join(config.get("platformio", "libdeps_dir"), "devkit")
        ).get_installed()
        # do not expect any platforms
        assert not os.path.exists(config.get("platformio", "platforms_dir"))
        # check saved deps
        assert config.get("env:devkit", "platform_packages") == [
            "platformio/tool-openocd@^2",
        ]
        # uninstall
        result = clirunner.invoke(
            package_uninstall_cmd,
            ["-e", "devkit", "-t", spec],
        )
        validate_cliresult(result)
        assert not pkgs_to_names(ToolPackageManager().get_installed())
        # check saved deps
        assert not ProjectConfig().get("env:devkit", "platform_packages")

        # install tool without saving to config
        result = clirunner.invoke(
            package_install_cmd,
            ["-e", "devkit", "-t", "platformio/tool-esptoolpy@1.20310.0"],
        )
        validate_cliresult(result)
        assert pkgs_to_names(ToolPackageManager().get_installed()) == [
            "tool-esptoolpy",
        ]
        assert ProjectConfig().get("env:devkit", "platform_packages") == [
            "platformio/tool-esptoolpy@1.20310.0",
        ]
        # uninstall
        result = clirunner.invoke(
            package_uninstall_cmd,
            ["-e", "devkit", "-t", "platformio/tool-esptoolpy@^1", "--no-save"],
        )
        validate_cliresult(result)
        assert not pkgs_to_names(ToolPackageManager().get_installed())
        assert ProjectConfig().get("env:devkit", "platform_packages") == [
            "platformio/tool-esptoolpy@1.20310.0",
        ]

        # unknown tool
        result = clirunner.invoke(
            package_uninstall_cmd, ["-t", "platformio/unknown_tool"]
        )
        assert isinstance(result.exception, UnknownPackageError)


def test_custom_project_platforms(
    clirunner, validate_cliresult, func_isolated_pio_core, tmp_path
):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "platformio.ini").write_text(PROJECT_CONFIG_TPL)
    spec = "platformio/atmelavr@^3.4.0"
    result = clirunner.invoke(
        package_install_cmd,
        ["-d", str(project_dir), "-e", "devkit", "-p", spec],
    )
    validate_cliresult(result)
    with fs.cd(str(project_dir)):
        config = ProjectConfig()
        assert pkgs_to_names(PlatformPackageManager().get_installed()) == ["atmelavr"]
        assert not LibraryPackageManager(
            os.path.join(config.get("platformio", "libdeps_dir"), "devkit")
        ).get_installed()
        assert pkgs_to_names(ToolPackageManager().get_installed()) == [
            "framework-arduino-avr-attiny",
            "toolchain-atmelavr",
        ]
        # uninstall
        result = clirunner.invoke(
            package_uninstall_cmd,
            ["-e", "devkit", "-p", spec],
        )
        validate_cliresult(result)
        assert not pkgs_to_names(PlatformPackageManager().get_installed())
        assert not pkgs_to_names(ToolPackageManager().get_installed())

        # unknown platform
        result = clirunner.invoke(package_uninstall_cmd, ["-p", "unknown_platform"])
        assert isinstance(result.exception, UnknownPackageError)
