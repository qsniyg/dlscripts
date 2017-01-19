import sys
import json
import urllib.parse
import urllib.request
import shutil
import datetime
import re
import subprocess
import os
import os.path
import glob
import signal
import threading
import queue
import pprint
import http.client
import PIL.Image
import magic
sys.path.append(".")
import util

windows_path = False
if "windows" in util.tokens and util.tokens["windows"] == 1:
    windows_path = True

thresh_processes = 3
thresh_sleep_times = 20

thresh_resume = 8
thresh_same_resume = 3
timeout_s = 30

do_async = False
lockfile = None
no_lockfile = False

has_errors = False
error_files = []

running = True
def signal_handler(signal, frame):
    global running
    print("Exiting...")
    running = False
    return


class Worker(threading.Thread):
    """Thread executing tasks from a given tasks queue"""
    def __init__(self, tasks):
        threading.Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while running:
            func, args, kargs = self.tasks.get()
            try:
                func(*args, **kargs)
            except Exception as e:
                print(e)
            finally:
                self.tasks.task_done()

class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, num_threads):
        self.tasks = queue.Queue(num_threads)
        for _ in range(num_threads): Worker(self.tasks)

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()


def getext(url):
    match = re.match(r"[^?]*\.(?P<ext>[^?/:]*)(:[^?/]*)?$", url)

    if not match:
        return None

    return match.group("ext")

def getsuffix(i, array):
    if len(array) > 1:
        return " (%i:%i)" % (i + 1, len(array))
    else:
        return ""

def quote_url(link):
    link = urllib.parse.unquote(link).strip()
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(link)
    path = urllib.parse.quote(path)
    link = urllib.parse.urlunsplit((scheme, netloc, path, query, fragment)).replace("%3A", ":")
    return link

def getrequest(url, *args, **kargs):
    request = urllib.request.Request(quote_url(url))
    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    request.add_header('Pragma', 'no-cache')
    request.add_header('Cache-Control', 'max-age=0')
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    if "end_range" in kargs and kargs["end_range"] > 0:
        request.add_header('Range', 'bytes=%s-%s' % (kargs["start_range"], kargs["end_range"]))
    return request


content_type_table = {
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "image/x-icon": "ico",
    "video/mpeg": "mpg",
    "video/x-flv": "flv",
    "video/x-ms-asf": "asf",
    "video/x-ms-wmv": "wmv",
    "video/x-msvideo": "avi"
}


def download_real(url, output, options):
    if not running:
        return

    if not options:
        options = {
            "addext": False,
            "timeout": timeout_s
        }

    if "addext" not in options:
        options["addext"] = False

    if "timeout" not in options:
        options["timeout"] = timeout_s

    addext = options["addext"]
    our_timeout = options["timeout"]

    retval = output

    master_times = 1
    while running:
        if master_times >= 5:
            print("Tried 5 times, giving up")
            break
        elif master_times > 1:
            print("Trying again (" + str(master_times) + "/5)")
        master_times += 1

        finished = False

        try:
            if not addext:
                with open(output, 'wb') as out_file:
                    content_length = -1
                    old_length = -1
                    times = 0
                    same_length = 0
                    strerr = ""
                    while running:
                        #if same_length > 0:
                        #    print("Same length (" + str(same_length) + "/3)")
                        if times > 1:
                            print("Resuming (" + str(times) + "/" + str(thresh_resume) + ")" + strerr)
                        if same_length >= thresh_same_resume:
                            print("Same length " + str(thresh_same_resume) + " times, giving up")
                            break
                        if times >= thresh_resume:
                            print("Resumed " + str(thresh_resume) + " times, giving up")
                            break

                        times += 1

                        request = getrequest(url, start_range=out_file.tell(), end_range=content_length)
                        with urllib.request.urlopen(request, timeout=our_timeout) as response:
                            for header in response.headers._headers:
                                if header[0].lower() == "content-length":
                                    content_length = int(header[1])

                            try:
                                read_file = response.read()
                            except http.client.IncompleteRead as e:
                                read_file = e.partial

                            out_file.write(read_file)
                            out_file.flush()

                            if out_file.tell() >= content_length:
                                finished = True
                                break
                            elif out_file.tell() == old_length:
                                same_length += 1
                                strerr = " (same length " + str(same_length) + "/" + str(thresh_same_resume) + ")"
                            else:
                                strerr = ""
                                same_length = 0

                            old_length = out_file.tell()
            else:
                with urllib.request.urlopen(getrequest(url), timeout=our_timeout) as response:
                    data = response.read()
                    content_type = response.headers.get_content_type()
                    splitted = content_type.split("/")

                    if content_type in content_type_table:
                        extension = content_type_table[content_type]
                    else:
                        extension = splitted[1]

                    retval = output + "." + extension

                    with open(output + "." + extension, "wb") as out_file:
                        out_file.write(data)

                    finished = True
            #urllib.request.urlretrieve(url, filename=output)
            if finished:
                break
        except urllib.error.HTTPError as e:
            print(e)
            if e.code == 404 or e.code == 403:
                retval = None
                break
        except Exception as e:
            print(e)

    return retval


