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

import io
import time
from email.utils import parsedate
from os.path import getsize, join
from time import mktime

import click
import requests.adapters
import requests.exceptions
from urllib3.util.retry import Retry

from platformio import fs
from platformio.compat import is_terminal
from platformio.http import HTTPSession
from platformio.package.exception import PackageException


_STREAM_RESET = object()


class FileDownloader:
    RETRY = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[413, 429, 500, 502, 503, 504],
        raise_on_status=False,
    )

    def __init__(self, url, dest_dir=None):
        self._url = url
        self._http_session = HTTPSession()
        adapter = requests.adapters.HTTPAdapter(max_retries=self.RETRY)
        self._http_session.mount("https://", adapter)
        self._http_session.mount("http://", adapter)
        self._http_response = None
        self._content_length = -1
        self._resume_validator = None
        # make connection
        self._request_stream()
        if self._http_response.status_code not in (200, 203):
            raise PackageException(
                "Got the unrecognized status code '{0}' when downloaded {1}".format(
                    self._http_response.status_code, url
                )
            )
        self._update_response_metadata()

        disposition = self._http_response.headers.get("content-disposition")
        if disposition and "filename=" in disposition:
            self._fname = (
                disposition[disposition.index("filename=") + 9 :]
                .replace('"', "")
                .replace("'", "")
            )
        else:
            self._fname = [p for p in url.split("/") if p][-1]
        self._fname = str(self._fname)
        self._destination = self._fname
        if dest_dir:
            self.set_destination(join(dest_dir, self._fname))

    def set_destination(self, destination):
        self._destination = destination

    def get_filepath(self):
        return self._destination

    def get_lmtime(self):
        return self._http_response.headers.get("last-modified")

    def get_size(self):
        return self._content_length

    def _update_response_metadata(self):
        if "content-length" in self._http_response.headers:
            self._content_length = int(
                self._http_response.headers["content-length"]
            )
        self._resume_validator = self._http_response.headers.get(
            "ETag"
        ) or self._http_response.headers.get("Last-Modified")

    def _request_stream(self, resume_from=0):
        if self._http_response:
            self._http_response.close()
        headers = {}
        if resume_from > 0 and self._resume_validator:
            headers["Range"] = f"bytes={resume_from}-"
            headers["If-Range"] = self._resume_validator
        try:
            self._http_response = self._http_session.get(
                self._url,
                stream=True,
                headers=headers,
            )
        except requests.exceptions.RequestException as exc:
            self._http_response = None
            raise IOError(str(exc)) from exc

    def _needs_restart(self, downloaded_size):
        if self._http_response.status_code == 206:
            content_range = self._http_response.headers.get(
                "Content-Range", ""
            )
            if content_range.startswith("bytes "):
                try:
                    range_start = int(
                        content_range[6:].split("-", 1)[0]
                    )
                except (ValueError, IndexError):
                    range_start = -1
                return range_start != downloaded_size
            return True
        return self._http_response.status_code in (200, 203)

    def _stream_with_retry(self, fp):
        max_retries = self.RETRY.total
        downloaded_size = 0
        attempt = 0
        while True:
            itercontent = self._http_response.iter_content(
                chunk_size=io.DEFAULT_BUFFER_SIZE
            )
            try:
                for chunk in itercontent:
                    try:
                        fp.write(chunk)
                    except IOError:
                        self._http_response.close()
                        raise
                    downloaded_size += len(chunk)
                    yield chunk
                return
            except requests.exceptions.RequestException as exc:
                self._http_response.close()
                attempt += 1
                if attempt >= max_retries:
                    raise IOError(
                        "Download failed after %d retries: %s"
                        % (max_retries, exc)
                    ) from exc
                backoff = self.RETRY.backoff_factor * (2 ** (attempt - 1))
                time.sleep(backoff)
                self._request_stream(resume_from=downloaded_size)
                if self._http_response.status_code not in (200, 203, 206):
                    raise PackageException(
                        "Got the unrecognized status code '%d' "
                        "when downloading %s"
                        % (self._http_response.status_code, self._url)
                    ) from exc
                if self._needs_restart(downloaded_size):
                    if self._http_response.status_code == 206:
                        self._request_stream(resume_from=0)
                    self._update_response_metadata()
                    fp.seek(0)
                    fp.truncate()
                    downloaded_size = 0
                    yield _STREAM_RESET

    @staticmethod
    def _consume_with_percent(itercontent, file_size, label):
        click.echo(f"{label} 0%", nl=False)
        print_percent_step = 10
        printed_percents = 0
        downloaded_size = 0
        for chunk in itercontent:
            if chunk is _STREAM_RESET:
                click.echo("")
                click.echo(f"{label} 0%", nl=False)
                downloaded_size = 0
                printed_percents = 0
                continue
            downloaded_size += len(chunk)
            if (downloaded_size / file_size * 100) >= (
                printed_percents + print_percent_step
            ):
                printed_percents += print_percent_step
                click.echo(f" {printed_percents}%", nl=False)
        click.echo("")

    def start(self, with_progress=True, silent=False):
        label = "Downloading"
        file_size = self.get_size()
        try:
            with open(self._destination, "wb") as fp:
                itercontent = self._stream_with_retry(fp)

                if file_size == -1 or not with_progress or silent:
                    if not silent:
                        click.echo(f"{label}...")
                    for chunk in itercontent:
                        if chunk is _STREAM_RESET:
                            continue

                elif not is_terminal():
                    self._consume_with_percent(itercontent, file_size, label)

                else:
                    with click.progressbar(
                        length=file_size,
                        iterable=itercontent,
                        label=label,
                        update_min_steps=min(
                            256 * 1024, file_size / 100
                        ),  # every 256Kb or less
                    ) as pb:
                        for chunk in pb:
                            if chunk is _STREAM_RESET:
                                pb.pos = 0
                                pb.finished = False
                                continue
                            pb.update(len(chunk))
        finally:
            if self._http_response:
                self._http_response.close()
            self._http_session.close()

        if self.get_lmtime():
            self._preserve_filemtime(self.get_lmtime())

        return True

    def verify(self, checksum=None):
        _dlsize = getsize(self._destination)
        if self.get_size() != -1 and _dlsize != self.get_size():
            raise PackageException(
                (
                    "The size ({0:d} bytes) of downloaded file '{1}' "
                    "is not equal to remote size ({2:d} bytes)"
                ).format(_dlsize, self._fname, self.get_size())
            )
        if not checksum:
            return True

        checksum_len = len(checksum)
        hash_algo = None
        if checksum_len == 32:
            hash_algo = "md5"
        elif checksum_len == 40:
            hash_algo = "sha1"
        elif checksum_len == 64:
            hash_algo = "sha256"

        if not hash_algo:
            raise PackageException(
                "Could not determine checksum algorithm by %s" % checksum
            )

        dl_checksum = fs.calculate_file_hashsum(hash_algo, self._destination)
        if checksum.lower() != dl_checksum.lower():
            raise PackageException(
                "The checksum '{0}' of the downloaded file '{1}' "
                "does not match to the remote '{2}'".format(
                    dl_checksum, self._fname, checksum
                )
            )
        return True

    def _preserve_filemtime(self, lmdate):
        lmtime = mktime(parsedate(lmdate))
        fs.change_filemtime(self._destination, lmtime)

    def __del__(self):
        self._http_session.close()
        if self._http_response:
            self._http_response.close()
