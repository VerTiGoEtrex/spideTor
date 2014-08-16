#!/usr/local/bin/python2.7
# coding: utf-8
'''
spideTor -- Seed your renamed files

spideTor is a utilty that analyzes your torrent metadata files and links your renamed or moved files to a directory structure emulating the metafile.

NOTICE: No support for merkle trees (yet?) (http://www.bittorrent.org/beps/bep_0030.html)

@author:     Noah Crocker

@copyright:  2014 Noah Crocker. All rights reserved.

@license:    Apache 2.0

@contact:    noahecrocker@gmail.com
@deffield    updated: Updated
'''

#############
# LIBRARIES #
#############

import sys
import os
import logging
import glob

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
import shutil
import pprint
from PieceMatcher import matchAllFilesInMetaFile
import pickle

###########
# GLOBALS #
###########

__all__ = []
__version__ = 0.1
__date__ = '2014-07-22'
__updated__ = '2014-08-15'
log = logging.getLogger()
pp = pprint.PrettyPrinter(indent = 1, width = 80)

#################
# LOCAL MODULES #
#################

from Metafile import Metafile
from DirectoryCache import DirectoryCache
import Utils

#####################################
# PATCH SYMLINK ON WINDOWS MACHINES #
#####################################

if os.name == "nt" or os.name == "ce":
    import ctypes

    #Symlinks can't be made unless run with adminstrator privs
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print "You must run this application with administrator privileges (try \"run as admin\" in the right-click menu"
        sys.exit(1)

    csl = ctypes.windll.kernel32.CreateSymbolicLinkW
    csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    csl.restype = ctypes.c_ubyte

    def windowsSymlink(source, link_name):
        '''symlink(source, link_name)
        Creates a symbolic link pointing to source named link_name'''
        flags = 0
        if source is not None and os.path.isdir(source):
            flags = 1
        if csl(link_name, source, flags) == 0:
            raise ctypes.WinError()

    mysymlink = windowsSymlink
else:
    mysymlink = os.symlink



#####################
# DEVELOPMENT FLAGS #
#####################

PROFILE = 0
SHOWHELP = 0
DEBUG = 1

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by Noah Crocker on %s.
  Copyright 2014 Noah Crocker. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-v", "--verbose", action="count", dest="verbose", default = 0, help="set verbosity")
        parser.add_argument('-V', '--version', action='version', version=program_version_message)
        parser.add_argument("-q", "--quick", dest="quick", action="store_true", help="Check the minimum number of pieces to verify the file (this will VERY rarely report false positives)")
        mutexgroup = parser.add_mutually_exclusive_group(required=True)
        mutexgroup.add_argument("-b", "--batch", dest="batch", metavar="METAFILEDIR", help="directory containing .torrent metafiles for batch processing")
        mutexgroup.add_argument("-m", "--metafile", dest="metafile", help="target .torrent metafile for directory reconstruction")
        parser.add_argument("-s", "--source", dest="sourcedir", help="directory you suspect contains the renamed/moved files in the metafile", required=True)
        parser.add_argument("-t", "--target", dest="targetdir", help="directory to fill with symlinks to your renamed files", required=True)

        # Process arguments
        args = parser.parse_args()

        verbose = args.verbose
        quick = args.quick
        batch = args.batch
        metafile = args.metafile
        sourcedir = args.sourcedir
        targetdir = args.targetdir

        # Verify args and setup logger
        # verbose
        log.setLevel(max(2 - verbose, 1) * 10)
        ch = logging.StreamHandler()
        ch.setLevel(max(2 - verbose, 1) * 10)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        log.addHandler(ch)

        if quick:
            log.info("Running in quick mode :)")

        log.debug("Verifying that necessary directories and files exist")

        # if batchdir is set, ensure it's a directory
        if batch != None:
            if not os.path.isdir(batch):
                raise Exception("Specified batch directory {} is not a directory".format(batch))
            unmatcheddir = batch + os.sep + "_unmatched"
            matcheddir = batch + os.sep + "_matched"

        # if metafile is set, ensure it exists and is readable
        if metafile != None:
            if os.path.exists(metafile):
                if not os.access(metafile, os.R_OK):
                    raise Exception("Specified metafile {} is not accessible (check permissions?)".format(metafile))
            else:
                raise Exception("Specified metafile {} does not exist".format(metafile))
            unmatcheddir = os.path.dirname(metafile) + os.sep + "_unmatched"
            matcheddir = os.path.dirname(metafile) + os.sep + "_matched"

        # ensure sourcedir is a directory, and is accessible
        if not os.path.isdir(sourcedir):
            raise Exception("Specified source directory {} is not a directory".format(sourcedir))

        # ensure targetdir is a directory, or create if necessary
        if os.path.exists(targetdir):
            if not os.path.isdir(targetdir):
                raise Exception("Specified target directory {} conflicts with a file of the same name".format(targetdir))
        else:
            os.makedirs(targetdir)

        # make the unmatched directory
        if os.path.exists(unmatcheddir):
            if not os.path.isdir(unmatcheddir):
                raise Exception("unmatcheddir directory {} conflicts with a file of the same name".format(unmatcheddir))
        else:
            os.makedirs(unmatcheddir)

        # make the matched directory
        if os.path.exists(matcheddir):
            if not os.path.isdir(matcheddir):
                raise Exception("matcheddir directory {} conflicts with a file of the same name".format(matcheddir))
        else:
            os.makedirs(matcheddir)

        # Phase 1: Read the metafile(s)
        log.info("=====Phase 1: Read the metafiles=====")
        metafilelist = []
        if batch != None:
            log.info("Batch mode")
            torrentfilepaths = glob.glob(u"{}/*.torrent".format(batch))
            if len(torrentfilepaths) == 0:
                log.error("Couldn't find any \".torrent\" files in specified directory")
                return
            for idx, f in enumerate(torrentfilepaths):
                log.info("Adding metafile [{}/{}]: {}".format(idx+1, len(torrentfilepaths), f.encode("utf-8")))
                metafilelist.append(Metafile(f))
        else:
            log.info("Single mode")
            log.info("Adding metafile: {}".format(metafile))
            metafilelist.append(Metafile(metafile))

        # Phase 2: Populate source directory cache
        log.info("=====Phase 2: Populating source directory cache (this might take a while)=====")
        sourcedirectorycache = DirectoryCache(sourcedir)
        # === DEBUG CODE (for skipping directory cache generation) ===
