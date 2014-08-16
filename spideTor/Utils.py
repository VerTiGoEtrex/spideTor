# coding: utf-8
'''
A collection of utility functions for spideTor

Created on Aug 2, 2014

@author: Noah
'''

import os
import re

def windowsPathLengthLimitWorkaround(path):
    '''
    Windows API causes trouble again...
    If we're running on windows and not rooted in a UNC path, 
    prepend "//?/" to allow paths > 260 chars, and insert slash after the colon
    '''
    if os.name == "nt" or os.name == "ce":
        #Try to find drive identifier
        if re.match(r'^[A-Z]:', path):
            #we're accessing a drive letter path and need UNC prefix
            path = "\\\\?\\" + path
        else:
            path = re.sub(r'^\\\\(?!\?\\UNC\\)', r'\\\\?\\UNC\\', path)
    return path