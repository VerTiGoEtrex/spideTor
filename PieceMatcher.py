'''
Created on Aug 3, 2014

@author: Noah
'''

import logging
from _collections import defaultdict
from FileCache import FileCache
import hashlib
from heapdict import heapdict
log = logging.getLogger(__name__)

class sha1BruteForcer:
    '''
    Brute forces file combinations to reveal sha1
    '''
    def __init__(self, piece, fileCache, potentialMatchesForMetafileFile, verifiedAnEntirePiece):
        self.piece = piece
        self.fileCache = fileCache
        self.potentialMatchesForMetafileFile = potentialMatchesForMetafileFile
        self.verifiedAnEntirePiece = verifiedAnEntirePiece
        self.matchingCombinations = []
        self.combinationsTried = 0
        
    def bruteForce(self):
        '''
        Test all possible pairings of files in piece (maintaining ordering) to find matching combination(s)
        Hopefully, exactly one combination matches the hash.
        '''
        rootsha1 = hashlib.sha1()
        remainingFiles = list(self.piece.getFileWithOffsetsInPiece())
        remainingFiles.reverse()
        self._bruteForceHelper(rootsha1, {}, remainingFiles)
        log.debug("\t=== Finished bruteforcing ===")
        log.debug("\tPredicted number of combinations: {}".format(getNumberOfCombinations(self.potentialMatchesForMetafileFile, self.piece)))
        log.debug("\tActual number of combinations: {}".format(self.combinationsTried))
        log.debug("\tfound {} matching combinations".format(len(self.matchingCombinations)))
        
        if self.piece.oneFileInPiece() and len(self.matchingCombinations) > 0:
            #We verified entire piece-worth of this file
            log.debug("\tverified piece-worth of file: {}".format(self.piece.getOneFileInPiece().getMetafileFile()))
            self.verifiedAnEntirePiece.add(self.piece.getOneFileInPiece().getMetafileFile())
            
        return self.matchingCombinations
        
    def _bruteForceHelper(self, sha1SoFar, pickedFiles, remainingFiles):
        '''
        DFS. Takes advantage of partially built SHA1 to cut down on computation time.
        
        TODO: It might be valuable to multi-thread this or link it to C++
        
        sha1SoFar(hashlib.sha1): sha1 builder that holds the sha1 of the selected files up until this point.
        pickedFiles(dict): files that are already selected for testing. MetafileFile => potl matching directoryCacheFile
        remainingFiles(deque): unexplored branch nodes (which we recurse on)
        '''
        
        if len(remainingFiles) == 0:
            #Base case: No more files to try to match, just test the Sha1
            if sha1SoFar.digest() == self.piece.getHash():
                #Hashes match, record this combination
                self.matchingCombinations.append(pickedFiles.copy())
            self.combinationsTried += 1
            if self.combinationsTried % 10000 == 0:
                log.info("\tTried {} combinations so far".format(self.combinationsTried))
            return
        
        #Get the next file in the branch
        ourFile = remainingFiles.pop()
        
        #Test each of the potential matches for this file
        for directoryCacheFile in self.potentialMatchesForMetafileFile[ourFile.getMetafileFile()] - set(pickedFiles.itervalues()):
            pickedFiles[ourFile] = directoryCacheFile
            ourSha1 = sha1SoFar.copy()
            ourSha1.update(self.fileCache.getCachedData(directoryCacheFile, ourFile.getStartOffset()))
            self._bruteForceHelper(ourSha1, pickedFiles, remainingFiles)
        
        #Restore this file back onto the "remainingFiles" branch
        del pickedFiles[ourFile]
        remainingFiles.append(ourFile)
        

def getNumberOfCombinations(potentialMatchesForMetafileFile, piece):
    # Figure out worst case number of combinations we'll need to check
    numberOfCombinations = 1
    for fileWithOffset in piece.getFileWithOffsetsInPiece():
        numberOfCombinations *= len(potentialMatchesForMetafileFile[fileWithOffset.getMetafileFile()])
    return numberOfCombinations

