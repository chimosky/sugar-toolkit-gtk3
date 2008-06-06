# Copyright (C) 2008 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import zipfile
import tarfile
import shutil
import subprocess
import re
import gettext
from optparse import OptionParser

from sugar import env
from sugar.bundle.activitybundle import ActivityBundle

def list_files(base_dir, ignore_dirs=None, ignore_files=None):
    result = []

    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if ignore_files and f not in ignore_files:
                rel_path = root[len(base_dir) + 1:]
                result.append(os.path.join(rel_path, f))
        if ignore_dirs and root == base_dir:
            for ignore in ignore_dirs:
                if ignore in dirs:
                    dirs.remove(ignore)

    return result

class Config(object):
    def __init__(self, bundle_name):
        self.source_dir = os.getcwd()

        bundle = ActivityBundle(self.source_dir)
        version = bundle.get_activity_version()

        self.bundle_name = bundle_name
        self.xo_name = '%s-%d.xo' % (self.bundle_name, version)
        self.tarball_name = '%s-%d.tar.bz2' % (self.bundle_name, version)
        self.bundle_id = bundle.get_bundle_id()
        self.bundle_root_dir = self.bundle_name + '.activity'
        self.tarball_root_dir = '%s-%d' % (self.bundle_name, version)

        info_path = os.path.join(self.source_dir, 'activity', 'activity.info')
        f = open(info_path,'r')
        info = f.read()
        f.close()
        match = re.search('^name\s*=\s*(.*)$', info, flags = re.MULTILINE)
        self.activity_name = match.group(1)

class Builder(object):
    def __init__(self, config):
        self.config = config

    def build(self):
        self.build_locale()

    def build_locale(self):
        po_dir = os.path.join(self.config.source_dir, 'po')

        for f in os.listdir(po_dir):
            if not f.endswith('.po'):
                continue

            file_name = os.path.join(po_dir, f)
            lang = f[:-3]

            localedir = os.path.join(self.config.source_dir, 'locale', lang)
            mo_path = os.path.join(localedir, 'LC_MESSAGES')
            if not os.path.isdir(mo_path):
                os.makedirs(mo_path)

            mo_file = os.path.join(mo_path, "%s.mo" % self.config.bundle_id)
            args = ["msgfmt", "--output-file=%s" % mo_file, file_name]
            retcode = subprocess.call(args)
            if retcode:
                print 'ERROR - msgfmt failed with return code %i.' % retcode

            cat = gettext.GNUTranslations(open(mo_file, 'r'))
            translated_name = cat.gettext(self.config.activity_name)
            linfo_file = os.path.join(localedir, 'activity.linfo')
            f = open(linfo_file, 'w')
            f.write('[Activity]\nname = %s\n' % translated_name)
            f.close()

class Packager(object):
    def __init__(self, config):
        self.config = config
        self.dist_dir = os.path.join(self.config.source_dir, 'dist')
        self.package_path = None

        if not os.path.exists(self.dist_dir):
            os.mkdir(self.dist_dir)
            

class BuildPackager(Packager):
    def __init__(self, config):
        Packager.__init__(self, config)
        self.build_dir = self.config.source_dir

    def get_files(self):
        return list_files(self.build_dir,
                          ignore_dirs=['po', 'dist', '.git'],
                          ignore_files=['.gitignore'])

class XOPackager(BuildPackager):
    def __init__(self, config):
        BuildPackager.__init__(self, config)
        self.package_path = os.path.join(self.dist_dir, self.config.xo_name)

    def package(self):
        bundle_zip = zipfile.ZipFile(self.package_path, 'w',
                                     zipfile.ZIP_DEFLATED)
        
        for f in self.get_files():
            bundle_zip.write(os.path.join(self.build_dir, f),
                             os.path.join(self.config.bundle_root_dir, f))

        bundle_zip.close()

class SourcePackager(Packager):
    def __init__(self, config):
        Packager.__init__(self, config)
        self.package_path = os.path.join(self.dist_dir,
                                         self.config.tarball_name)

    def get_files(self):
        return list_files(self.config.source_dir,
                          ignore_dirs=['locale', 'dist', '.git'],
                          ignore_files=['.gitignore'])

    def package(self):
        tar = tarfile.open(self.package_path, "w:bz2")
        for f in self.get_files():
            tar.add(os.path.join(self.config.source_dir, f),
                    os.path.join(self.config.tarball_root_dir, f))
        tar.close()

def cmd_help(config, options, args):
    print 'Usage: \n\
setup.py build               - build generated files \n\
setup.py dev                 - setup for development \n\
setup.py dist_xo             - create a xo bundle package \n\
setup.py dist_source         - create a tar source package \n\
setup.py install   [dirname] - install the bundle \n\
setup.py uninstall [dirname] - uninstall the bundle \n\
setup.py genpot              - generate the gettext pot file \n\
setup.py release             - do a new release of the bundle \n\
setup.py help                - print this message \n\
'

