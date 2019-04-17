import sys
sys.path.append(".")
import util
import urllib
import urllib.error
import os
import os.path
import time
import shutil
import re
import subprocess
import argparse
import natsort
import pprint
import traceback
import datetime


if True:
    try:
        from lxml import etree
    except ImportError:
        try:
            # Python 2.5
            import xml.etree.cElementTree as etree
        except ImportError:
            try:
                # Python 2.5
                import xml.etree.ElementTree as etree
            except ImportError:
                try:
                    # normal cElementTree install
                    import cElementTree as etree
                except ImportError:
                    try:
                        # normal ElementTree install
                        import elementtree.ElementTree as etree
                    except ImportError:
                        pass


util.enable_logging()
defaultoutputdir = '~/.cache/iglivedl/'  # "output"
outputdir = os.path.expanduser(defaultoutputdir)
verbose = 1

cache = {}

prev_pool = util.ThreadPool(2)
prev_running = False
next_pool = util.ThreadPool(2)
next_running = False
main_pool = util.ThreadPool(1)

downloading = {}

lastmpd = None
lastcount = 0
lastdownload = 0
is_gone = False

lastcount_thresh = 30

ns_schema = "{urn:mpeg:dash:schema:mpd:2011}"


def _add_ns(path):
    return ns_schema + path


def download_mpd(url):
    global lastmpd
    global lastcount
    try:
        data = util.download(url, timeout=10)
        # This removes timestamps, which is more likely to be identical
        # However, this could eliminate scenarios where the person is temporarily offline
        #simpledata = re.sub(r"<MPD.*?>", "", str(x))
        if lastmpd == data:
            lastcount = lastcount + 1
            if (verbose >= 1 and lastcount > 2) or verbose >= 2:
                print("Same (%i/%i)" % (lastcount, lastcount_thresh))
            if lastcount > lastcount_thresh:
                return None
        lastmpd = data
        lastcount = 0
        outfile = open(os.path.join(outputdir, re.sub(r".*/([^/?]*)[^/]*?$", "\\1", url)), "wb")
        outfile.write(data)
        outfile.close()
        tree = etree.fromstring(data)
        return tree
    except urllib.error.HTTPError as e:
        print("Error downloading mpd (HTTPError):")
        print(e)

        if e.code == 410:
            global is_gone
            is_gone = True
        return None
    except Exception as e:
        print("Error downloading mpd:")
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
    if curr is None:
        try:
            max_total = 0
            for representation in representations:
                if representation.attrib.get("width") is not None:
                    width = int(representation.attrib.get("width"))
                    height = int(representation.attrib.get("height"))
                    framerate = float(representation.attrib.get("frameRate"))

                    total = width * height * framerate
                else:
                    samplerate = int(representation.attrib.get("audioSamplingRate"))
                    total = samplerate

                if total > max_total:
                    max_total = total
                    curr = representation
        except Exception as e:
            #print(e)
            traceback.print_exc()
    if curr is None:
        print("No curr!")
        pprint.pprint(representations)
    return curr


def parse_link(url, link, segment=None, time=""):
    if segment is not None:
        newtime = segment.attrib.get("t")
        if newtime:
            time = newtime
    return urllib.parse.urljoin(url, link.replace("$Time$", time))


def get_template(representation):
    return representation.find(_add_ns("SegmentTemplate"))


def get_link(url, template, representation, segment=None, time=""):
    baseurl = None
    try:
        baseurl = representation.find(_add_ns("BaseURL")).text
    except Exception:
        pass

    if not baseurl:# or True:
        return parse_link(url, template.attrib.get("media"), segment=segment, time=time)
    else:
        return parse_link(url, baseurl, segment=segment, time=time)


def get_representation_links(url, representation, template):
    #template = representation.find(_add_ns("SegmentTemplate"))
    newtemplate = get_template(representation)
    if newtemplate is not None:
        template = newtemplate

    timeline = template.find(_add_ns("SegmentTimeline"))

    links = []
    try:
        links.append(parse_link(url, template.attrib.get("initialization")))
    except Exception:
        print("Warning: no initialization")
        pass

    for s in timeline.findall(_add_ns("S")):
        links.append(get_link(url, template, representation, segment=s))
        continue
        try:
            links.append(get_link(url, template, representation, s))#parse_link(url, template.attrib.get("media"), segment=s))
        except Exception:
            links.append(parse_link(url, representation.find(_add_ns("BaseURL")).text, segment=s))

    return links


