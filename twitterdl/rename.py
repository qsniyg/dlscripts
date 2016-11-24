import sys
import json
import glob
import subprocess
import urllib.request

with open(sys.argv[1], "r") as f:
    jsonold = json.loads(f.read())

with open(sys.argv[2], "r") as f:
    jsonnew = json.loads(f.read())

import datetime
import re
import os
import os.path

def getext(url):
    return re.match(r"[^?]*\.(?P<ext>[^?/]*)", url).group("ext")

def getsuffix(i, array):
    if len(array) > 1:
        return " (%i:%i)" % (i + 1, len(array))
    else:
        return ""

def download(url, output):
    urllib.request.urlretrieve(url, filename=output)

if __name__ == "__main__":
    home = os.path.expanduser("~")

    generator = jsonold["config"]["generator"]
    thedir = home + "/Pictures/social/" + generator + "/" + jsonold["author"] + "/"

    for entry_i in range(len(jsonold["entries"])):
        entry_old = jsonold["entries"][entry_i]
        entry_new = jsonnew["entries"][entry_i]

        if not entry_old["caption"] or len(entry_old["caption"]) == 0:
            oldcaption = ""
        else:
            oldcaption = " " + entry_old["caption"].replace("\n", " ").replace("/", " (slash) ")[:50]

        if not entry_new["caption"] or len(entry_new["caption"]) == 0:
            newcaption = ""
        else:
            newcaption = " " + entry_new["caption"].replace("\n", " ").replace("/", " (slash) ")[:50]

        olddate = datetime.datetime.fromtimestamp(entry_old["date"]).isoformat()
        newdate = datetime.datetime.fromtimestamp(entry_new["date"]).isoformat()

        if not entry_old["images"]:
            entry_old["images"] = []

        for i, image in enumerate(entry_old["images"]):
            ext = getext(image)

            suffix = getsuffix(i, entry_old["images"])

            oldoutput = "(%s)%s%s.%s" % (olddate, oldcaption, suffix, ext)
            fulloldout = thedir + oldoutput

            newoutput = "(%s)%s%s.%s" % (newdate, newcaption, suffix, ext)
            fullnewout = thedir + newoutput

            if os.path.exists(fullnewout):
                continue

            if not os.path.exists(fulloldout):
                print(fulloldout + "doesn't exist!")

            os.rename(fulloldout, fullnewout)
            print("Renamed " + oldoutput + " to " + newoutput)

        if not entry_old["videos"]:
            entry_old["videos"] = []

        for i, video in enumerate(entry_old["videos"]):
            #ext = getext(video["video"])

            suffix = getsuffix(i, entry_old["videos"])

            url = video["video"]
            mymatch = re.match(r".*twitter.com/i/videos/(?P<id>[0-9]*)", url)
            if mymatch:
                url = "http://twitter.com/i/videos/tweet/%s" % mymatch.group("id")

            oldoutput = "(%s)%s%s" % (olddate, oldcaption, suffix)
            fulloldout = thedir + oldoutput

            newoutput = "(%s)%s%s" % (newdate, newcaption, suffix)
            fullnewout = thedir + newoutput

            if len(glob.glob(fullnewout + ".mp4")) > 0:
                continue

            if len(glob.glob(fulloldout + ".mp4")) <= 0:
                print("Old path doesn't exist!!")

            os.rename(fulloldout + ".mp4", fullnewout + ".mp4")
            continue

            if jsonold["config"]["generator"] == "instagram":
                fullout = fullout + ".mp4"

                if os.path.exists(fullout):
                    continue

                download(url, fullout)
            else:
                fullout = fullout + ".%(ext)s"

                if os.path.exists(fullout):
                    continue

                p = subprocess.Popen(["youtube-dl", url, "-o", fullout])
                p.wait()

            print("Downloaded video " + output)
