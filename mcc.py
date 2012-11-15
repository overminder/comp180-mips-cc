#!/usr/bin/env python
"""The main entrance of the mips compiler"""
import sys
import tomips
import irgen

def main():
    if len(sys.argv) <= 2:
        print 'usage: %s (-i -c) [filename]' % (sys.argv[0])
        return

    if sys.argv[1] == '-c':
        del sys.argv[1]
        tomips.main()

    elif sys.argv[1] == '-i':
        del sys.argv[1]
        irgen.main()

    else:
        print 'usage: %s (-i -c) [filename]' % (sys.argv[0])
        return

if __name__ == '__main__':
    main()