def download_real_cb(url, output, options, cb):
    retval = download_real(url, output, options)
    if cb:
        cb(retval)

def download(pool, url, output, options = None, cb = None):
    if do_async:
        pool.add_task(download_real_cb, url, output, options, cb)
    else:
        download_real_cb(url, output, options, cb)

def check_image(url):
    try:
        if os.stat(url).st_size == 0:
            return False

        image = PIL.Image.open(url)
        if image.format == "JPEG":
            image.load()
        else:
            image.verify()
        return True
    except:
        return False

def check_video(url):
    if os.stat(url).st_size == 0:
        return False

    if url.endswith(".part"):
        return False

    our_magic = magic.from_file(url, mime=True)
    if not our_magic:
        return False

    if our_magic.split("/")[0] != "video" and our_magic != "application/x-shockwave-flash":
        return False

    return True

def download_image(pool, url, output, options = None, *args, **kwargs):
    global has_errors
    if not "total_times" in kwargs:
        kwargs["total_times"] = 0

    if not "same_times" in kwargs:
        kwargs["same_times"] = 0

    if not "lastcontent" in kwargs:
        kwargs["lastcontent"] = None

    if not "func" in kwargs:
        kwargs["func"] = check_image

    if kwargs["total_times"] >= 5 or kwargs["same_times"] >= 2:
        print("Tried downloading %s too many times, stopping" % url)
        has_errors = True
        error_files.append(url)
        return

    kwargs["total_times"] += 1

    def download_image_inner(output):
        global has_errors
        if not output or not os.path.exists(output):
            print(str(output) + " does not exist? (URL: %s)" % url)
            has_errors = True
            error_files.append(url)
            return

        if kwargs["func"](output):
            return

        with open(output, "rb") as out_file:
            content = out_file.read()

        if content == kwargs["lastcontent"]:
            kwargs["same_times"] += 1
        else:
            kwargs["lastcontent"] = content
            kwargs["same_times"] = 0

        download_image(pool, url, output, options, *args, **kwargs)

    download(pool, url, output, options, download_image_inner)


def download_video(pool, url, output, options = None, *args, **kwargs):
    kwargs["func"] = check_video
    download_image(pool, url, output, options, *args, **kwargs)


def geturl(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req)
        return resp.geturl()
    except Exception as e:
        print(e)

def sanitize_path(text):
    if windows_path:
        return text.rstrip(".")
    return text

def fsify_base(text):
    return sanitize_path(text.replace("\n", " ").replace("\r", " ").replace("/", " (slash) "))

def old_fsify(text):
    return sanitize_path(fsify_base(text)[:50])

def fsify_album(text):
    return sanitize_path(fsify_base(text)[:100].strip())

def getdirs(base):
    return [x[0] for x in os.walk(base)]

def file_exists(f, dirs):
    for d in dirs:
        if os.path.exists(os.path.join(d, f)):
            return True
    return False

def image_exists(f, dirs):
    for d in dirs:
        if os.path.exists(os.path.join(d, f)) and check_image(os.path.join(d, f)):
            return True
    return False

from subprocess import check_output
def get_pid(name):
    return check_output(["pgrep","-f",name]).split()
import time

def get_processes_amt():
    dir = "/tmp/"
    files = os.listdir(dir)
    amt = 0
    for file in files:
        if file.startswith(".tdownload."):
            process = file.split(".")[-1]
            if not os.path.exists("/proc/" + process):
                print("/tmp/" + file + " doesn't exist")
                try:
                    os.unlink("/tmp/" + file)
                except Exception as e:
                    print(e)
            else:
                amt += 1
    return amt

