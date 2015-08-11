# coding: utf-8
'''
Created on Jul 28, 2014

@author: Noah
'''
import logging
import os
from _collections import defaultdict
import Utils
log = logging.getLogger(__name__)

def walkfail(self, error):
        log.warning("Failed to access file: {}".format(error.filename))
        log.warning(error)
        log.warning("Check permissions?")

class DirectoryCache:
    '''
    Provides a quick way to locate potential file matches by file size
    '''


    def __init__(self, directorypath):
        '''
        Builds a directory cache using the given directorypath
        '''
        self.cacheinfo = defaultdict(set)
        self.walkDirs(directorypath)

    def walkDirs(self, directorypath):
        for root, dirs, files in os.walk(unicode(directorypath), onerror=walkfail):
            # Make path absolute, and take care of win32 API behavior
            root = Utils.windowsPathLengthLimitWorkaround(os.path.abspath(root))
            for f in files:
                filepath = os.path.join(root, f)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    self.cacheinfo[size].add(DirectoryCacheFile(f, filepath, size))
                else:
                    log.warn("os.walk-ed file isn't accessible/doesn't exist: rootpath: {}".format(filepath.encode("utf-8")))

    def getFilesWithSize(self, size):
        return set(self.cacheinfo[size])

    def writeUnmatchedFilesReport(self, reportfile):
        unmatchedFiles = list()
        for dcfs in self.cacheinfo.itervalues():
            for dcf in dcfs:
                if not dcf.isLinked:
                    unmatchedFiles.append(dcf)
        unmatchedFiles.sort(key=lambda dcf: dcf.path)
        for dcf in unmatchedFiles:
            reportfile.write(dcf.path.encode("utf-8") + "\n")
            

class DirectoryCacheFile:
    '''
    Contains information about a file on your filesystem (size, name and path)
    '''
    def __init__(self, name, path, size):
        self.name = name
        self.path = path
        self.size = size
        self.isLinked = False

    def __unicode__(self):
        return self.fullPath()

    def __str__(self):
        return self.__unicode__().encode("utf-8")

    def __repr__(self):
        return "DCFI|" + self.__str__()

    def fullPath(self):
        return self.path

    def getSize(self):
        return self.size;
    
    def setIsLinked(self, isLinked):
        self.isLinked = isLinked