def cmd_dev(config, options, args):
    bundle_path = env.get_user_activities_path()
    if not os.path.isdir(bundle_path):
        os.mkdir(bundle_path)
    bundle_path = os.path.join(bundle_path, config.bundle_root_dir)
    try:
        os.symlink(config.source_dir, bundle_path)
    except OSError:
        if os.path.islink(bundle_path):
            print 'ERROR - The bundle has been already setup for development.'
        else:
            print 'ERROR - A bundle with the same name is already installed.'

def cmd_dist_xo(config, options, args):
    builder = Builder(config)
    builder.build()

    packager = XOPackager(config)
    packager.package()

def cmd_dist_source(config, options, args):
    packager = SourcePackager(config)
    packager.package()

def cmd_install(config, options, args):
    path = args[0]

    packager = XOPackager(config)
    packager.package()

    root_path = os.path.join(args[0], config.bundle_root_dir)
    if os.path.isdir(root_path):
        shutil.rmtree(root_path)

    if not os.path.exists(path):
        os.mkdir(path)

    zf = zipfile.ZipFile(packager.package_path)

    for name in zf.namelist():
        full_path = os.path.join(path, name)            
        if not os.path.exists(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path))

        outfile = open(full_path, 'wb')
        outfile.write(zf.read(name))
        outfile.flush()
        outfile.close()

def cmd_genpot(config, options, args):
    po_path = os.path.join(config.source_dir, 'po')
    if not os.path.isdir(po_path):
        os.mkdir(po_path)

    python_files = []
    for root_dummy, dirs_dummy, files in os.walk(config.source_dir):
        for file_name in files:
            if file_name.endswith('.py'):
                python_files.append(file_name)

    # First write out a stub .pot file containing just the translated
    # activity name, then have xgettext merge the rest of the
    # translations into that. (We can't just append the activity name
    # to the end of the .pot file afterwards, because that might
    # create a duplicate msgid.)
    pot_file = os.path.join('po', '%s.pot' % config.bundle_name)
    escaped_name = re.sub('([\\\\"])', '\\\\\\1', config.activity_name)
    f = open(pot_file, 'w')
    f.write('#: activity/activity.info:2\n')
    f.write('msgid "%s"\n' % escaped_name)
    f.write('msgstr ""\n')
    f.close()

    args = [ 'xgettext', '--join-existing', '--language=Python',
             '--keyword=_', '--add-comments=TRANS:', '--output=%s' % pot_file ]

    args += python_files
    retcode = subprocess.call(args)
    if retcode:
        print 'ERROR - xgettext failed with return code %i.' % retcode

def cmd_release(config, options, args):
    if not os.path.isdir('.git'):
        print 'ERROR - this command works only for git repositories'

    retcode = subprocess.call(['git', 'pull'])
    if retcode:
        print 'ERROR - cannot pull from git'

    print 'Bumping activity version...'

    info_path = os.path.join(config.source_dir, 'activity', 'activity.info')
    f = open(info_path,'r')
    info = f.read()
    f.close()

    exp = re.compile('activity_version\s?=\s?([0-9]*)')
    match = re.search(exp, info)
    version = int(match.group(1)) + 1
    info = re.sub(exp, 'activity_version = %d' % version, info)

    f = open(info_path, 'w')
    f.write(info)
    f.close()

    news_path = os.path.join(config.source_dir, 'NEWS')

    if os.environ.has_key('SUGAR_NEWS'):
        print 'Update NEWS.sugar...'

        sugar_news_path = os.environ['SUGAR_NEWS']
        if os.path.isfile(sugar_news_path):
            f = open(sugar_news_path,'r')
            sugar_news = f.read()
            f.close()
        else:
            sugar_news = ''

        sugar_news += '%s - %d\n\n' % (config.bundle_name, version)

        f = open(news_path,'r')
        for line in f.readlines():
            if len(line.strip()) > 0:
                sugar_news += line
            else:
                break
        f.close()

        sugar_news += '\n'

        f = open(sugar_news_path, 'w')
        f.write(sugar_news)
        f.close()

    print 'Update NEWS...'

    f = open(news_path,'r')
    news = f.read()
    f.close()

    news = '%d\n\n' % version + news

    f = open(news_path, 'w')
    f.write(news)
    f.close()

    print 'Committing to git...'

    changelog = 'Release version %d.' % version
    retcode = subprocess.call(['git', 'commit', '-a', '-m % s' % changelog])
    if retcode:
        print 'ERROR - cannot commit to git'

    retcode = subprocess.call(['git', 'push'])
    if retcode:
        print 'ERROR - cannot push to git'

    print 'Creating the bundle...'
    packager = XOPackager(config)
    packager.package()

    print 'Done.'

def cmd_build(config, options, args):
    builder = Builder(config)
    builder.build()

def start(bundle_name):
    parser = OptionParser()
    (options, args) = parser.parse_args()

    config = Config(bundle_name)

    try:
        globals()['cmd_' + args[0]](config, options, args[1:])
    except (KeyError, IndexError):
        cmd_help(config, options, args)

if __name__ == '__main__':
    start()