import os
import sys
import re

if len(sys.argv) < 2:
    print(sys.argv[0] + " dir")
    exit()


def replacestr(old):
    old = old.replace(':', '')
    old = re.sub(' $', '', old)
    old = re.sub(r'\.$', '', old)
    old = old.replace('<', '(')
    old = old.replace('>', ')')
    old = old.replace('"', "'")
    old = old.replace('?', '？')
    old = old.replace('*', '·')
    old = old.replace('|', '❘')
    old = old.replace('\\', '_')
    return old

curr = 0
modded = 0
total = 0

def dodir(thedir):
    global curr, modded, total
    listed = list(os.listdir(thedir))
    total += len(listed)
    for x in listed:
        path = os.path.join(thedir, x)
        newpath = replacestr(path)
        #print(path)
        #print(replacestr(path))

        if newpath != path:
            os.rename(path, newpath)
            modded += 1
            pass

        curr += 1
        sys.stderr.write("\r(%i/%i/%i)" % (curr, modded, total))

        if os.path.isdir(newpath):
            dodir(newpath)

dodir(sys.argv[1])
sys.stderr.write("\n")
sys.stderr.flush()