def canSkip(potentialMatchesForMetafileFile, verifiedAnEntirePiece, piece):
    '''
    Files that have only one potential match and have been verified against at least one entire piece
    are considered skippable in quick mode (we don't need to evaluate any more of their pieces)
    '''
    for fileWithOffset in piece.getFileWithOffsetsInPiece():
        metafileFile = fileWithOffset.getMetafileFile()
        if len(potentialMatchesForMetafileFile[metafileFile]) != 1 and metafileFile not in verifiedAnEntirePiece:
            return False
    return True

def findPotentialMatches(files, directorycache):
    '''
    Returns a set of MetafileFile => set of potential DirectoryCache Files using the directoryCache
    '''
    filesWithMatches = defaultdict(set)
    for idy, f in enumerate(files):
        log.debug("Matching file by size [{}/{}]:".format(idy+1, len(files)))
        log.debug("\tPath: {}".format(f))
        log.debug("\tSize: {}".format(f.getSize()))
        potentialmatches = directorycache.getFilesWithSize(f.getSize());
        if not potentialmatches or len(potentialmatches) == 0:
            log.warn("No match for file {} found.".format(f))
            return False
        log.debug("\tFound {} potential matches for this file:".format(len(potentialmatches)))
        for potentialmatch in potentialmatches:
            log.debug("\t\t{}".format(potentialmatch))
        filesWithMatches[f] = potentialmatches
    return filesWithMatches

def matchPieceToFiles(quick, piece, potentialMatchesForMetafileFile, verifiedAnEntirePiece):
    log.debug("Solving piece with combinations: {}".format(getNumberOfCombinations(potentialMatchesForMetafileFile, piece)))
    log.debug("pieceNumber: {}".format(piece.getPieceNumber()))
    log.debug("Number of files: {}".format(len(piece.getFileWithOffsetsInPiece())))
    log.debug("Files")
    for fileWithOffset in piece.getFileWithOffsetsInPiece():
        log.debug(fileWithOffset.getMetafileFile())
    if quick and canSkip(potentialMatchesForMetafileFile, verifiedAnEntirePiece, piece):
        # Skip this file if we're in quick mode and the file has already been matched
        log.debug("piece was skippable")
        return True
    
    # Cache all of the possibly needed file parts
    fileCache = FileCache(piece, potentialMatchesForMetafileFile)
    
    # Match the files in this piece as best we can
    #TODO: add support for merkle hashes/trees
    if len(piece.getFileWithOffsetsInPiece()) > 1:
        log.debug("Trying to match a file with more than one piece using brute force")
    matcher = sha1BruteForcer(piece, fileCache, potentialMatchesForMetafileFile, verifiedAnEntirePiece)
    matchingCombinations = matcher.bruteForce()
    
    if len(matchingCombinations) > 1:
        log.warn("FOUND > 1 MATCHING COMBINATIONS! (duplicate files?)")
        log.warn(matchingCombinations)
    
    if len(matchingCombinations) == 0:
        #TODO: create partial structures?
        log.debug("No combinations found for files:")
        for fileWithOffset in piece.getFileWithOffsetsInPiece():
            log.debug(fileWithOffset.getMetafileFile())
        return False
    
    #Update the potentialMatchesForMetafileFile map
    for fileWithOffset in piece.getFileWithOffsetsInPiece():
        metafileFile = fileWithOffset.getMetafileFile()
        potentialMatchesForMetafileFile[metafileFile] = set()
    for matchingCombination in matchingCombinations:
        for metafileFile, directoryCacheFile in matchingCombination.iteritems():
            potentialMatchesForMetafileFile[metafileFile.getMetafileFile()].add(directoryCacheFile)
            
    return True

