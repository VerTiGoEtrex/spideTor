'''
Created on Aug 2, 2014

@author: Noah
'''

class FileCache:
    '''
    Will cache small portions of a DirectoryCacheFile to allow for faster repeated access. This is crucial when the crossproduct is large (small files/large pieces)
    '''


    def __init__(self, piece, potentialMatchesForMetafileFile):
        self.cache = {}
        for metafileFileWithOffset in piece.getFileWithOffsetsInPiece():
            for directoryCacheFile in potentialMatchesForMetafileFile[metafileFileWithOffset.getMetafileFile()]:
                self.addDirectoryCacheFile(directoryCacheFile, metafileFileWithOffset.getStartOffset(), metafileFileWithOffset.getReadLength())

    def addDirectoryCacheFile(self, realfile, startOffset, readLength):
        with open(realfile.fullPath(), 'rb') as openedFile:
            openedFile.seek(startOffset)
            self.cache[(realfile, startOffset, readLength)] = openedFile.read(readLength)

    def getCachedData(self, realfile, startOffset, readLength):
        return self.cache[(realfile, startOffset, readLength)]
