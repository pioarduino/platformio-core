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

import json
import os

from platformio import fs
from platformio.package.exception import (
    MissingPackageManifestError,
    PackageException,
)
from platformio.package.meta import PackageItem, PackageMetadata, PackageSpec
from platformio.project.config import ProjectConfig
from platformio.project.exception import ProjectError


class PackageManagerSymlinkMixin:
    @staticmethod
    def is_symlink(path):
        return path and path.endswith(".pio-link") and os.path.isfile(path)

    @classmethod
    def resolve_symlink(cls, path):
        assert cls.is_symlink(path)
        data = fs.load_json(path)
        spec = PackageSpec(**data["spec"])
        assert spec.symlink
        # Prefer the pre-resolved absolute target stored at install time.
        # Fall back to cwd + relative URI for older link files that lack it.
        resolved_target = data.get("resolved_target")
        if resolved_target:
            resolved_target = os.path.abspath(resolved_target)
            if os.path.isdir(resolved_target):
                return (resolved_target, spec)
        pkg_dir = spec.uri[10:].replace("\\", os.sep)
        if not os.path.isabs(pkg_dir):
            base_dir = data.get("cwd")
            if not base_dir or not os.path.isdir(
                os.path.normpath(os.path.join(base_dir, pkg_dir))
            ):
                try:
                    base_dir = ProjectConfig.get_instance().get(
                        "platformio", "project_dir"
                    )
                except (OSError, ProjectError):
                    base_dir = os.getcwd()
            pkg_dir = os.path.normpath(os.path.join(base_dir, pkg_dir))
        return (pkg_dir if os.path.isdir(pkg_dir) else None, spec)

    def get_symlinked_package(self, path):
        pkg_dir, spec = self.resolve_symlink(path)
        if not pkg_dir:
            return None
        pkg = PackageItem(os.path.realpath(pkg_dir))
        if not pkg.metadata or not pkg.metadata.spec or not pkg.metadata.spec.symlink:
            try:
                pkg.metadata = self.build_metadata(pkg.path, spec)
            except MissingPackageManifestError:
                pkg.metadata = PackageMetadata(
                    type=self.pkg_type,
                    name=spec.name or os.path.basename(pkg.path),
                    version=self.generate_rand_version(),
                    spec=spec,
                )
        else:
            pkg.metadata.spec = spec
        return pkg

    def install_symlink(self, spec):
        assert spec.symlink
        pkg_dir = spec.uri[10:].replace("\\", os.sep)
        if not os.path.isabs(pkg_dir):
            try:
                project_dir = ProjectConfig.get_instance().get(
                    "platformio", "project_dir"
                )
            except (OSError, ProjectError):
                project_dir = os.getcwd()
            pkg_dir = os.path.normpath(os.path.join(project_dir, pkg_dir))
        if not os.path.isdir(pkg_dir):
            raise PackageException(
                f"Can not create a symbolic link for `{pkg_dir}`, not a directory"
            )
        link_path = os.path.join(
            self.package_dir,
            "%s.pio-link" % (spec.name or os.path.basename(os.path.abspath(pkg_dir))),
        )
        if os.path.isfile(link_path):
            existing_pkg = self.get_symlinked_package(link_path)
            if existing_pkg and os.path.normcase(
                os.path.realpath(existing_pkg.path)
            ) == os.path.normcase(os.path.realpath(pkg_dir)):
                if (
                    existing_pkg.metadata
                    and existing_pkg.metadata.spec
                    and existing_pkg.metadata.spec.uri == spec.uri
                ):
                    return existing_pkg
        with open(link_path, mode="w", encoding="utf-8") as fp:
            json.dump(
                dict(
                    cwd=os.getcwd(),
                    spec=spec.as_dict(),
                    resolved_target=os.path.abspath(pkg_dir),
                ),
                fp,
            )
        return self.get_symlinked_package(link_path)

    def uninstall_symlink(self, spec):
        assert spec.symlink
        for name in os.listdir(self.package_dir):
            path = os.path.join(self.package_dir, name)
            if not self.is_symlink(path):
                continue
            pkg = self.get_symlinked_package(path)
            if (
                pkg
                and pkg.metadata
                and pkg.metadata.spec
                and pkg.metadata.spec.uri == spec.uri
            ):
                os.remove(path)
