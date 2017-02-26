import os
import os.path
import sys
import re
import pprint
import hashlib


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def md5(fname):
    return os.path.getsize(fname)
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

if len(sys.argv) < 2:
    print("need directory")
    sys.exit(1)

files = os.listdir(sys.argv[1])

dupes = {}

sys.stderr.write("Getting list... ")
i = 1
total_files = 0
for file in files:
    sys.stderr.write("\rGetting list... " + str(i) + "/" + str(len(files)) + "       ")
    i += 1
    path = os.path.join(sys.argv[1], file)
    if not os.path.isfile(path):
       continue
    total_files += 1
    key = re.match("^\([^)]*\) *(.*)$", file).group(1)
    if not key in dupes:
        dupes[key] = [path]
    else:
        dupes[key].append(path)

sys.stderr.write("\rGetting list... done           \n")

defects = {}
remove = []

sys.stderr.write("Processing...")
i = 1
remsize = 0
for dupe in dupes:
    sys.stderr.write("\rProcessing... " + str(i) + "/" + str(len(dupes)) + "      ")
    i += 1
    if len(dupes[dupe]) == 1:
       continue

    max = 0
    maxpath = ""

    for file in dupes[dupe]:
        stat = os.stat(file)
        if stat.st_mtime > max:
           max = stat.st_mtime
           maxpath = file

    mmd5 = md5(maxpath)
    defected = mmd5 == 0
    for file in dupes[dupe]:
        if file == maxpath:
           continue
        fmd5 = md5(file)
        if fmd5 != mmd5:
           defected = True
           if not maxpath in defects:
              defects[maxpath] = [file]
           else:
              defects[maxpath].append(file)
           #print("!!! " + file)
           #print("--- " + maxpath)
    if not defected:
        for file in dupes[dupe]:
            if file == maxpath:
                continue
            remsize += md5(file)
            remove.append(file)
    #print("+++")
    #print(maxpath)
    #print("=========")

sys.stderr.write("\rProcessing... done       \n")
sys.stderr.write(str(len(remove)) + " files to remove, " + str(total_files) + " total, -" + sizeof_fmt(remsize) + "\n")

sys.stderr.write("Removing...")
i = 1
for file in remove:
    sys.stderr.write("\rRemoving... " + str(i) + "/" + str(len(remove)) + "      ")
    i += 1
    os.remove(file)
sys.stderr.write("\rRemoving... done       \n")