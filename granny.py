#!/usr/bin/env python
"""Granny.py. Suck eggs into your PyPI server by name and version or URI.

Usage: granny.py -r REPOSITORY -p PACKAGE [-v VERSION]
       granny.py -r REPOSITORY URI

Options:
    -h --help                              show this help
    -r REPOSITORY --repository=REPOSITORY  specify your pypi repository
    -p PACKAGE --package=PACKAGE           specify package name
    -v VERSION --version=VERSION           specify version number. Defaults to latest available.
"""
import os
import sys
import tempfile
import shutil
import tarfile
import zipfile
import subprocess
import logging
import contextlib
from distutils.sysconfig import get_python_version
from distutils import config
# using vanilla upload, distribute's one strips off required metadata
from distutils.command import upload    

from docopt import docopt
from setuptools import package_index
from setuptools.command import register
from setuptools.dist import Distribution
import pkg_resources
import requests


SETUPEGG_PY="""#!/usr/bin/env/python
import sys
from setuptools import setup

if sys.version_info[0] >= 3:
    import imp
    setupfile = imp.load_source('setupfile', 'setup.py')
    setupfile.setup_package()
else:
    execfile('setup.py')
"""


def get_log():
    return logging.getLogger('granny')


class GrannyError(Exception):
    """ Granny related errors """

@contextlib.contextmanager
def chdir(dirname):
    """
    Context Manager to change to a dir then change back
    """
    here = os.getcwd()
    os.chdir(dirname)
    yield
    os.chdir(here)


def unpack_tarball(arch):
    get_log().info("Unpacking tarball {}".format(arch))
    with chdir(os.path.dirname(arch)):
        tar = tarfile.open(arch)
        tar.extractall()
        tar.close()


def unpack_zipball(arch):
    get_log().info("Unpacking zipfile {}".format(arch))
    with chdir(os.path.dirname(arch)):
        zip = zipfile.ZipFile(arch, 'r')
        zip.extractall()


def download_archive(requirement_or_uri, dest_dir):
    get_log().info("Downloading archive {}".format(requirement_or_uri))
    index = package_index.PackageIndex()
    archive = index.download(requirement_or_uri, dest_dir)
    if not archive:
        raise GrannyError("Can't find package on pypi.python.org")
    return archive


def unpack_archive(archive):
    get_log().info("Unpacking archive {}".format(archive))
    if archive.endswith('.tar.gz') or archive.endswith('.tgz'):
        unpack_tarball(archive)
    elif archive.endswith('.zip'):
        unpack_zipball(archive)
    else:
        raise GrannyError("Can't unpack archive format: {}".format(archive))


def build_egg(egg_dir):
    get_log().info("Building egg in {}".format(egg_dir))
    with chdir(egg_dir):
        if not os.path.isfile('setupegg.py'):
            with open('setupegg.py', 'w') as fp:
                fp.write(SETUPEGG_PY)
        p = subprocess.Popen([sys.executable, 'setupegg.py', 'bdist_egg'])
        p.communicate()
        if p.returncode != 0:
            raise GrannyError("Failed to build egg")
        dists = [i for i in os.listdir('dist')]
        if not dists:
            raise GrannyError("No dists were built under {}".format(os.path.join(egg_dir, 'dists')))
        if len(dists) > 1:
            raise GrannyError("More than one dist built, can't choose between them: {}".format(dists))
        return os.path.join(egg_dir, 'dist', dists[0])


def _get_dist(egg_file):
    # This is so totally b0rked.. why are there so many Distribution classes that do different things... 
    pr_dist = pkg_resources.Distribution.from_location(os.path.dirname(egg_file), os.path.basename(egg_file))
    dist =  Distribution({'name': pr_dist.project_name, 'version': pr_dist.version})
    zip = zipfile.ZipFile(egg_file, 'r')
    pkginfo = zip.open('EGG-INFO/PKG-INFO')
    dist.metadata.read_pkg_file(pkginfo)
    return dist


def _get_pypi_cfg(egg_file, repo):
    pypirc_cmd = config.PyPIRCCommand(_get_dist(egg_file))
    pypirc_cmd.repository = repo
    return pypirc_cmd._read_pypirc()


def is_registered(egg_file, repo):
    dist = _get_dist(egg_file)
    cfg = _get_pypi_cfg(egg_file, repo)
    r = requests.get("{}/simple/{}".format(cfg['repository'], dist.get_name()))
    if r.status_code == 200:
        get_log().info("Egg {} already registered on {}".format(egg_file, repo))
        return True
    get_log().info("Egg {} not yet registered on {}".format(egg_file, repo))
    return False


def register_egg(egg_file, repo):
    get_log().info("Registering {} to {}".format(egg_file, repo))
    dist = _get_dist(egg_file)
    register_cmd = register.register(dist)
    register_cmd.repository = repo
    register_cmd._set_config()
    register_cmd.send_metadata()


def upload_egg(egg_file, repo):
    dist = _get_dist(egg_file)
    cfg = _get_pypi_cfg(egg_file, repo)

    up_cmd = upload.upload(dist)
    up_cmd.repository = cfg['repository']
    up_cmd.username = cfg['username']
    up_cmd.password = cfg['password']

    get_log().info("Uploading {} to {}".format(egg_file, cfg['repository']))

    up_cmd.upload_file('bdist_egg', get_python_version(), egg_file)


def main(repo, uri=None, package=None, version=None):
    if not uri and not package:
        raise GrannyError("Please specify at least package URI or name")
    tempdir = tempfile.mkdtemp()
    try:
        if uri:
            archive = download_archive(uri, tempdir)
        elif version:
            archive = download_archive('{}=={}'.format(package, version), tempdir)
        else:
            archive = download_archive(package, tempdir)

        if not archive.endswith(".egg"):
            unpack_archive(archive)
            arch_dirname = [i for i in os.listdir(tempdir) if i != os.path.basename(archive)][0]
            egg_file = build_egg(os.path.join(tempdir, arch_dirname))
        else:
            egg_file = archive

        if not is_registered(egg_file, repo):
            register_egg(egg_file, repo)

        upload_egg(egg_file, repo)

    finally:
        shutil.rmtree(tempdir)


if __name__ == '__main__': 
    args = docopt(__doc__)
    logging.basicConfig(level=logging.INFO)
    try:
        main(repo=args['--repository'], uri=args['URI'], package=args['--package'], version=args['--version'])
    except GrannyError, e:
        get_log().error(e.args[0])
        sys.exit(1)