#        if not os.path.exists("dircache.pickle"):
#            with open("dircache.pickle", 'w') as pickled:
#                sourcedirectorycache = DirectoryCache(sourcedir)
#                pickle.dump(sourcedirectorycache, pickled)
#        else:
#            with open("dircache.pickle", 'r') as pickled:
#                sourcedirectorycache = pickle.load(pickled)
        # === /DEBUG CODE/ ===

        # Phase 3: Find matches and create symlinks
        log.info("=====Phase 3: Finding matches=====")
        matchedmetafiles = []
        unmatchedmetafiles = []
        for idx, metafile in enumerate(metafilelist):
            log.info("Metafile [{}/{}]: {}".format(idx+1, len(metafilelist), metafile))
            matchedFilesMap = matchAllFilesInMetaFile(metafile, sourcedirectorycache, quick)
            if matchedFilesMap != None and makeSymlinksFromFileMap(metafile, matchedFilesMap, targetdir) == True:
                #Entire metafile was matched
                matchedmetafiles.append(metafile)
                shutil.move(metafile.getMetafilePath(), matcheddir)
            else:
                unmatchedmetafiles.append(metafile)
                shutil.move(metafile.getMetafilePath(), unmatcheddir)

        # Phase 4: Print a report
        log.info("Finished!")
        log.info("Matched metafiles:")
        for metafile in matchedmetafiles:
            log.info("\tName: {}   ---   Path: {}".format(metafile.getName().encode("utf-8"), metafile.getMetafilePath().encode("utf-8")))
        log.info("")
        log.info("Unmatched metafiles:")
        for metafile in unmatchedmetafiles:
            log.info("\tName: {}   ---   Path: {}".format(metafile.getName().encode("utf-8"), metafile.getMetafilePath().encode("utf-8")))

        return 0
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
#    except Exception, e:
#        if DEBUG:
#            raise(e)
#        log.critical(e)
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": unrecoverable error\n")
        sys.stderr.write(indent + "  for help use -h/--help")
        return 2

def makeSymlinksFromFileMap(metafile, fileMap, rootdir):

    for metafilefile, realfile in fileMap.iteritems():
        #Make sure directories exist to metafilefile
        if metafile.isSingleFileTorrent():
            targetfile = os.path.join(rootdir, metafilefile.getPath())
        else:
            targetfile = os.path.join(rootdir, metafile.getName(), metafilefile.getPath())
        #Windows is #1
        targetfile = Utils.windowsPathLengthLimitWorkaround(targetfile)
        targetdir = os.path.dirname(targetfile)
        if not os.path.exists(targetdir):
            log.debug("Path doesn't exist, creating: {}".format(targetdir.encode("utf-8")))
            os.makedirs(targetdir)

        #Create symlink from targetfile to the real file
        if os.path.exists(targetfile):
            log.warn("File already exists in your symlink directory -- Not making link: {}".format(targetfile.encode("utf-8")))
            continue

        sourcefile = Utils.windowsPathLengthLimitWorkaround(realfile.fullPath())
        log.debug("Source: {}".format(sourcefile.encode("utf-8")))
        log.debug("Target: {}".format(targetfile.encode("utf-8")))
        try:
            symlinkresult = mysymlink(sourcefile, targetfile)
        except Exception, e:
            log.error("Error creating symlink: {}".format(e))
            return False
    return True

if __name__ == "__main__":
    if SHOWHELP:
        sys.argv.append("-h");
    if PROFILE:
        import cProfile
        import pstats
        profile_filename = 'spideTor_profile.txt'
        cProfile.run('main()', profile_filename)
        statsfile = open("profile_stats.txt", "wb")
        p = pstats.Stats(profile_filename, stream=statsfile)
        stats = p.strip_dirs().sort_stats('cumulative')
        stats.print_stats()
        statsfile.close()
        sys.exit(0)
    sys.exit(main())