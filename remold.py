import os
import sys
import datetime
import time


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


if "/dlscripts" in sys.argv[1]:
    timethresh = 30 * (60 * 60 * 24)
else:
    timethresh = 1.5 * (60 * 60 * 24)

files = os.listdir(sys.argv[1])
remfiles = []
now = datetime.datetime.now().timestamp()
remsize = 0
totalsize = 0
earliest = None
latest = None
for file in files:
    file = os.path.join(sys.argv[1], file)
    s = os.stat(file)
    if earliest is None or s.st_ctime < earliest:
        earliest = s.st_ctime

    filesize = os.path.getsize(file)
    totalsize += filesize

    if (((now - s.st_ctime) >= timethresh) and
        ((now - s.st_mtime) >= timethresh)):
        remfiles.append(file)
        remsize += filesize
        if latest is None or s.st_ctime > latest:
            latest = s.st_ctime

sys.stderr.write(str(len(remfiles)) + " files to remove, " + str(len(files)) + " total, -" + sizeof_fmt(remsize) + " (" + sizeof_fmt(totalsize) + " total)\n")
sys.stderr.write("Earliest: " + time.ctime(earliest) + "\nLatest: " + time.ctime(latest) + "\n")
hours = (latest - earliest) / 60 / 60
sys.stderr.write('%.2f' % (hours) + " hours (~" + sizeof_fmt(remsize / (hours / 24)) + "/day)\n")

if len(remfiles) == 0:
    exit()

sys.stderr.write("Remove?\n")

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
        time.sleep(.1)
    if i % 1000 == 0:
        time.sleep(.3)
    if i % 10000 == 0:
        time.sleep(5)
    if i % 100000 == 0:
        time.sleep(10)
sys.stderr.write("\rRemoving... done       \n")