def download_prev_representation_real(url, vrepresentation, arepresentation, until_prev, template, prevnext=False):
    def set_runningstate(value):
        global prev_running
        prev_running = value
    if prevnext is True:
        def set_runningstate(value):
            global next_running
            next_running = value

    set_runningstate(True)
    #global prev_running
    #prev_running = True

    vtemplate = template
    atemplate = template

    newtemplate = get_template(vrepresentation)
    if newtemplate is not None:
        vtemplate = newtemplate

    newtemplate = get_template(arepresentation)
    if newtemplate is not None:
        atemplate = newtemplate

    #vtemplate = vrepresentation.find(_add_ns("SegmentTemplate"))
    #atemplate = arepresentation.find(_add_ns("SegmentTemplate"))
    timeline = vtemplate.find(_add_ns("SegmentTimeline"))

    s_es = timeline.findall(_add_ns("S"))
    if len(s_es) == 0:
        print("Warning: len(s_es) == 0")
        return

    s = None
    err_thresh = 10

    if not prevnext:
        s = s_es[0]
    else:
        s = s_es[-1]
        err_thresh = 1

    time = int(s.attrib.get("t"))
    d = int(s.attrib.get("d"))
    if d <= 0:
        print("Warning: d <= 0, skipping prev/next")
        return

    i = time
    errors = 0
    while i > 0:
        if not prevnext:
            i = i - d
        else:
            i = i + d
        if i < 0:
            #prev_running = False
            set_runningstate(False)
            return
        #retcode = download_link(parse_link(url, vtemplate.attrib.get("media"), time=str(i)))
        retcode = download_link(get_link(url, vtemplate, vrepresentation, time=str(i)))
        if retcode != 200:
            if retcode != 304 or until_prev:
                if retcode == 410:
                    #prev_running = False
                    set_runningstate(False)
                    return
                errors = errors + 1
                if errors > err_thresh:
                    #prev_running = False
                    set_runningstate(False)
                    return
                continue
            errors = 0
        #download_link(parse_link(url, atemplate.attrib.get("media"), time=str(i)))
        download_link(get_link(url, atemplate, arepresentation, time=str(i)))
    #prev_running = False
    set_runningstate(False)


def download_prev_representation(url, vrepresentation, arepresentation, until_prev, template):
    if prev_running and False:
        return
    prev_pool.add_task(download_prev_representation_real, url, vrepresentation, arepresentation, until_prev, template, False)


def download_next_representation(url, vrepresentation, arepresentation, until_prev, template):
    if next_running and False:
        return
    next_pool.add_task(download_prev_representation_real, url, vrepresentation, arepresentation, until_prev, template, True)


def remquery(url):
    return re.sub(r"[?#].*$", "", url)


def download_link(url, nocache=False):
    if url in cache and not nocache:
        return cache[url]

    now = str(datetime.datetime.now())
    basename = remquery(os.path.basename(url))
    output = os.path.join(outputdir, basename)
    if not os.path.exists(output):
        if url in downloading and downloading[url]:
            return 200

        downloading[url] = True

        global lastdownload
        lastdownload = time.monotonic()

        if verbose >= 1:
            print(now + " Downloading " + url)
        retval = util.download_file(url, output)
        if retval == 200:
            cache[url] = 304
        else:
            cache[url] = retval
        del downloading[url]
        return retval
    else:
        if verbose >= 3:
            print(now + " Skipping " + url)
        return 304
    return 200


def get_mpd(url, download_prev=False, nosave=False):
    mpd = download_mpd(url)
    if mpd is None:
        return None

    vrepresentations = []
    arepresentations = []

    global ns_schema
    ns_schema = '{' + str(mpd[0].nsmap[None]) + '}'

    period = mpd.find(_add_ns("Period"))
    roottemplate = get_template(period)

    adaptationsets = mpd.find(_add_ns("Period")).findall(_add_ns("AdaptationSet"))
    for adaptation in adaptationsets:
        adaptation_mime = str(adaptation.attrib.get("mimeType")).split("/")[0]
        for representation in adaptation.findall(_add_ns("Representation")):
            mime = str(representation.attrib.get("mimeType")).split("/")[0]
            if mime == "video":
                vrepresentations.append(representation)
            elif mime == "audio":
                arepresentations.append(representation)
            else:
                if adaptation_mime == "video":
                    vrepresentations.append(representation)
                elif adaptation_mime == "audio":
                    arepresentations.append(representation)
                else:
                    print("Invalid mime type: " + str(representation.attrib.get("mimeType")))

    vrepresentation = choose_representation(vrepresentations)
    arepresentation = choose_representation(arepresentations)

    vlinks = get_representation_links(url, vrepresentation, roottemplate)
    alinks = get_representation_links(url, arepresentation, roottemplate)

    links = vlinks + alinks

    if nosave:
        print(etree.tostring(vrepresentation))
        print(etree.tostring(arepresentation))
        pprint.pprint(vlinks)
        pprint.pprint(alinks)
        return

    for link in links:
        main_pool.add_task(download_link, link, True)

    #print("Done download in main thread")

    # maybe thread this?
    if download_prev or True:
        download_prev_representation(url, vrepresentation, arepresentation, not download_prev, roottemplate)
        download_next_representation(url, vrepresentation, arepresentation, not download_prev, roottemplate)
        #print("Done prev in main thread")

    if lastdownload > 0 and (time.monotonic() - lastdownload) > (60*30):
        print("lastdownload timeout: " + str(time.monotonic()) + " " + str(lastdownload) + " (" + str(time.monotonic() - lastdownload) + ")")
        return None

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