#from profilehooks import profile
#@profile(entries = 800)
def matchAllFilesInMetaFile(metafile, directorycache, quick):
    metafileFiles = metafile.getMetafileFiles()
    
    # We can narrow down the search space by only considering DirectoryCacheFiles that are the same size
    potentialMatchesForMetafileFile = findPotentialMatches(metafileFiles, directorycache)
    if potentialMatchesForMetafileFile == False:
        log.warn("Skipping metafile because we couldn't find match for a file in metafile: {}".format(metafile))
        return
    
    log.debug("Mapping metafile pieces to metafile files")
    log.debug("Match by hash:")
    
    piecesToVerify = metafile.getPieces()
    verifiedAnEntirePiece = set()
    
    log.debug("Resolving pieces in least-complex first order")
    
    # First we need a min-heap of the remaining pieces (compared by how many combinations they have)
    pieceHeap = heapdict() # TODO: This is nlog(n) construction, because there's no heapify constructor
    for piece in piecesToVerify:
        if piece.oneFileInPiece():
            if not matchPieceToFiles(quick, piece, potentialMatchesForMetafileFile, verifiedAnEntirePiece):
                log.debug("Necessary pieces could not be verified. Skipping this metafile.")
                return
        else:
            #This is a more complicated piece. Solve it later.
            pieceHeap[piece] = getNumberOfCombinations(potentialMatchesForMetafileFile, piece)
    
    
    # TODO: This handles cross-piece files very poorly. For pieces that contain an entire file in them and 
    # have multiple matches with a cross-piece file, if that cross-piece file has matches eliminated later,
    # we might select files for this piece that are wrong.
    
    # POSSIBLE SOLUTION: If a piece that contains multiple files in it has multuple matching combinations, 
    # insert it into a "re-check" queue that will try to match it again after more pieces has been 
    # 100% matched to a single combination of files
    
    # REASON THIS ISN'T FIXED: It's VERY unlikely. We'd have to have several hash collisions, which I don't 
    # claim to resolve anyway
    
    try:
        pieceTuple = pieceHeap.popitem()
    except IndexError, e:
        pieceTuple = None
    while pieceTuple != None:
        piece = pieceTuple[0]
        if getNumberOfCombinations(potentialMatchesForMetafileFile, piece) > 10000:
            # We're trying to do the impossible here... (this is a crossproduct)
            # It's probably good to let the user know that SOMETHING it happening...
            log.info("Piece {} has as many as {} potential combinations. This might take a while.".format(piece.getPieceNumber(), getNumberOfCombinations(potentialMatchesForMetafileFile, piece)))
        if not matchPieceToFiles(quick, piece, potentialMatchesForMetafileFile, verifiedAnEntirePiece):
            log.warn("Necessary pieces could not be verified. Skipping this metafile.")
            return
                
        #Update the neighbors in the heap
        if piece.getNextPiece() != None and piece.getNextPiece() in pieceHeap:
            updatedCost = getNumberOfCombinations(potentialMatchesForMetafileFile, piece.getNextPiece())
            if pieceHeap[piece.getNextPiece()] != updatedCost:
                log.debug("Updated cost of piece {} FROM {} TO {}".format(piece.getNextPiece().getPieceNumber(), pieceHeap[piece.getNextPiece()], updatedCost))
                pieceHeap[piece.getNextPiece()] = updatedCost
        if piece.getPrevPiece() != None and piece.getPrevPiece() in pieceHeap:
            updatedCost = getNumberOfCombinations(potentialMatchesForMetafileFile, piece.getPrevPiece())
            if pieceHeap[piece.getPrevPiece()] != updatedCost:
                log.debug("Updated cost of piece {} FROM {} TO {}".format(piece.getNextPiece().getPieceNumber(), pieceHeap[piece.getPrevPiece()], updatedCost))
                pieceHeap[piece.getPrevPiece()] = updatedCost
        
        try:
            pieceTuple = pieceHeap.popitem()
        except IndexError, e:
            pieceTuple = None
     
    #Make sure that each file has only has one match (both directions)
    metafileFilesWithActualMatches = {}
    matchedFileSystem = set()
    for metafileFile, matchingFiles in potentialMatchesForMetafileFile.iteritems():
        if len(matchingFiles) != 1:
            #This metafile file has more than one match on the filesystem
            log.warn("Metafile File didn't resolve to one match: {}".format(metafileFile))
            log.warn("This is likely due to a hash collision or duplicated files")
            log.warn("Matching files: {}".format(len(matchingFiles)))
            for matchingFile in matchingFiles:
                log.warn("{}".format(matchingFile))
        for matchingFile in matchingFiles:
            if matchingFile in matchedFileSystem:
                #This filesystem file has more than one metafile mapped to it
                log.warn("Filesystem file has more than one Metafile File mapped to it: {}".format(iter(matchingFiles).next()))
                log.warn("Maybe you've got tiny files (hash collision), or the metafile contains duplicate files?")
        # If there are multiple matches, just pick the first one
        metafileFilesWithActualMatches[metafileFile] = iter(matchingFiles).next()
    return metafileFilesWithActualMatches