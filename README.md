spideTor
========

Reseed torrent metafiles with renamed or moved files

spideTor is a "weekend hack" project born to solve a personal need. As far as I'm aware, it is the fastest and most robust tool of it's kind, although admittedly, competition is scarce...

In short, spideTor takes .torrent metafiles and a search directory containing the files downloaded as part of the provided .torrent as input. Given some time, spideTor will eventually create a directory structure of symlinks emulating that of the .torrent.  If you're from windows land, you can think of symlinks like shortcuts. They take no space, and simply point to another file.

Due to the nature of brute forcing, spideTor will perform best (fastest) with torrents that contain files that are larger than the torrent piece size. I explain this in further detail later.


Usage
=====

You can get help using
<pre>python spideTor.py -h</pre>

In addition, I've created a short video showing how to use the tool here: (TODO, probably never)

NOTE: On Windows, you must run spideTor with administrator privileges  or else it won't be allowed to create symlinks for you. The easiest way to do this is to use "run as administator" in the explorer context menu when starting your command line.

Features
========

Supported platforms: Windows Vista and above, and Linux (although Linux remains largely untested)

* Unicode support -- This was my first foray into internationalization and may have bugs, but it seems to be very stable.
* Robust mode (verify all pieces) and Quick mode (verify one full piece of a file, at most)
* Network filesystem support under Windows and Linux
* Supports UNC paths (paths over 260 characters on Windows)
* Batch processing mode
* Super fast -- Fastest processing of cross-product pieces that I've been able to find

Challenges
==========

UNC Paths
---------
Windows has a long standing 260 character limit on paths. With the standard drive letter snippet (i.e. C:\\) taking up 3 characters and the null byte taking up 1 character, you end up with 256 usable characters for absolute paths. For further information about this problem, you can read Microsoft's documentation here http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath

This limitation appeared while I was testing spideTor on my own collection of files stored on my Linux-based server. Although the python "walk" function could access the files, os.path.exists would always return null for those long paths and I could not read/write the files. 

As a workaround, I've wrapped most file accesses in a utility function that prepends "\\\\?\\UNC\\" to the paths to tell Windows to not preprocess the path and allow access to paths over 260 characters long. This, of course, only effects paths when running on Windows.

Symlinks
--------
Python 2 does not have a built in symlink function for Windows. As a result, I have to patch the symlink function at runtime if running on Windows to call the kernal32 DLL. In addition, symlinks can only be created on windows if you have Administrator privileges, so I had to add a function to check for the necessary symlink privileges. 

Computational complexity
------------------------
The nature of this project is a challenge in itself. In essence, we're brute forcing a password. Thankfully, there are many tricks that I came up with to make this much easier. However, there are still rare cases where a metafile could take a few days to process as opposed to a few seconds. I go into detail about my approach to simplifying this problem in the "implementation details" section


Implementation details
======================
spideTor is split into stages of execution.

Stage 1 -- Read metafiles
-------------------------
This stage is very simple. I use the bencode libary to decode the binary-encoded metafiles, and then wrap them into their own objects.

Stage 2 -- Fill the directory cache
-----------------------------------
This is the magic that makes this whole project feasible. It obviously doesn't make any sense to match metafile files to filesystem files if they're not the same size, so I created a DirectoryCache class which os.walk(s) your source directory to map a file size to files that are that size.

Stage 3 -- Match the files and create symlinks
---------------------------------------------
In summary, this stage is a semi-intelligent brute-force.

To begin, I create a mapping from metafileFile to a set of potential matches on your filesystem. These potential matches are found using the DirectoryCache created in stage 2. The ultimate goal is to reduce the size of all of the sets to 1. This step is O(n) time.

Next, we can begin eliminating files from the potential matches set by verifying pieces of the file against their piece hash. This is performed in 2 steps.

Step 1: Resolve all 1-file pieces.
<pre>
Piece: -----XXXX-----
File : -----XXXX-----
OR
Piece: -----XXXX-----
File : ---XXXXXXXX---
</pre>
These pieces give us the most information, and are always the easiest to resolve. Since there is only one metafileFile in the piece, brute forcing this piece takes O(n) time, where n is the number of potential matches for the metafileFile in this piece. In addition, assuming you're using a mechanical hard disk, this should also decrease access time slightly

