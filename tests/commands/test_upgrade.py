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

from types import SimpleNamespace

from platformio.commands import upgrade as upgrade_module


def test_post_release_uses_stable_package(clirunner, monkeypatch):
    monkeypatch.setattr(upgrade_module, "VERSION", (6, 2, 0, "post1"))
    monkeypatch.setattr(upgrade_module, "__version__", "6.2.0.post1")
    monkeypatch.setattr(upgrade_module, "update_core_packages", lambda: None)
    monkeypatch.setattr(upgrade_module, "get_latest_version", lambda: "6.2.1")
    monkeypatch.setattr(upgrade_module, "get_pythonexe_path", lambda: "python")
    calls = []

    def mock_run(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=b"PlatformIO version 6.2.0.post1")

    monkeypatch.setattr(upgrade_module.subprocess, "run", mock_run)

    result = clirunner.invoke(upgrade_module.cli)

    assert result.exit_code == 0, result.output
    assert calls[0][-1] == "platformio"
