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

from platformio.package.commands.install import package_install_cmd
from platformio.package.commands.list import package_list_cmd

PROJECT_CONFIG_TPL = """
[env]
platform = platformio/atmelavr@^3.4.0

[env:devkit]
framework = arduino
board = attiny88
lib_deps =
    milesburton/DallasTemperature@^3.9.1
    https://github.com/bblanchon/ArduinoJson.git#v6.19.0
"""


def test_global_packages(clirunner, validate_cliresult, isolated_pio_core, tmp_path):
    result = clirunner.invoke(package_list_cmd, ["-g"])
    validate_cliresult(result)
    assert "atmelavr @ 3" in result.output
    assert "framework-arduino-avr-attiny" in result.output

    # only tools
    result = clirunner.invoke(package_list_cmd, ["-g", "--only-tools"])
    validate_cliresult(result)
    assert "toolchain-atmelavr" in result.output
    assert "Platforms" not in result.output

    # find tool package
    result = clirunner.invoke(package_list_cmd, ["-g", "-t", "toolchain-atmelavr"])
    validate_cliresult(result)
    assert "toolchain-atmelavr" in result.output
    assert "framework-arduino-avr-attiny@" not in result.output

    # only libraries - no packages
    result = clirunner.invoke(package_list_cmd, ["-g", "--only-libraries"])
    validate_cliresult(result)
    assert not result.output.strip()

    # check global libs
    result = clirunner.invoke(
        package_install_cmd, ["-g", "-l", "milesburton/DallasTemperature@^3.9.1"]
    )
    validate_cliresult(result)
    result = clirunner.invoke(package_list_cmd, ["-g", "--only-libraries"])
    validate_cliresult(result)
    assert "DallasTemperature" in result.output
    assert "OneWire" in result.output

    # filter by lib
    result = clirunner.invoke(package_list_cmd, ["-g", "-l", "OneWire"])
    validate_cliresult(result)
    assert "DallasTemperature" in result.output
    assert "OneWire" in result.output
