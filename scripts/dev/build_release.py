#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Build a new release."""


import os
import sys
import os.path
import shutil
import subprocess
import argparse
import tarfile
import collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                os.pardir))

import qutebrowser
from scripts import utils
from scripts.dev import update_3rdparty


def call_script(name, *args, python=sys.executable):
    """Call a given shell script.

    Args:
        name: The script to call.
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    path = os.path.join(os.path.dirname(__file__), os.pardir, name)
    subprocess.check_call([python, path] + list(args))


def call_freeze(*args, python=sys.executable):
    """Call freeze.py via tox.

    Args:
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    env = os.environ.copy()
    env['PYTHON'] = python
    subprocess.check_call(
        [sys.executable, '-m', 'tox', '-e', 'cxfreeze-windows'] + list(args),
        env=env)


def run_asciidoc2html(args):
    """Common buildsteps used for all OS'."""
    utils.print_title("Running asciidoc2html.py")
    if args.asciidoc is not None:
        a2h_args = ['--asciidoc'] + args.asciidoc
    else:
        a2h_args = []
    call_script('asciidoc2html.py', *a2h_args)


def _maybe_remove(path):
    """Remove a path if it exists."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def smoke_test(executable):
    """Try starting the given qutebrowser executable."""
    subprocess.check_call([executable, '--no-err-windows', '--nowindow',
                          '--temp-basedir', 'about:blank', ':later 500 quit'])


def build_windows():
    """Build windows executables/setups."""
    utils.print_title("Updating 3rdparty content")
    update_3rdparty.update_pdfjs()

    utils.print_title("Building Windows binaries")
    parts = str(sys.version_info.major), str(sys.version_info.minor)
    ver = ''.join(parts)
    dotver = '.'.join(parts)
    python_x86 = r'C:\Python{}_x32'.format(ver)
    python_x64 = r'C:\Python{}'.format(ver)

    utils.print_title("Running 32bit freeze.py build_exe")
    call_freeze('build_exe', python=python_x86)
    utils.print_title("Running 32bit freeze.py bdist_msi")
    call_freeze('bdist_msi', python=python_x86)
    utils.print_title("Running 64bit freeze.py build_exe")
    call_freeze('build_exe', python=python_x64)
    utils.print_title("Running 64bit freeze.py bdist_msi")
    call_freeze('bdist_msi', python=python_x64)

    utils.print_title("Running 32bit smoke test")
    smoke_test('build/exe.win32-{}/qutebrowser.exe'.format(dotver))
    utils.print_title("Running 64bit smoke test")
    smoke_test('build/exe.win-amd64-{}/qutebrowser.exe'.format(dotver))

    destdir = os.path.join('dist', 'zip')
    _maybe_remove(destdir)
    os.makedirs(destdir)

    basedirname = 'qutebrowser-{}'.format(qutebrowser.__version__)
    builddir = os.path.join('build', basedirname)
    _maybe_remove(builddir)

    utils.print_title("Zipping 32bit standalone...")
    name = 'qutebrowser-{}-windows-standalone-win32'.format(
        qutebrowser.__version__)
    origin = os.path.join('build', 'exe.win32-{}'.format(dotver))
    os.rename(origin, builddir)
    shutil.make_archive(os.path.join(destdir, name), 'zip', 'build',
                        basedirname)
    shutil.rmtree(builddir)

    utils.print_title("Zipping 64bit standalone...")
    name = 'qutebrowser-{}-windows-standalone-amd64'.format(
        qutebrowser.__version__)
    origin = os.path.join('build', 'exe.win-amd64-{}'.format(dotver))
    os.rename(origin, builddir)
    shutil.make_archive(os.path.join(destdir, name), 'zip', 'build',
                        basedirname)
    shutil.rmtree(builddir)

    utils.print_title("Creating final zip...")
    shutil.move(os.path.join('dist', 'qutebrowser-{}-amd64.msi'.format(
        qutebrowser.__version__)), os.path.join('dist', 'zip'))
    shutil.move(os.path.join('dist', 'qutebrowser-{}-win32.msi'.format(
        qutebrowser.__version__)), os.path.join('dist', 'zip'))
    shutil.make_archive('qutebrowser-{}-windows'.format(
        qutebrowser.__version__), 'zip', destdir)


def build_sdist():
    """Build an sdist and list the contents."""
    utils.print_title("Building sdist")

    _maybe_remove('dist')

    subprocess.check_call([sys.executable, 'setup.py', 'sdist'])
    dist_files = os.listdir(os.path.abspath('dist'))
    assert len(dist_files) == 1

    dist_file = os.path.join('dist', dist_files[0])
    subprocess.check_call(['gpg', '--detach-sign', '-a', dist_file])

    tar = tarfile.open(dist_file)
    by_ext = collections.defaultdict(list)

    for tarinfo in tar.getmembers():
        if not tarinfo.isfile():
            continue
        name = os.sep.join(tarinfo.name.split(os.sep)[1:])
        _base, ext = os.path.splitext(name)
        by_ext[ext].append(name)

    assert '.pyc' not in by_ext

    utils.print_title("sdist contents")

    for ext, files in sorted(by_ext.items()):
        utils.print_subtitle(ext)
        print('\n'.join(files))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--asciidoc', help="Full path to python and "
                        "asciidoc.py. If not given, it's searched in PATH.",
                        nargs=2, required=False,
                        metavar=('PYTHON', 'ASCIIDOC'))
    args = parser.parse_args()
    utils.change_cwd()

    if os.name == 'nt':
        if sys.maxsize > 2**32:
            # WORKAROUND
            print("Due to a python/Windows bug, this script needs to be run ")
            print("with a 32bit Python.")
            print()
            print("See http://bugs.python.org/issue24493 and ")
            print("https://github.com/pypa/virtualenv/issues/774")
            sys.exit(1)
        run_asciidoc2html(args)
        build_windows()
    else:
        build_sdist()


if __name__ == '__main__':
    main()
