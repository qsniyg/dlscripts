import os
import sys
import datetime


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


timethresh = 3 * (60 * 60 * 24)

files = os.listdir(sys.argv[1])
remfiles = []
now = datetime.datetime.now().timestamp()
remsize = 0
for file in files:
    file = os.path.join(sys.argv[1], file)
    s = os.stat(file)
    if (((now - s.st_ctime) >= timethresh) and
        ((now - s.st_mtime) >= timethresh) and
        ((now - s.st_atime) >= timethresh)):
        remfiles.append(file)
        remsize += os.path.getsize(file)

sys.stderr.write(str(len(remfiles)) + " files to remove, " + str(len(files)) + " total, -" + sizeof_fmt(remsize) + "\n")

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
sys.stderr.write("\rRemoving... done       \n")
