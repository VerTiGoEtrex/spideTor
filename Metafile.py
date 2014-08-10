# coding: utf-8
'''
Created on Jul 24, 2014

@author: Noah
'''

import bencode
import logging
import pprint
import os.path
log = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent = 1, width = 80)
HASHLEN = 20


class Metafile:
    '''
    Decodes the metadata stored in a .torrent metafile and presents a standard interface to access it
    
    Notice about the bencode library. Everything is encoded in UTF-8 strings, so you must .decode them to get them back to unicode
    '''


    def __init__(self, metafilepath):
        self.metafilepath = metafilepath
        with open(metafilepath, 'rb') as metafile:
            encoded = metafile.read()
            log.debug("Read metafile successfully")
        log.debug("decoding bencoded data")
        self.decoded = bencode.bdecode(encoded)
        log.debug("decoded as {}".format(pp.pformat(self.decoded)))
        if self.isSingleFileTorrent():
            log.debug("metafile appears to be a single file metafile")
        else:
            log.debug("metafile appears to contain many files")
        self.files = None
            
    def __unicode__(self):
        return self.metafilepath
    
    def __str__(self):
        return self.__unicode__().encode("utf-8")
    
    def getMetafileFiles(self):
        if self.files != None:
            return self.files
        self.files = []
        if self.isSingleFileTorrent():
            self.files.append(MetafileFile(self.getName(), self.decoded['info']['length']))
        else:
            for metadata in self.decoded['info']['files']:
                self.files.append(MetafileFile(os.path.join(*(path.decode("utf-8") for path in metadata['path'])), metadata['length']))
        return self.files
    
    def getPieces(self):
        hashes = self.getHashes()
        log.debug("Number of pieces: {}".format(len(hashes)))
        
        pieceLength = self.decoded['info']['piece length']
        log.debug("Piece length: {}".format(pieceLength))
        
        pieces = []
        
        # Populate all of the constant-length pieces
        metafileFiles = self.getMetafileFiles()
        fileIterator = iter(metafileFiles)
        currentFile = fileIterator.next()
        currentPiecePosition = 0
        currentFileReadPosition = 0
        prevPiece = None
        for pieceNumber in xrange(0, len(hashes)):
            # Get files in this piece (similar to a merge)
            # This is a list, because ordering matters
            filesInPiece = []
            
            # If this file ends inside this piece, then advance to the next one and add it too
            #Piece ------XXXXX-----
            #File  --XXXXXX++++----
            #AND ALSO
            #Piece ------XXXXX-----
            #File  --XXXXXXXXX+++--
            bytesReadInPiece = 0
            while currentPiecePosition + currentFile.getSize() <= (pieceNumber + 1) * pieceLength:
                currentPiecePosition += currentFile.getSize()
                bytesRemainingInFile = currentFile.getSize() - currentFileReadPosition
                filesInPiece.append(MetafileFileWithOffset(currentFile, currentFileReadPosition, bytesRemainingInFile, (currentFileReadPosition == 0)))
                bytesReadInPiece += bytesRemainingInFile
                currentFileReadPosition = 0
                try:
                    currentFile = fileIterator.next()
                except StopIteration, e:
                    # That was the last file. This should be the last piece, which is asserted later.
                    currentFile = None
                    break
            
            if currentFile != None:
                bytesToRead = min(pieceLength - bytesReadInPiece, currentFile.getSize() - currentFileReadPosition)
                filesInPiece.append(MetafileFileWithOffset(currentFile, currentFileReadPosition, bytesToRead, False))
                currentFileReadPosition += bytesToRead
            elif not pieceNumber == len(hashes)-1 or len(filesInPiece) == 0: #Assert that this is the last piece
                log.error("Ran out of files on piece {} / {}".format(pieceNumber, len(hashes)-1))
                return
            
            log.debug("Piece [{}/{}]: {} files".format(pieceNumber, len(hashes)-1, len(filesInPiece)))
            pieceToInsert = Piece(pieceNumber, hashes[pieceNumber], pieceLength, filesInPiece)
            
            # Setup linked list (for heapq updating)
            pieceToInsert.setPrevPiece(prevPiece)
            if prevPiece != None:
                prevPiece.setNextPiece(pieceToInsert)
            pieces.append(pieceToInsert)
            prevPiece = pieceToInsert
        return pieces
            
        
        
        
    def getHashes(self):
        allHashes = self.decoded['info']['pieces']
        return [allHashes[window:window+HASHLEN] for window in xrange(0, len(allHashes), HASHLEN)]
    
    def getName(self):
        return self.decoded['info']['name'].decode("utf-8")
        
    def isSingleFileTorrent(self):
        return 'length' in self.decoded['info']
    
    def getMetafilePath(self):
        return self.metafilepath
    
class Piece:
    '''
    Holds information about a "piece" in the metafile
    '''
    
    def __init__(self, pieceNumber, pieceHash, pieceLength, fileWithOffsetsInPiece):
        self.pieceNumber = pieceNumber
        self.pieceHash = pieceHash
        self.pieceLength = pieceLength
        self.fileWithOffsetsInPiece = fileWithOffsetsInPiece
        self.nextPiece = None
        self.prevPiece = None
        
    def getPieceNumber(self):
        return self.pieceNumber
        
    def getFileWithOffsetsInPiece(self):
        return self.fileWithOffsetsInPiece
    
    def getHash(self):
        return self.pieceHash
    
    def getPieceLength(self):
        return self.pieceLength
    
    def oneFileInPiece(self):
        return len(self.fileWithOffsetsInPiece) == 1
    
    def getOneFileInPiece(self):
        if self.oneFileInPiece():
            return next(iter(self.fileWithOffsetsInPiece))
        
    def setPrevPiece(self, prevPiece):
        self.prevPiece = prevPiece
        
    def setNextPiece(self, nextPiece):
        self.nextPiece = nextPiece
        
    def getPrevPiece(self):
        return self.prevPiece
    
    def getNextPiece(self):
        return self.nextPiece

class MetafileFile:
    '''
    Holds more detailed information about a file within a metafile
    '''


    def __init__(self, file_path, size):
        '''
        Constructs a new MetafileFile object
        '''
        self.file_path = file_path
        self.size = size
        
    def __unicode__(self):
        return self.getPath()
    
    def __str__(self):
        return self.__unicode__().encode("utf-8")
        
    def getPath(self):
        return self.file_path
    
    def getSize(self):
        return self.size
    
class MetafileFileWithOffset:
    '''
    Holds some additional information about a file as it relates to a piece
    '''
    
    def __init__(self, metafileFile, startOffset, readLength, entirelyInPiece):
        self.metafileFile = metafileFile
        self.startOffset = startOffset
        self.readLength = readLength
        self.entirelyInPiece = entirelyInPiece
        
    def __str__(self):
        return self.__unicode__().encode("utf-8")
    
    def __unicode__(self):
        return unicode(self.metafileFile)
    
    def __repr__(self):
        return "MFWO|" + self.__str__()
    
    def getMetafileFile(self):
        return self.metafileFile
    
    def getStartOffset(self):
        return self.startOffset
    
    def getReadLength(self):
        return self.readLength
    
    def fileEntirelyInPiece(self):
        return self.entirelyInPiece