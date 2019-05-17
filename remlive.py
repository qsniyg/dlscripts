import os
import os.path
import re
import sys
import datetime
import json
import time
import pprint


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


livethresh = 11 * (60 * 60 * 24)
fastthresh = 2 * (60 * 60 * 24)
otherthresh = 28 * (60 * 60 * 24)
storythresh = 38 * (60 * 60 * 24)

dirs = os.listdir(sys.argv[1])

try:
    with open(os.path.join(os.path.dirname(__file__), "remlive.json"), "rb") as f:
        settings = json.loads(f.read())
except Exception as e:
    print(e)
    exit()

if False:
    settings = {
        "protected": [],
        "protected_nolive": [],
        "fast_nolive": [],
        "noigtv": []
    }

remfiles = []
now = datetime.datetime.now().timestamp()
remsize = 0
totalsize = 0

def check_live(filepath):
    if not re.search(r"/\([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+\) \[LIVE(?: REPLAY)?\]\.mp4", filepath):
        return False
    return True

def check_live_replay(filepath):
    if not re.search(r"/\([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+\) \[LIVE REPLAY\]\.mp4", filepath):
        return False
    return True

def check_story(filepath):
    if not re.search(r"/\([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+\) \[(?:STORY|DP)\]", filepath):
        return False
    return True

def check_dp(filepath):
    if not re.search(r"/\([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+\) \[(?:DP)\]", filepath):
        return False
    return True

def check_igtv(filepath):
    if not re.search(r"/\([0-9]+-[0-9]+-[0-9]+T[0-9]+:[0-9]+:[0-9]+\) \[(?:IGTV)\]", filepath):
        return False
    return True

def check_dld(file):
    if re.search(r"^[(]2014-", file):
        return True
    return False

def can_remove(filepath, nolive, noigtv=False):
    if check_igtv(filepath) and not noigtv:
        return False

    if nolive:
        if check_live_replay(filepath) or check_live(filepath):
            return True
        if noigtv and check_igtv(filepath):
            return True
        return False

    #if (check_live(filepath) and not check_live_replay(filepath)) or check_story(filepath):
    #if check_live_replay(filepath) or check_story(filepath):
    if check_story(filepath) and False:
        return False
    if check_dp(filepath):
        return False
    return True

def inthresh(s, thresh):
    return (
        ((now - s.st_ctime) >= thresh)
        and ((now - s.st_mtime) >= thresh)
    )

def dofile(filepath, nolive, is_small=False, fast=False, noigtv=False):
    global remfiles, now, remsize, totalsize

    totalsize += os.path.getsize(filepath)
    if not can_remove(filepath, nolive, noigtv):
        return

    s = os.stat(filepath)
    #if (((now - s.st_ctime) >= timethresh)
    #    and ((now - s.st_mtime) >= timethresh)
    #    #and ((now - s.st_atime) >= timethresh)):
    #    ):"""
    remove = False
    if check_live(filepath):
        if inthresh(s, livethresh):
            #print(filepath)
            #print((now -s.st_ctime) / 60 / 60 / 24)
            remove = True
        else:
            if fast and inthresh(s, fastthresh):
                remove = True
            else:
                pass
    elif not is_small:
        if check_story(filepath):
            if inthresh(s, storythresh):
                remove = True
        elif inthresh(s, otherthresh):
            remove = True

    if remove:
        #if nolive and check_live(filepath):
        #    print(filepath)
        remfiles.append(filepath)
        #print(filepath)
        remsize += os.path.getsize(filepath)


dld = 0
smalldirs = []
smallthresh = 40
def dofiles(dirpath, nolive, fast=False, noigtv=False):
    global smalldirs
    files = os.listdir(dirpath)
    is_small = False

    if False:
        for file in files:
            if check_dld(file):
                global dld
                #print(dirpath)
                dld += 1
                return

    if len(files) < smallthresh:
        #print(dirpath)
        is_small = True

        if False:
            size = 0
            for file in files:
                size += os.path.getsize(os.path.join(dirpath, file))
            smalldirs.append([dirpath, size])
        if False:
            dld += 1
            return

    totalfiles = 0
    for file in files:
        if not can_remove(os.path.join(dirpath, file), nolive, noigtv) and False:  # why?
            continue
        totalfiles += 1

    if totalfiles < smallthresh:
        #print(dirpath)
        is_small = True

        if False:
            dld += 1
            return

    for file in files:
        filepath = os.path.join(dirpath, file)
        dofile(filepath, nolive, is_small, fast, noigtv)

i = 1
for dir_ in dirs:
    dirpath = os.path.join(sys.argv[1], dir_)
    if os.path.isdir(dirpath):
        nolive = False
        fast = False
        noigtv = False
        if dir_.lower() in settings["protected"]:
            i += 1
            #nolive = True
            continue
        if dir_.lower() in settings["protected_nolive"]:
            nolive = True
        if dir_.lower() in settings["fast_nolive"]:
            fast = True
        if dir_.lower() in settings["noigtv"]:
            noigtv = True
        dofiles(dirpath, nolive, fast, noigtv)
    else:
        print("ERROR")
        dofile(dirpath, False)
    sys.stderr.write("\r" + str(i) + "/" + str(len(dirs)) + "            ")
    i += 1

    if i % 10 == 0 and False:
        time.sleep(.03)

sys.stderr.write("\n")


sys.stderr.write(str(len(remfiles)) + " files to remove, -" + sizeof_fmt(remsize) + " (" + sizeof_fmt(totalsize) + " total-protected)\n")
sys.stderr.write(str(dld) + "\n")

#print(len(smalldirs))
#for i in smalldirs:
#    print(str(int(i[1] / 1024 / 1024)) + " " + i[0])
if len(remfiles) == 0:
    exit()

sys.stderr.write("Remove?\n")

#exit()
# read line
for line in sys.stdin:
    break


sys.stderr.write("Removing...")
i = 1
for file in remfiles:
    sys.stderr.write("\rRemoving... " + str(i) + "/" + str(len(remfiles)) + "      ")
    i += 1
    os.remove(file)

    if i % 100 == 0:
        time.sleep(.5)
    #print(file)
sys.stderr.write("\rRemoving... done       \n")