if __name__ == "__main__":
    myjson = sys.stdin.read()
    sys.stdin.close()

    if len(sys.argv) > 1 and sys.argv[1] == "async":
        do_async = True
        no_lockfile = True

        amt = 10
        if len(sys.argv) > 2:
            amt = int(sys.argv[2])

        pool = ThreadPool(amt)
    else:
        pool = None

    processes = get_processes_amt()
    times = 0
    while processes > thresh_processes and not no_lockfile and running:
        time.sleep(2)
        processes = get_processes_amt()
        times += 1
        if times > thresh_sleep_times:
            no_lockfile = True
            break

    if not running:
        sys.exit()

    if not no_lockfile:
        lockfile = "/tmp/.tdownload." + str(os.getpid())
        open(lockfile, 'a').close()

    signal.signal(signal.SIGINT, signal_handler)

    jsond = json.loads(myjson)
    #print(jsond)

    prefix = "~/Pictures/social/"
    if "prefix" in util.tokens:
        prefix = util.tokens["prefix"]
    home = os.path.expanduser(prefix)

    generator = jsond["config"]["generator"]
    thedirbase = home + "/" + generator + "/" + jsond["author"] + "/"

    if not os.path.exists(thedirbase):
        os.makedirs(thedirbase, exist_ok=True)
        filesbase = []
    else:
        filesbase = os.listdir(thedirbase)

    dirs = getdirs(thedirbase)

    current_id = 1
    all_entries = len(jsond["entries"])

    for entry in jsond["entries"]:
        if not running:
            break

        our_id = current_id
        current_id = current_id + 1

        if (not entry["images"] or len(entry["images"]) <= 0) and (not entry["videos"] or len(entry["videos"]) <= 0):
            continue

        entry_caption = entry["caption"]
        if "media_caption" in entry:
            entry_caption = entry["media_caption"]

        authorcaption = ""
        if "author" in entry and entry["author"] != jsond["author"]:
            authorcaption = "[@" + entry["author"] + "] "

        if not entry_caption or len(entry_caption) == 0:
            newcaption = ""
        else:
            #oldcaption = " " + old_fsify(entry_caption)
            newcaption = " " + authorcaption + old_fsify(entry_caption)

        newdate = datetime.datetime.fromtimestamp(entry["date"]).isoformat()

        if "album" in entry and entry["album"]:
            oldthedir = thedirbase + old_fsify(entry["album"]) + "/"
            thedir = thedirbase + fsify_album(entry["album"]) + "/"

            if not os.path.exists(thedir):
                if os.path.exists(oldthedir):
                    print("Renaming " + oldthedir + " to " + thedir)
                    os.rename(oldthedir, thedir)
                    dirs.append(thedir)
                    files = os.listdir(thedir)
                else:
                    os.makedirs(thedir, exist_ok=True)
                    dirs.append(thedir)
                    files = []
            else:
                files = os.listdir(thedir)
        else:
            thedir = thedirbase
            files = filesbase

        if not entry["images"]:
            entry["images"] = []

        for i, image in enumerate(entry["images"]):
            if not running:
                break

            #imageurl = geturl(image)
            imageurl = image

            ext = getext(imageurl)

            if ext:
                ext = "." + ext
            else:
                ext = ""

            suffix = getsuffix(i, entry["images"])

            output = "(%s)%s%s%s" % (newdate, newcaption, suffix, ext)
            fullout = thedir + output

            exists = False
            for file_ in files:
                if file_.startswith(output) and check_image(os.path.join(thedir, file_)):
                    exists = True
                    break


            if exists:
                continue

            #if os.path.exists(fullout):
            #    continue

            exists = False
            for file_ in filesbase:
                if file_.startswith(output) and check_image(os.path.join(thedirbase, file_)):
                    exists = True
                    break

            if exists:
                if not ext:
                    ext = getext(thedirbase + file_)

                    if ext:
                        os.rename(thedirbase + file_, fullout + "." + ext)
                    else:
                        os.rename(thedirbase + file_, fullout)
                        print("WARNING: no extension for " + file_)
                else:
                    os.rename(thedirbase + file_, fullout)

                print("[RN:IMAGE] " + output +" (%i/%i)" % (our_id, all_entries))
                continue

            if image_exists(output, dirs):
                continue

            sys.stdout.write("[DL:IMAGE] " + output + " (%i/%i)... " % (our_id, all_entries))
            sys.stdout.flush()

            if ext == "":
                download_image(pool, imageurl, fullout, {"addext": True})
            else:
                download_image(pool, imageurl, fullout, {"addext": False})
            #print ("Downloaded image " + output + " (%i/%i)" % (our_id, all_entries))
            print("Done")


        if not entry["videos"]:
            entry["videos"] = []

        for i, video in enumerate(entry["videos"]):
            if not running:
                break
            #ext = getext(video["video"])

            suffix = getsuffix(i, entry["videos"])

            url = quote_url(video["video"])
            mymatch = re.match(r".*twitter.com/i/videos/(?P<id>[0-9]*)", url)
            if mymatch:
                url = "http://twitter.com/i/videos/tweet/%s" % mymatch.group("id")

            output = "(%s)%s%s" % (newdate, newcaption, suffix)
            fullout = thedir + output

            exists = False
            for file_ in files:
                if file_.startswith(output) and check_video(os.path.join(thedir, file_)):
                    exists = True
                    break

            if exists:
                continue

            sys.stdout.write("[DL:VIDEO] " + output + " (%i/%i)... " % (our_id, all_entries))
            sys.stdout.flush()

            if jsond["config"]["generator"] == "instagram" or url.endswith(".mp4"):
                fullout = fullout + ".mp4"

                #if os.path.exists(fullout):
                if file_exists(output, dirs):
                    continue

                download_video(pool, url, fullout)
            else:
                fullout = fullout + ".%(ext)s"

                p = subprocess.Popen(["youtube-dl", url, "-o", fullout])

                if not do_async:
                    p.wait()

            #print("Downloaded video " + output + " (%i/%i)" % (our_id, all_entries))
            print("Done")
            sys.stdout.flush()

    if do_async:
        pool.wait_completion()

    if lockfile:
        try:
            os.unlink(lockfile)
        except Exception as e:
            print(e)

    if not has_errors:
        print("[FINAL] Done")
    else:
        print("[FINAL,ERRORS] Done:")
        pprint.pprint(error_files)

    sys.stdout.flush()