def remove_singles(array1, array2):
    newarray = []
    for item in array1:
        if item.endswith(".m4v"):
            item1 = re.sub(r"\.m4v$", ".m4a", item)
        else:
            item1 = re.sub(r"\.m4a$", ".m4v", item)

        if item1 not in array2:
            print("Warning: removing single item: " + item)
        else:
            newarray.append(item)
    return newarray


def stitch_files(url, output, cleanup=False):
    mediaid = re.sub(r".*/([0-9]*)[^/]*$", "\\1", url)
    if mediaid == url:
        print("Unable to find media ID in: %s" % url)
    stitch_files_real(mediaid, output, cleanup)


def stitch_files_real(mediaid, output, cleanup=False):
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

    if len(video) == 0 and len(audio) == 0:
        for f in os.listdir(outputdir):
            if f.startswith(mediaid + "_") and re.search(r"_[0-9]+[-.]", f):
                newmediaid = re.sub(r"(_[0-9]+)[-.].*", "\\1", f)
                print("Trying new media ID: %s" % newmediaid)
                return stitch_files_real(newmediaid, output, cleanup)
        print("No video or audio files")

    video_orig = sorted(video)
    audio_orig = sorted(audio)

    video = natsort.natsorted(remove_singles(video_orig, audio))
    audio = natsort.natsorted(remove_singles(audio_orig, video))

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

    print("Stitching %i video files" % len(video))
    stitch(video, videoout)
    print("Stitching %i audio files" % len(video))
    stitch(audio, audioout)

    if output == "auto":
        output = outfile + ".mkv"

    #retval = subprocess.check_call(["ffmpeg", "-i", videoout, "-i", audioout, "-c", "copy", "-y", output]) == 0
    retval = subprocess.check_call(["ffmpeg", "-ss", "0", "-seek_timestamp", "-2147483648.000000", "-i", videoout, "-ss", "0", "-seek_timestamp", "-2147483648.000000", "-i", audioout, "-c", "copy", "-y", output]) == 0
    #retval = subprocess.check_call(["mkvmerge", "-o", output, "-A", videoout, audioout]) == 0

    if cleanup and retval:
        print("Cleaning up")
        os.remove(videoout)
        os.remove(audioout)
        for f in video:
            os.remove(f)
        for f in audio:
            os.remove(f)

    if retval and "live_hook" in util.tokens and len(util.tokens["live_hook"]) > 0:
        hook = util.tokens["live_hook"]
        hook.append(output)
        subprocess.check_call(hook)


def download_stream(url, nosave=False):
    print("Downloading stream: " + str(url))

    running = True
    first = True
    errors = 0
    while running:
        if verbose >= 2:
            print("loop")
        try:
            out = get_mpd(url, first, nosave=nosave)
            if not out:
                now = str(datetime.datetime.now())
                print(now + " No mpd (probably done?): " + str(errors))
                errors = errors + 1
                if errors > 10:
                    break
                time.sleep(4)
                continue

            errors = 0
            running = out["running"]
            first = False
            waitamt = out["wait"]
            if waitamt > 10:
                print("Warning: wait amount > 10s: " + str(waitamt))
                waitamt = 10
            if waitamt < 0:
                print("Warning: wait amount < 0s: " + str(waitamt))
                continue
            time.sleep(out["wait"])
        except Exception as e:
            print("Error in main loop:")
            print(e)
            time.sleep(1)

    now = str(datetime.datetime.now())
    print(now + " Done, waiting for completion")
    prev_pool.wait_completion()
    next_pool.wait_completion()
    now = str(datetime.datetime.now())
    print(now + " Done prev pool, waiting for main pool")
    main_pool.wait_completion()
    now = str(datetime.datetime.now())
    print(now + " All done")


def run(url, stitch=True, cleanup=True, cachedir=defaultoutputdir, output="auto", nosave=False):
    global outputdir
    outputdir = os.path.expanduser(cachedir)
    os.makedirs(outputdir, exist_ok=True)
    print("Output: " + str(output))

    if stitch:
        stitch_files(url, output, cleanup=cleanup)
        return

    download_stream(url, nosave=nosave)

    stitch_files(url, output, cleanup=cleanup)


def main():
    parser = argparse.ArgumentParser(description='Download Instagram Live Streams')
    parser.add_argument('url', help='Livestream MPD Url')
    parser.add_argument('--stitch', action='store_true', help='Stitch already downloaded files')
    parser.add_argument('--no-cleanup', dest='cleanup', action='store_false', help="Don't clean up after downloading")
    parser.add_argument('--cache-dir', dest='cachedir', default=defaultoutputdir, help="Cache directory")
    parser.add_argument('--output', default='auto', help='Output file')
    parser.add_argument('--no-save', dest='nosave', action='store_true', help='Test run')
    args = parser.parse_args()

    run(args.url, stitch=args.stitch, cleanup=args.cleanup, cachedir=args.cachedir, output=args.output, nosave=args.nosave)


if __name__ == "__main__":
    main()