When operating in quick mode, resolving these pieces could potentially make a file skippable. For example:
<pre>
Pieces: ----WWWWXXXXYYYYZZZZ----
Files : AAAAAABBBBBBBBBBBBCCCCCC
</pre>
Since pieces X and Y contain only one file, these are solved first. If we solve piece X first, and only one potential match is returned, then we can skip piece Y, since it won't tell us anything more about the file (unless you're running in robust mode).

They also have a high probability to make step 2 much easier. It should be obvious why this is in Step 2.

Step 2: Resolve the remaining pieces in least-number-of-combinations-first order.
This step is essentially a password cracker. You can also think of it as solving a TSP -- The only way to get a correct answer is to try *EVERY* combination. 

Unlike the TSP, this problem has no heuristic to tell you if you're getting close, or if a branch isn't promising. Thankfully, though, SHA1 allows us to incrementally update it so we can keep information from higher in the search tree to avoid *some* duplicate processing.

The actual process looks something like this:</br>
For each metafileFile in the piece, we cache the portions of all of the potential matching filesystem files that could appear in the piece. If we're going to read the same data over and over, there's no point in dealing with disk latency. This has the potential to run your computer out of memory, but this should never happen in practice, and if it did, there is no question that the metafile would be solvable in your lifetime.

Once the potential matches are cached, we can begin searching the tree using a simple DFS. Each node in the tree points to a filesystem file. These nodes are generated based on their depth, where increasing depth by 1 means moving to the next metafileFile in the piece.

EX (the tree are nodes of file contents):
<pre>
Metafile File: 11111111111111111222222222223333333333333333
Tree         :
              |AAAAAAAAAAAAAAAAA
              |                |CCCCCCCCCCC
              |                `DDDDDDDDDDD
              |                           |EEEEEEEEEEEEEEEE
              |                           |FFFFFFFFFFFFFFFF
              |                           `GGGGGGGGGGGGGGGG
              `BBBBBBBBBBBBBBBBB
                               |CCCCCCCCCCC
                               `DDDDDDDDDDD
                                          |EEEEEEEEEEEEEEEE
                                          |FFFFFFFFFFFFFFFF
                                          `GGGGGGGGGGGGGGGG

</pre>

In short, we must search the cross-product of all possible files. The worst-case number of combinations can be calculated using n^m, where n is the number of potential files in a file, and m is the number of files in the piece. We obviously can't effect m, but we can do a few things to reduce n. I haven't seen any similar tool use these optimizations before, and this is why I built this tool in the first place.

For example:
<pre>
Pieces: ---Piece 1---+++Piece 2+++
Files : AAAABBBBBBBCCCCDDDDDDDEEEE
Files A, B, and C have 10 potential matches, and files D and E have 2 potential matches

Nr combinations:
Piece 1: 10 * 10 * 10 = 1000
Piece 2: 2 * 2 * 10 = 40

The naive solution -- solve the pieces in order:
Solve piece 1: Try 1000 combinations
New cost of piece 2: 2 * 2 * 1 = 4
Solve piece 2: Try 4 combinations
Total cost = 1004
Combinations saved = 36

My solution -- solve the pieces in least-complex first order:
Solve piece 2: Try 40 combinations
New cost of piece 1: 10 * 10 * 1 = 100
Solve piece 1: Try 100 combinations
Total cost = 140
Combinations saved = 900
</pre>

At each recursive call (new node), we update the SHA1 sum with the contents of one of the filesystem files at this node. When there are no more files to add to the tree, we compare the SHA1 sums.


Possible improvements (TODO)
============================
- Multiprocessing in batch mode
- Run the DFS search with SHA1 on a GPU if available (I'd probably need to write this as an extension in C++)
- Look into Cython to compile as C
- Automated unit testing
- Better combination calculation function (I worked out the formula, but haven't implemented it yet.)
- Partial structure creation when we can't match a file
- Learn how to make one of those Python auto-dep installers

I fix things as I need to. At some point, I might have enough files where Python becomes too slow. Until then though, spideTor will remain a strictly Python-only project.
