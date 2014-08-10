spideTor
========

Reseed torrent metafiles with renamed or moved files

spideTor is a "weekend hack" project born to solve a personal need. As far as I'm aware, it is the fastest and most robust tool of it's kind, although admittedly, competition is scarce...

In short, spideTor takes .torrent metafiles and a search directory containing the files downloaded as part of the provided .torrent as input. Given some time, spideTor will eventually create a directory structure of symlinks emulating that of the .torrent.  If you're from windows land, you can think of symlinks like shortcuts. They take no space, and simply point to another file.

Due to the nature of bruteforcing, spideTor will perform best (fastest) with torrents that contain files that are larger than the torrent piece size. I explain this in further detail later.


Usage
=====

You can get help using
python spideTor.py -h

In addition, I've created a short video showing how to use the tool here: (TODO)

NOTE: On Windows, you must run spideTor with administrator privlidges or else it won't be allowed to create symlinks for you. 

Features
========

Supported platforms: Windows Vista and above, and Linux (although Linux remains largely untested)

* Unicode support
* Robust mode (verify all pieces) and Quick mode (verify one full piece of a file, at most)
* Network filesystem support under Windows and Linux
* Supports UNC paths (paths over 260 characters on Windows)
* Batch processing mode -- TODO: Add multiprocessor support to batch mode!!

Challenges
==========

UNC Paths
---------
Windows has a long standing 260 character limit on paths. With the standard drive letter snippet (i.e. C:\\) taking up 3 characters and the null byte taking up 1 charater, you end up with 256 usable characters for absolute paths. For further information about this problem, you can read Microsoft's documentation here http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath

This limitation appeared while I was testing spideTor on my own collection of files stored on my Linux-based server. Although the python "walk" function could access the files, os.path.exists would always return null for those long paths and I could not read/write the files. 

As a workaround, I've wrapped most file accesses in a utility function that prepends "\\\\?\\UNC\\" to the paths to tell Windows to not preprocess the path and allow access to paths over 260 characters long. This, of course, only effects paths when running on Windows.

Symlinks
--------
Python 2 does not have a built in symlink function for Windows. As a result, I have to patch the symlink function at runtime if running on Windows to call the kernal32 DLL. In addition, symlinks can only be created on windows if you have Administrator privlidges, so I had to add a function to check for the necessary symlink privlidges. 

Computational complexity
------------------------
The nature of this project is a challenge in itself. In essence, we're bruteforcing a password. Thankfully, there are many tricks that I came up with to make this much easier. However, there are still rare cases where a metafile could take a few days to process as opposed to a few seconds. I go into detail about my approach to simplifying this problem in the "implementation details" section


Implementation details
======================
TODO

Possible improvements (TODO)
============================
- Multiprocessing in batch mode
- Run the DFS search with SHA1 on a GPU if available (I'd probably need to write this as an extension in C++)
- Automated unit testing
- Better combination calculation function (I think this would be better modeled as a graph coloring problem)

I fix things as I need to. At some point, I might have enough files where Python becomes too slow. Until then though, spideTor will remain a strictly Python-only project.
