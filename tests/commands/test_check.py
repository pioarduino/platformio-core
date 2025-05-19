# Copyright (c) 2019-present PlatformIO <contact@platformio.org>
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

# pylint: disable=redefined-outer-name

import json
import os
import sys

import pytest

from platformio import fs
from platformio.check.cli import cli as cmd_check

DEFAULT_CONFIG = """
[env:native]
platform = native
"""

TEST_CODE = """
#include <stdlib.h>

void run_defects() {
    /* Freeing a pointer twice */
    int* doubleFreePi = (int*)malloc(sizeof(int));
    *doubleFreePi=2;
    free(doubleFreePi);
    free(doubleFreePi); /* High */

    /* Reading uninitialized memory */
    int* uninitializedPi = (int*)malloc(sizeof(int));
    *uninitializedPi++; /* High + Medium*/
    free(uninitializedPi);

    /* Delete instead of delete [] */
    int* wrongDeletePi = new int[10];
    wrongDeletePi++;
    delete wrongDeletePi; /* High */

    /* Index out of bounds */
    int arr[10];
    for(int i=0; i < 11; i++) {
        arr[i] = 0; /* High */
    }
}

int main() {
    int uninitializedVar; /* Low */
    run_defects();
}
"""


PVS_STUDIO_FREE_LICENSE_HEADER = """
// This is an open source non-commercial project. Dear PVS-Studio, please check it.
// PVS-Studio Static Code Analyzer for C, C++, C#, and Java: http://www.viva64.com
"""

EXPECTED_ERRORS = 5
EXPECTED_WARNINGS = 1
EXPECTED_STYLE = 4
EXPECTED_DEFECTS = EXPECTED_ERRORS + EXPECTED_WARNINGS + EXPECTED_STYLE


@pytest.fixture(scope="module")
def check_dir(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp("project")
    tmpdir.join("platformio.ini").write(DEFAULT_CONFIG)
    tmpdir.mkdir("src").join("main.cpp").write(TEST_CODE)
    return tmpdir


def count_defects(output):
    error, warning, style = 0, 0, 0
    for line in output.split("\n"):
        if "[high:error]" in line:
            error += 1
        elif "[medium:warning]" in line:
            warning += 1
        elif "[low:style]" in line:
            style += 1
    return error, warning, style


def test_check_cli_output(clirunner, validate_cliresult, check_dir):
    result = clirunner.invoke(cmd_check, ["--project-dir", str(check_dir)])
    validate_cliresult(result)

    errors, warnings, style = count_defects(result.output)

    assert errors + warnings + style == EXPECTED_DEFECTS


def test_check_json_output(clirunner, validate_cliresult, check_dir):
    result = clirunner.invoke(
        cmd_check, ["--project-dir", str(check_dir), "--json-output"]
    )
    validate_cliresult(result)

    output = json.loads(result.stdout.strip())

    assert isinstance(output, list)
    assert len(output[0].get("defects", [])) == EXPECTED_DEFECTS


def test_check_tool_defines_passed(clirunner, check_dir):
    result = clirunner.invoke(cmd_check, ["--project-dir", str(check_dir), "--verbose"])
    output = result.output

    assert "PLATFORMIO=" in output
    assert "__GNUC__" in output




def test_check_language_standard_definition_passed(clirunner, tmpdir):
    config = DEFAULT_CONFIG + "\nbuild_flags = -std=c++17"
    tmpdir.join("platformio.ini").write(config)
    tmpdir.mkdir("src").join("main.cpp").write(TEST_CODE)
    result = clirunner.invoke(cmd_check, ["--project-dir", str(tmpdir), "-v"])

    assert "__cplusplus=201703L" in result.output
    assert "--std=c++17" in result.output


def test_check_language_standard_option_is_converted(clirunner, tmpdir):
    config = (
        DEFAULT_CONFIG
        + """
build_flags = -std=gnu++1y
    """
    )
    tmpdir.join("platformio.ini").write(config)
    tmpdir.mkdir("src").join("main.cpp").write(TEST_CODE)
    result = clirunner.invoke(cmd_check, ["--project-dir", str(tmpdir), "-v"])

    assert "--std=c++14" in result.output


def test_check_language_standard_is_prioritized_over_build_flags(clirunner, tmpdir):
    config = (
        DEFAULT_CONFIG
        + """
check_flags = --std=c++03
build_flags = -std=c++17
    """
    )
    tmpdir.join("platformio.ini").write(config)
    tmpdir.mkdir("src").join("main.cpp").write(TEST_CODE)
    result = clirunner.invoke(cmd_check, ["--project-dir", str(tmpdir), "-v"])

    assert "--std=c++03" in result.output
    assert "--std=c++17" not in result.output


def test_check_language_standard_for_c_language(clirunner, tmpdir):
    config = DEFAULT_CONFIG + "\nbuild_flags = -std=c11"
    tmpdir.join("platformio.ini").write(config)
    tmpdir.mkdir("src").join("main.c").write(TEST_CODE)
    result = clirunner.invoke(cmd_check, ["--project-dir", str(tmpdir), "-v"])

    assert "--std=c11" in result.output
    assert "__STDC_VERSION__=201112L" in result.output
    assert "__cplusplus" not in result.output




def test_check_no_source_files(clirunner, tmpdir):
    tmpdir.join("platformio.ini").write(DEFAULT_CONFIG)
    tmpdir.mkdir("src")

    result = clirunner.invoke(cmd_check, ["--project-dir", str(tmpdir)])

    errors, warnings, style = count_defects(result.output)

    assert result.exit_code != 0
    assert errors == 0
    assert warnings == 0
    assert style == 0


def test_check_bad_flag_passed(clirunner, check_dir):
    result = clirunner.invoke(
        cmd_check, ["--project-dir", str(check_dir), '"--flags=--UNKNOWN"']
    )

    errors, warnings, style = count_defects(result.output)

    assert result.exit_code != 0
    assert errors == 0
    assert warnings == 0
    assert style == 0
