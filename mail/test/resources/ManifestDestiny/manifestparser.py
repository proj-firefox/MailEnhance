#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Mozilla universal manifest parser
"""

# this file lives at
# http://hg.mozilla.org/automation/ManifestDestiny/raw-file/tip/manifestparser.py

__all__ = ['ManifestParser', 'TestManifest', 'convert']

import os
import shutil
import sys
from fnmatch import fnmatch
from optparse import OptionParser

version = '0.2.2' # package version
try:
    from setuptools import setup
except ImportError:
    setup = None

def read_ini(fp, variables=None, default='DEFAULT',
             comments=';#', separators=('=', ':'),
             strict=True):
    """
    read an .ini file and return a list of [(section, values)]
    - fp : file pointer or path to read
    - variables : default set of variables
    - default : name of the section for the default section
    - comments : characters that if they start a line denote a comment
    - separators : strings that denote key, value separation in order
    - strict : whether to be strict about parsing
    """

    if variables is None:
        variables = {}

    if isinstance(fp, basestring):
        fp = file(fp)

    sections = []
    key = value = None
    section_names = set([])

    # read the lines
    for line in fp.readlines():

        stripped = line.strip()

        # ignore blank lines
        if not stripped:
            # reset key and value to avoid continuation lines
            key = value = None
            continue

        # ignore comment lines
        if stripped[0] in comments:
            continue

        # check for a new section
        if len(stripped) > 2 and stripped[0] == '[' and stripped[-1] == ']':
            section = stripped[1:-1].strip()
            key = value = None

            # deal with DEFAULT section
            if section.lower() == default.lower():
                if strict:
                    assert default not in section_names
                section_names.add(default)
                current_section = variables
                continue

            if strict:
                # make sure this section doesn't already exist
                assert section not in section_names

            section_names.add(section)
            current_section = {}
            sections.append((section, current_section))
            continue

        # if there aren't any sections yet, something bad happen
        if not section_names:
            raise Exception('No sections yet :(')

        # (key, value) pair
        for separator in separators:
            if separator in stripped:
                key, value = stripped.split(separator, 1)
                key = key.strip()
                value = value.strip()

                if strict:
                    # make sure this key isn't already in the section or empty
                    assert key
                    if current_section is not variables:
                        assert key not in current_section

                current_section[key] = value
                break
        else:
            # continuation line ?
            if line[0].isspace() and key:
                value = '%s%s%s' % (value, os.linesep, stripped)
                current_section[key] = value
            else:
                # something bad happen!
                raise Exception("Not sure what you're trying to do")

    # interpret the variables
    def interpret_variables(global_dict, local_dict):
        variables = global_dict.copy()
        variables.update(local_dict)
        return variables

    sections = [(i, interpret_variables(variables, j)) for i, j in sections]
    return sections


### objects for parsing manifests

class ManifestParser(object):
    """read .ini manifests"""

    ### methods for reading manifests

    def __init__(self, manifests=(), defaults=None, strict=True):
        self._defaults = defaults or {}
        self.tests = []
        self.strict = strict
        self.rootdir = None
        if manifests:
            self.read(*manifests)

    def read(self, *filenames, **defaults):

        # ensure all files exist
        missing = [ filename for filename in filenames
                    if not os.path.exists(filename) ]
        if missing:
            raise IOError('Missing files: %s' % ', '.join(missing))

        # process each file
        for filename in filenames:

            # set the per file defaults
            defaults = defaults.copy() or self._defaults.copy()
            here = os.path.dirname(os.path.abspath(filename))
            defaults['here'] = here

            if self.rootdir is None:
                # set the root directory
                # == the directory of the first manifest given
                self.rootdir = here

            # read the configuration
            sections = read_ini(filename, variables=defaults)

            # get the tests
            for section, data in sections:

                # a file to include
                # TODO: keep track of structure:
                # self.manifests = {'manifest.ini': 'relative/path.ini'}
                if section.startswith('include:'):
                    include_file = section.split('include:', 1)[-1]
                    include_file = os.path.join(here, include_file)
                    if not os.path.exists(include_file):
                        if strict:
                            raise IOError("File '%s' does not exist" % include_file)
                        else:
                            continue
                    include_defaults = data.copy()
                    self.read(include_file, **include_defaults)
                    continue

                # otherwise a test
                test = data
                test['name'] = section
                test['path'] = os.path.join(here, section)
                test['manifest'] = os.path.abspath(filename)
                self.tests.append(test)

    ### methods for querying manifests

    def query(self, *checks):
        """
        general query function for tests
        - checks : callable conditions to test if the test fulfills the query
        """
        retval = []
        for test in self.tests:
            for check in checks:
                if not check(test):
                    break
            else:
                retval.append(test)
        return retval

    def get(self, _key=None, inverse=False, tags=None, **kwargs):
        # TODO: pass a dict instead of kwargs since you might hav
        # e.g. 'inverse' as a key in the dict

        # TODO: tags should just be part of kwargs with None values
        # (None == any is kinda weird, but probably still better)

        # fix up tags
        if tags:
            tags = set(tags)
        else:
            tags = set()

        # make some check functions
        if inverse:
            has_tags = lambda test: tags.isdisjoint(test.keys())
            def dict_query(test):
                for key, value in kwargs.items():
                    if test.get(key) == value:
                        return False
                return True
        else:
            has_tags = lambda test: tags.issubset(test.keys())
            def dict_query(test):
                for key, value in kwargs.items():
                    if test.get(key) != value:
                        return False
                return True

        # query the tests
        tests = self.query(has_tags, dict_query)

        # if a key is given, return only a list of that key
        # useful for keys like 'name' or 'path'
        if _key:
            return [test[_key] for test in tests]

        # return the tests
        return tests

    def missing(self, tests=None):
        """return list of tests that do not exist on the filesystem"""
        if tests is None:
            tests = self.tests
        return [test for test in tests
                if not os.path.exists(test['path'])]

    def manifests(self, tests=None):
        """
        return manifests in order in which they appear in the tests
        """
        if tests is None:
            tests = self.tests
        manifests = []
        for test in tests:
            manifest = test.get('manifest')
            if not manifest:
                continue
            if manifest not in manifests:
                manifests.append(manifest)
        return manifests


    ### methods for outputting from manifests

    def write(self, fp=sys.stdout, rootdir=None,
              global_tags=None, global_kwargs=None,
              local_tags=None, local_kwargs=None):
        """
        write a manifest given a query
        global and local options will be munged to do the query
        globals will be written to the top of the file
        locals (if given) will be written per test
        """

        # root directory
        if rootdir is None:
            rootdir = self.rootdir

        # sanitize input
        global_tags = global_tags or set()
        local_tags = local_tags or set()
        global_kwargs = global_kwargs or {}
        local_kwargs = local_kwargs or {}
        
        # create the query
        tags = set([])
        tags.update(global_tags)
        tags.update(local_tags)
        kwargs = {}
        kwargs.update(global_kwargs)
        kwargs.update(local_kwargs)

        # get matching tests
        tests = self.get(tags=tags, **kwargs)

        # print the .ini manifest
        if global_tags or global_kwargs:
            print >> fp, '[DEFAULT]'
            for tag in global_tags:
                print >> fp, '%s =' % tag
            for key, value in global_kwargs.items():
                print >> fp, '%s = %s' % (key, value)
            print >> fp

        for test in tests:
            test = test.copy() # don't overwrite

            path = test['name']
            if not os.path.isabs(path):
                path = os.path.relpath(test['path'], self.rootdir)
            print >> fp, '[%s]' % path
          
            # reserved keywords:
            reserved = ['path', 'name', 'here', 'manifest']
            for key in sorted(test.keys()):
                if key in reserved:
                    continue
                if key in global_kwargs:
                    continue
                if key in global_tags and not test[key]:
                    continue
                print >> fp, '%s = %s' % (key, test[key])
            print >> fp

    def copy(self, directory, rootdir=None, *tags, **kwargs):
        """
        copy the manifests and associated tests
        - directory : directory to copy to
        - rootdir : root directory to copy to (if not given from manifests)
        - tags : keywords the tests must have
        - kwargs : key, values the tests must match
        """
        # XXX note that copy does *not* filter the tests out of the
        # resulting manifest; it just stupidly copies them over.
        # ideally, it would reread the manifests and filter out the
        # tests that don't match *tags and **kwargs
        
        # destination
        if not os.path.exists(directory):
            os.path.makedirs(directory)
        else:
            # sanity check
            assert os.path.isdir(directory)

        # tests to copy
        tests = self.get(tags=tags, **kwargs)
        if not tests:
            return # nothing to do!

        # root directory
        if rootdir is None:
            rootdir = self.rootdir

        # copy the manifests + tests
        manifests = [os.path.relpath(manifest, rootdir) for manifest in self.manifests()]
        for manifest in manifests:
            destination = os.path.join(directory, manifest)
            dirname = os.path.dirname(destination)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            else:
                # sanity check
                assert os.path.isdir(dirname)
            shutil.copy(os.path.join(rootdir, manifest), destination)
        for test in tests:
            if os.path.isabs(test['name']):
                continue
            source = test['path']
            if not os.path.exists(source):
                print >> sys.stderr, "Missing test: '%s' does not exist!" % source
                continue
                # TODO: should err on strict
            destination = os.path.join(directory, os.path.relpath(test['path'], rootdir))
            shutil.copy(source, destination)
            # TODO: ensure that all of the tests are below the from_dir

    def update(self, from_dir, rootdir=None, *tags, **kwargs):
        """
        update the tests as listed in a manifest from a directory
        - from_dir : directory where the tests live
        - rootdir : root directory to copy to (if not given from manifests)
        - tags : keys the tests must have
        - kwargs : key, values the tests must match
        """
    
        # get the tests
        tests = self.get(tags=tags, **kwargs)

        # get the root directory
        if not rootdir:
            rootdir = self.rootdir

        # copy them!
        for test in tests:
            if not os.path.isabs(test['name']):
                relpath = os.path.relpath(test['path'], rootdir)
                source = os.path.join(from_dir, relpath)
                if not os.path.exists(source):
                    # TODO err on strict
                    print >> sys.stderr, "Missing test: '%s'; skipping" % test['name']
                    continue
                destination = os.path.join(rootdir, relpath)
                shutil.copy(source, destination)


class TestManifest(ManifestParser):
    """
    apply logic to manifests;  this is your integration layer :)
    specific harnesses may subclass from this if they need more logic
    """

    def active_tests(self):

        # ignore disabled tests
        tests = self.get(inverse=True, tags=['disabled'])

        # TODO: could filter out by current platform, existence, etc
        return tests

    def test_paths(self):
        return [test['path'] for test in self.active_tests()]


### utility function(s); probably belongs elsewhere

def convert(directories, pattern=None, ignore=(), write=None):
    """
    convert directories to a simple manifest
    """

    retval = []
    include = []
    for directory in directories:
        for dirpath, dirnames, filenames in os.walk(directory):

            # filter out directory names
            dirnames = [ i for i in dirnames if i not in ignore ]
            dirnames.sort()

            # reference only the subdirectory
            _dirpath = dirpath
            dirpath = dirpath.split(directory, 1)[-1].strip('/')

            if dirpath.split(os.path.sep)[0] in ignore:
                continue

            # filter by glob
            if pattern:
                filenames = [filename for filename in filenames
                             if fnmatch(filename, pattern)]

            filenames.sort()

            # write a manifest for each directory
            if write and (dirnames or filenames):
                manifest = file(os.path.join(_dirpath, write), 'w')
                for dirname in dirnames:
                    print >> manifest, '[include:%s]' % os.path.join(dirname, write)
                for filename in filenames:
                    print >> manifest, '[%s]' % filename
                manifest.close()

            # add to the list
            retval.extend([os.path.join(dirpath, filename)
                           for filename in filenames])

    if write:
        return # the manifests have already been written!
  
    retval.sort()
    retval = ['[%s]' % filename for filename in retval]
    return '\n'.join(retval)

### command line attributes

class ParserError(Exception):
  """error for exceptions while parsing the command line"""

def parse_args(_args):
    """
    parse and return:
    --keys=value (or --key value)
    -tags
    args
    """


    # return values
    _dict = {}
    tags = []
    args = []

    # parse the arguments
    key = None
    for arg in _args:
        if arg.startswith('---'):
            raise ParserError("arguments should start with '-' or '--' only")
        elif arg.startswith('--'):
            if key:
                raise ParserError("Key %s still open" % key)
            key = arg[2:]
            if '=' in key:
                key, value = key.split('=', 1)
                _dict[key] = value
                key = None
                continue
        elif arg.startswith('-'):
            if key:
                raise ParserError("Key %s still open" % key)
            tags.append(arg[1:])
            continue
        else:
            if key:
                _dict[key] = arg
                continue
            args.append(arg)

    # return values
    return (_dict, tags, args)


### classes for subcommands

class CLICommand(object):
    usage = '%prog [options] command'
    def __init__(self, parser):
      self._parser = parser # master parser
    def parser(self):
      return OptionParser(usage=self.usage, description=self.__doc__,
                          add_help_option=False)

class Copy(CLICommand):
    usage = '%prog [options] copy manifest directory -tag1 -tag2 --key1=value1 --key2=value2 ...'
    def __call__(self, options, args):
      # parse the arguments
      try:
        kwargs, tags, args = parse_args(args)
      except ParserError, e:
        self._parser.error(e.message)

      # make sure we have some manifests, otherwise it will
      # be quite boring
      if not len(args) == 2:
        HelpCLI(self._parser)(options, ['copy'])
        return

      # read the manifests
      # TODO: should probably ensure these exist here
      manifests = ManifestParser()
      manifests.read(args[0])

      # print the resultant query
      manifests.copy(args[1], None, *tags, **kwargs)


class CreateCLI(CLICommand):
    """
    create a manifest from a list of directories
    """
    usage = '%prog [options] create directory <directory> <...>'

    def parser(self):
        parser = CLICommand.parser(self)
        parser.add_option('-p', '--pattern', dest='pattern',
                          help="glob pattern for files")
        parser.add_option('-i', '--ignore', dest='ignore',
                          default=[], action='append',
                          help='directories to ignore')
        parser.add_option('-w', '--in-place', dest='in_place',
                          help='Write .ini files in place; filename to write to')
        return parser

    def __call__(self, _options, args):
        parser = self.parser()
        options, args = parser.parse_args(args)

        # need some directories
        if not len(args):
            parser.print_usage()
            return

        # add the directories to the manifest
        for arg in args:
            assert os.path.exists(arg)
            assert os.path.isdir(arg)
            manifest = convert(args, pattern=options.pattern, ignore=options.ignore,
                               write=options.in_place)
        if manifest:
            print manifest


class WriteCLI(CLICommand):
    """
    write a manifest based on a query
    """
    usage = '%prog [options] write manifest <manifest> -tag1 -tag2 --key1=value1 --key2=value2 ...'
    def __call__(self, options, args):

        # parse the arguments
        try:
            kwargs, tags, args = parse_args(args)
        except ParserError, e:
            self._parser.error(e.message)

        # make sure we have some manifests, otherwise it will
        # be quite boring
        if not args:
            HelpCLI(self._parser)(options, ['write'])
            return

        # read the manifests
        # TODO: should probably ensure these exist here
        manifests = ManifestParser()
        manifests.read(*args)

        # print the resultant query
        manifests.write(global_tags=tags, global_kwargs=kwargs)
      

class HelpCLI(CLICommand):
    """
    get help on a command
    """
    usage = '%prog [options] help [command]'

    def __call__(self, options, args):
        if len(args) == 1 and args[0] in commands:
            commands[args[0]](self._parser).parser().print_help()
        else:
            self._parser.print_help()
            print '\nCommands:'
            for command in sorted(commands):
                print '  %s : %s' % (command, commands[command].__doc__.strip())

class SetupCLI(CLICommand):
    """
    setup using setuptools
    """
    usage = '%prog [options] setup [setuptools options]'
    
    def __call__(self, options, args):
        sys.argv = [sys.argv[0]] + args
        assert setup is not None, "You must have setuptools installed to use SetupCLI"
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            filename = os.path.join(here, 'README.txt')
            description = file(filename).read()
        except:    
            description = ''
        os.chdir(here)

        setup(name='ManifestDestiny',
              version=version,
              description="universal reader for manifests",
              long_description=description,
              classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
              keywords='mozilla manifests',
              author='Jeff Hammel',
              author_email='jhammel@mozilla.com',
              url='https://wiki.mozilla.org/Auto-tools/Projects/ManifestDestiny',
              license='MPL',
              zip_safe=False,
              py_modules=['manifestparser'],
              install_requires=[
                  # -*- Extra requirements: -*-
                  ],
              entry_points="""
              [console_scripts]
              manifestparser = manifestparser:main
              """,
              )


class UpdateCLI(CLICommand):
    """
    update the tests as listed in a manifest from a directory
    """
    usage = '%prog [options] update manifest directory -tag1 -tag2 --key1=value1 --key2=value2 ...'

    def __call__(self, options, args):
        # parse the arguments
        try:
            kwargs, tags, args = parse_args(args)
        except ParserError, e:
            self._parser.error(e.message)

        # make sure we have some manifests, otherwise it will
        # be quite boring
        if not len(args) == 2:
            HelpCLI(self._parser)(options, ['update'])
            return

        # read the manifests
        # TODO: should probably ensure these exist here
        manifests = ManifestParser()
        manifests.read(args[0])

        # print the resultant query
        manifests.update(args[1], None, *tags, **kwargs)


# command -> class mapping
commands = { 'create': CreateCLI,
             'help': HelpCLI,
             'update': UpdateCLI,
             'write': WriteCLI }
if setup is not None:
    commands['setup'] = SetupCLI

def main(args=sys.argv[1:]):
    """console_script entry point"""

    # set up an option parser
    usage = '%prog [options] [command] ...'
    description = __doc__
    parser = OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--strict', dest='strict',
                      action='store_true', default=False,
                      help='adhere strictly to errors')
    parser.disable_interspersed_args()

    options, args = parser.parse_args(args)

    if not args:
        HelpCLI(parser)(options, args)
        parser.exit()

    # get the command
    command = args[0]
    if command not in commands:
        parser.error("Command must be one of %s (you gave '%s')" % (', '.join(sorted(commands.keys())), command))

    handler = commands[command](parser)
    handler(options, args[1:])

if __name__ == '__main__':
    main()
