import sys
sys.path.append(".")
import util
import urllib
import os
import os.path
import time
import shutil
import re
import subprocess
import argparse


outputdir = "output"
verbose = 1

cache = {}

prev_pool = util.ThreadPool(2)
prev_running = False
main_pool = util.ThreadPool(1)

downloading = {}

lastmpd = None
lastcount = 0

lastcount_thresh = 30


def _add_ns(path):
    return "{urn:mpeg:dash:schema:mpd:2011}" + path


def download_mpd(url):
    global lastmpd
    global lastcount
    try:
        data = util.download(url)
        if lastmpd == data:
            lastcount = lastcount + 1
            if verbose >= 1:
                print("Same (%i/%i)" % (lastcount, lastcount_thresh))
            if lastcount > lastcount_thresh:
                return None
        lastmpd = data
        lastcount = 0
        tree = util.etree.fromstring(data)
        return tree
    except Exception as e:
        print(e)
        return None


def choose_representation(representations):
    max_bandwidth = 0
    curr = None
    for representation in representations:
        bandwidth = int(representation.attrib.get("bandwidth"))
        if bandwidth > max_bandwidth:
            max_bandwidth = bandwidth
            curr = representation
    return curr


def parse_link(url, link, segment=None, time=""):
    if segment is not None:
        time = segment.attrib.get("t")
    return urllib.parse.urljoin(url, link.replace("$Time$", time))


def get_representation_links(url, representation):
    template = representation.find(_add_ns("SegmentTemplate"))
    timeline = template.find(_add_ns("SegmentTimeline"))

    links = []
    links.append(parse_link(url, template.attrib.get("initialization")))

    for s in timeline.findall(_add_ns("S")):
        links.append(parse_link(url, template.attrib.get("media"), segment=s))

    return links


def download_prev_representation_real(url, vrepresentation, arepresentation, until_prev):
    global prev_running
    prev_running = True
    vtemplate = vrepresentation.find(_add_ns("SegmentTemplate"))
    atemplate = arepresentation.find(_add_ns("SegmentTemplate"))
    timeline = vtemplate.find(_add_ns("SegmentTimeline"))

    s = timeline.find(_add_ns("S"))
    time = int(s.attrib.get("t"))
    d = int(s.attrib.get("d"))

    i = time
    errors = 0
    while i > 0:
        i = i - d
        if i < 0:
            prev_running = False
            return
        retcode = download_link(parse_link(url, vtemplate.attrib.get("media"), time=str(i)))
        if retcode != 200:
            if retcode != 304 or until_prev:
                if retcode == 410:
                    prev_running = False
                    return
                errors = errors + 1
                if errors > 10:
                    prev_running = False
                    return
                continue
        download_link(parse_link(url, atemplate.attrib.get("media"), time=str(i)))
    prev_running = False


def download_prev_representation(url, vrepresentation, arepresentation, until_prev):
    if prev_running and False:
        return
    prev_pool.add_task(download_prev_representation_real, url, vrepresentation, arepresentation, until_prev)


def download_link(url):
    if url in cache:
        return cache[url]

    basename = os.path.basename(url)
    output = os.path.join(outputdir, basename)
    if not os.path.exists(output):
        if url in downloading and downloading[url]:
            return 200

        downloading[url] = True
        if verbose >= 1:
            print("Downloading " + url)
        retval = util.download_file(url, output)
        if retval == 200:
            cache[url] = 304
        else:
            cache[url] = retval
        del downloading[url]
        return retval
    else:
        if verbose >= 2:
            print("Skipping " + url)
        return 304
    return 200


def get_mpd(url, download_prev=False):
    mpd = download_mpd(url)
    if mpd is None:
        return None

    vrepresentations = []
    arepresentations = []

    adaptationsets = mpd.find(_add_ns("Period")).findall(_add_ns("AdaptationSet"))
    for adaptation in adaptationsets:
        for representation in adaptation.findall(_add_ns("Representation")):
            mime = str(representation.attrib.get("mimeType")).split("/")[0]
            if mime == "video":
                vrepresentations.append(representation)
            elif mime == "audio":
                arepresentations.append(representation)
            else:
                print("Invalid mime type: " + str(representation.attrib.get("mimeType")))

    vrepresentation = choose_representation(vrepresentations)
    arepresentation = choose_representation(arepresentations)

    vlinks = get_representation_links(url, vrepresentation)
    alinks = get_representation_links(url, arepresentation)

    links = vlinks + alinks
    print(len(links))

    for link in links:
        main_pool.add_task(download_link, link)

    print("Done download in main thread")

    # maybe thread this?
    if download_prev or True:
        download_prev_representation(url, vrepresentation, arepresentation, not download_prev)
        print("Done prev in main thread")

    return {
        "running": mpd.attrib.get("type") == "dynamic",
        "wait": 1
    }


# https://stackoverflow.com/a/27077437
def stitch(files, output):
    with open(output, 'wb') as wfd:
        for f in files:
            with open(f, 'rb') as fd:
                shutil.copyfileobj(fd, wfd, 1024*1024*10)


def stitch_files(url, output):
    mediaid = re.sub(r".*/([0-9]*)[^/]*$", "\\1", url)

    video = []
    audio = []

    for f in os.listdir(outputdir):
        arr = None
        if f.startswith(mediaid + "-"):
            if f.endswith(".m4a"):
                arr = audio
            elif f.endswith(".m4v"):
                arr = video
            if arr is not None:
                if "-init." not in f:
                    arr.append(os.path.join(outputdir, f))

    video = sorted(video)
    audio = sorted(audio)

    initfile = os.path.join(outputdir, mediaid + "-init")
    if (not os.path.exists(initfile + ".m4v")
        or not os.path.exists(initfile + ".m4a")):
        print("No init file")
        return

    video.insert(0, initfile + ".m4v")
    audio.insert(0, initfile + ".m4a")

    outfile = os.path.join(outputdir, mediaid)
    videoout = outfile + ".m4v"
    audioout = outfile + ".m4a"

    if len(video) != len(audio):
        print("Different video/audio length, currenty unhandled")
        return

    stitch(video, videoout)
    stitch(audio, audioout)

    if output == "auto":
        output = outfile + ".mp4"

    return subprocess.check_call(["ffmpeg", "-i", videoout, "-i", audioout, "-c", "copy", output]) == 0


def main():
    os.makedirs(outputdir, exist_ok=True)

    parser = argparse.ArgumentParser(description='Download Instagram Live Streams')
    parser.add_argument('url', help='Livestream MPD Url')
    parser.add_argument('--stitch', action='store_true', help='Stitch already downloaded files')
    parser.add_argument('--output', default='auto', help='Output file')
    args = parser.parse_args()

    if args.stitch:
        stitch_files(args.url, args.output)
        return

    running = True
    first = True
    while running:
        print("loop")
        out = get_mpd(args.url, first)
        if not out:
            break
        running = out["running"]
        first = False
        time.sleep(out["wait"])

    prev_pool.wait_completion()
    main_pool.wait_completion()

    stitch_files(args.url, args.output)


if __name__ == "__main__":
    main()
