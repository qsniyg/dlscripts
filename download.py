import sys
#import json
import urllib.parse
#import urllib.request
#import shutil
import datetime
import re
import subprocess
import os
import os.path
#import glob
import signal
import threading
import queue
import pprint
#import http.client
#import PIL.Image
#import magic
import hashlib
import binascii
import redis
import errno
sys.path.append(".")
import util

windows_path = False
if "windows" in util.tokens and (util.tokens["windows"] == 1 or util.tokens["windows"] is True):
    windows_path = True

thresh_processes = 15
thresh_sleep_times = 600

if "thresh_processes" in util.tokens and util.tokens["thresh_processes"]:
    thresh_processes = util.tokens["thresh_processes"]

if "thresh_sleep_times" in util.tokens and util.tokens["thresh_sleep_times"]:
    thresh_sleep_times = util.tokens["thresh_sleep_times"]

thresh_resume = 8
thresh_same_resume = 3

thresh_redis_check = 3

timeout_s = 30

debug = False
overwrite = False
do_async = False
lockfile = None
no_lockfile = False

livelocks = []

has_errors = False
error_files = []

similar_queue = []

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


def getext(urls, local=False, *args, **kwargs):
    origtype = type(urls)
    if origtype not in [list, tuple]:
        urls = [urls]

    ret = []

    for url in urls:
        if local:
            match = re.match(r".*\.(?P<ext>[^. ]*)$", url)
        else:
            match = re.match(r"[^?]*\.(?P<ext>[^?/:]*)(:[^?/]*)?$", url)

        if not match:
            ret.append(None)
            continue

        addme = match.group("ext")

        if "lower" in kwargs and kwargs["lower"]:
            addme = addme.lower()

        ret.append(addme)

    if origtype not in [list, tuple]:
        return ret[0]
    else:
        for ext in ret:
            if ext:
                return ret
        return None


similarexts = [
    ["jpg", "jpeg"],
    ["mp4", "mkv"]
]


def similarext(url1, url2):
    url1_ext = getext(url1, True).lower()
    url2_ext = getext(url2, True).lower()

    if url1_ext == url2_ext:
        return True

    for ext in similarexts:
        if url1_ext in ext and url2_ext in ext:
            return True

    return False


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
    import urllib.request
    #request = urllib.request.Request(quote_url(url))
    request = urllib.request.Request(url)
    if (".photobucket.com" not in url and
        ".tinypic.com" not in url):
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


# http://stackoverflow.com/a/3431838
def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def crc32(fname):
    with open(fname, "rb") as f:
        crc = binascii.crc32(f.read()) & 0xffffffff
    return crc


def get_file_hash(fname):
    return [md5(fname), crc32(fname)]


def cmp_file_hash(hash1, hash2):
    return hash1[0] == hash2[0] and hash1[1] == hash2[1]


def fix_tumblr(x):
    if ".media.tumblr.com" in x:
       return re.sub("(.*)//[0-9]*(.media.tumblr.com/.*)", "\\1//68\\2", x)

    return x


def download_real(url, output, options):
    if not running:
        return

    import urllib.request
    import http.client

    if not options:
        options = {
            "addext": False,
            "timeout": timeout_s
        }

    if "addext" not in options:
        options["addext"] = False

    if "timeout" not in options:
        options["timeout"] = timeout_s

    if "similar" not in options:
        options["similar"] = []

    addext = options["addext"]

    if type(addext) in [list, tuple]:
        if len(addext) > 0:
            addext = addext[0]
        else:
            addext = False

    our_timeout = options["timeout"]

    retval = output

    master_times = 1
    while running:
        if master_times >= 5:
            print("Tried 5 times, giving up")
            break
        elif master_times > 1:
            print("Trying again (" + str(master_times) + "/5)")
            url = fix_tumblr(url)
        master_times += 1

        finished = False

        try:
            #with open(output, 'wb') as out_file:
            out_file = None
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

                start_r = 0
                if out_file:
                    start_r = out_file.tell()

                request = getrequest(url, start_range=start_r, end_range=content_length)
                with urllib.request.urlopen(request, timeout=our_timeout) as response:
                    for header in response.headers._headers:
                        if header[0].lower() == "content-length":
                            content_length = int(header[1])

                    content_type = response.headers.get_content_type()
                    splitted = content_type.split("/")

                    if content_type in content_type_table:
                        extension = content_type_table[content_type]
                    elif (content_type != "text/plain"
                          and content_type != response.headers.get_default_type()
                          and content_type != "application/octet-stream"):
                        extension = splitted[1]
                    elif addext:
                        extension = addext
                    else:
                        print("WARNING: no extension")
                        extension = ""

                    retval = output + "." + extension

                    if not out_file:
                        out_file = open(output + "." + extension, "wb")

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

            if finished:
                if out_file:
                    out_file.close()
                break

        except urllib.error.HTTPError as e:
            print(e)
            if e.code == 404 or e.code == 403:
                retval = None
                break
        except Exception as e:
            print(e)

    if len(options["similar"]) > 0:
        #ourcrc = crc32(retval)
        ourcrc = None
        ourmd5 = md5(retval)
        oursize = os.path.getsize(retval)

        for similar in options["similar"]:
            if os.path.getsize(similar) != oursize:
                continue

            similarmd5 = md5(similar)

            if ourmd5 == similarmd5:
                global similar_queue
                similar_queue.append(similar)

            continue

            """similarcrc = crc32(similar)

            if ourcrc == similarcrc:
                if not ourmd5:
                    ourmd5 = md5(retval)

                similarmd5 = md5(similar)

                if ourmd5 == similarmd5:
                    global similar_queue
                    similar_queue.append(similar)"""

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


def get_redis_key(url):
    key = os.path.abspath(url)
    if key.startswith(home):
        key = key[len(home):]
    key = "DLPATH:" + key
    return key

def get_redis_meta_str(url):
    return get_meta_str(url).encode("utf-8")

def check_redis(url):
    if not rinstance:
        return None

    meta = get_redis_meta_str(url)
    key = get_redis_key(url)

    try:
        val = rinstance.hgetall(key)
    except:
        return None

    expire_redis(key)

    if b"meta" in val and val[b"meta"] == meta:
        if b"times" in val and int(val[b"times"]) >= thresh_redis_check:
            return True
    return False

def expire_redis(key):
    if not rinstance:
        return

    try:
        rinstance.expire(key, 60*60*24*7)
    except:
        return

def update_redis(url):
    if not rinstance:
        return None

    meta = get_redis_meta_str(url)
    key = get_redis_key(url)

    val = rinstance.hgetall(key)

    if b"meta" in val and val[b"meta"] == meta:
        if b"times" not in val:
            val[b"times"] = "0"
        val[b"times"] = str(int(val[b"times"]) + 1)
    else:
        val = {
            "meta": meta,
            "times": "0"
        }

    rinstance.hmset(key, val)
    expire_redis(key)


def check_image(url):
    retval = False
    try:
        if check_redis(url):
            return True

        if os.stat(url).st_size == 0:
            return False

        import PIL.Image
        image = PIL.Image.open(url)
        if image.format == "JPEG":
            image.load()
        else:
            image.verify()

        retval = True
    except:
        return False

    try:
        update_redis(url)
    except Exception as e:
        print(e)

    return retval

def check_video(url):
    if check_redis(url):
        return True

    if os.stat(url).st_size == 0:
        return False

    if url.endswith(".part"):
        return False

    import magic

    our_magic = magic.from_file(url, mime=True)
    if not our_magic:
        return False

    if our_magic.split("/")[0] != "video" and our_magic != "application/x-shockwave-flash":
        return False

    try:
        update_redis(url)
    except Exception as e:
        print(e)

    return True

def download_image(pool, url, output, options = None, *args, **kwargs):
    global has_errors

    if not running:
        return

    if not "url_id" in kwargs:
        kwargs["url_id"] = 0

    if not "total_times" in kwargs:
        kwargs["total_times"] = 0

    if not "same_times" in kwargs:
        kwargs["same_times"] = 0

    if not "lastcontent" in kwargs:
        kwargs["lastcontent"] = None

    if not "func" in kwargs:
        kwargs["func"] = check_image

    if kwargs["total_times"] >= 5 or kwargs["same_times"] >= 2:
        if type(url) in [list, tuple] and len(url) > (kwargs["url_id"] + 1):
            print("Tried downloading %s too many times, going to next url" % url[kwargs["url_id"]])
            kwargs["url_id"] += 1
            kwargs["total_times"] = 0
            kwargs["same_times"] = 0
            kwargs["lastcontent"] = None

            if type(options) == dict and "addext" in options and type(options["addext"]) in [list, tuple]:
                options["addext"] = options["addext"][1:]

            download_image(pool, url, output, options, *args, **kwargs)
            return

        print("Tried downloading %s too many times, stopping" % str(url))
        has_errors = True
        error_files.append(url)
        return

    kwargs["total_times"] += 1

    oldoutput = output

    def download_image_inner(output):
        global has_errors
        if not output or not os.path.exists(output):
            print(str(output) + " does not exist? (URL: %s)" % url)

            if type(url) in [list, tuple] and len(url) > (kwargs["url_id"] + 1):
                print("Trying next url")
                kwargs["url_id"] += 1
                kwargs["total_times"] = 0
                kwargs["same_times"] = 0
                kwargs["lastcontent"] = None

                if type(options) == dict and "addext" in options and type(options["addext"]) in [list, tuple]:
                    options["addext"] = options["addext"][1:]

                download_image(pool, url, oldoutput, options, *args, **kwargs)
                return

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

        download_image(pool, url, oldoutput, options, *args, **kwargs)

    newurl = url
    if type(newurl) in [list, tuple]:
        newurl = url[kwargs["url_id"]]

    download(pool, newurl, output, options, download_image_inner)


def download_video(pool, url, output, options = None, *args, **kwargs):
    kwargs["func"] = check_video
    download_image(pool, url, output, options, *args, **kwargs)


def geturl(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req)
        return resp.geturl()
    except Exception as e:
        print(e)

def sanitize_path(text):
    if windows_path:
        return text.rstrip(".").rstrip(" ").replace(":", "-").replace('"', "'").replace("<", "(lt)").replace(">", "(gt)").replace("\\", " (bslash) ").replace("|", "(pipe)").replace("?", "(qmark)").replace("*", "(asterisk)")
    return text

def remext(file1):
    return re.sub(r"\.[^. ]*$", "", file1)
    #return os.path.splitext(file1)[0]

def similar_filename(file1, file2):
    return os.path.basename(remext(file1)) == os.path.basename(file2) # hack!!

def old_fsify_base(text):
    return sanitize_path(text.replace("\n", " ").replace("\r", " ").replace("/", " (slash) "))

def fsify_base(text):
    return sanitize_path(text.replace("\n", " ").replace("\r", " ").replace("/", "∕"))

def old_fsify(text):
    return sanitize_path(old_fsify_base(text)[:50])

def old_fsify_album(text):
    return sanitize_path(old_fsify_base(text)[:100].strip())

def fsify_album_oldbase(text):
    return sanitize_path(old_fsify_base(text)[:200].strip())

def fsify_album(text):
    return sanitize_path(fsify_base(text)[:200].strip())

def sanitize_caption(entry_caption, entry):
    authorcaption = ""
    if "author" in entry and entry["author"] != jsond["author"] and not is_index:
        authorcaption = "[@" + entry["author"] + "] "

    if not entry_caption or len(entry_caption) == 0:
        newcaption = ""
    else:
        #oldcaption = " " + old_fsify(entry_caption)
        newcaption = " " + authorcaption + old_fsify_album(entry_caption)

        try:
            encoded = newcaption.encode("utf-8")
            encoded_len = len(encoded)
        except Exception as e:
            encoded_len = 10000

        if encoded_len > 200:
            newcaption = " " + authorcaption + old_fsify(entry_caption)

    return newcaption

def get_meta_str(f):
    st = os.stat(f)

    return "MOD: " + str(st.st_mtime) + " SIZE: " + str(st.st_size)

def getdirs(base):
    return [x[0] for x in os.walk(base)]

def file_exists(f, dirs):
    for d in dirs:
        for i in os.listdir(d):
            if similar_filename(i, f):
                return True
    return False

def video_exists(f, dirs):
    for d in dirs:
        for i in os.listdir(d):
            if similar_filename(i, f) and check_video(os.path.join(d, i)):
                return True
    return False

def image_exists(f, dirs):
    for d in dirs:
        for i in os.listdir(d):
            if similar_filename(i, f) and check_image(os.path.join(d, i)):
                if debug:
                    print("[DEBUG] Exists in " + d)
                return True
    return False

from subprocess import check_output
def get_pid(name):
    return check_output(["pgrep","-f",name]).split()
import time


def process_exists_proc(pid):
    return os.path.exists("/proc/" + str(pid))


# https://stackoverflow.com/a/6940314
def pid_exists(pid):
    """Check whether pid exists in the current process table.
    UNIX only.
    """
    try:
        pid = int(pid)
    except Exception as err:
        print(err)
        return True

    if pid < 0:
        return False
    if pid == 0:
        # According to "man 2 kill" PID 0 refers to every process
        # in the process group of the calling process.
        # On certain systems 0 is a valid PID but we have no way
        # to know that in a portable fashion.
        raise ValueError('invalid PID 0')
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            # ESRCH == No such process
            return False
        elif err.errno == errno.EPERM:
            # EPERM clearly means there's a process to deny access to
            return True
        else:
            # According to "man 2 kill" possible error values are
            # (EINVAL, EPERM, ESRCH)
            raise
    else:
        return True


def process_exists(pid):
    return pid_exists(pid)


subprocesses = []


def run_subprocess(arr, wait=True):
    p = subprocess.Popen(arr)
    if not do_async or wait:
        p.wait()
    else:
        subprocesses.append(p)


def get_processes_amt():
    dir = "/tmp/"
    files = os.listdir(dir)
    amt = 0
    for file in files:
        if file.startswith(".tdownload."):
            process = file.split(".")[-1]
            #if not os.path.exists("/proc/" + process):
            if not process_exists(process):
                print("Process for /tmp/" + file + " doesn't exist")
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

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug = True
        sys.argv = sys.argv[1:]

    if len(sys.argv) > 1 and sys.argv[1] == "overwrite":
        overwrite = True
        sys.argv = sys.argv[1:]

    if len(sys.argv) > 1 and sys.argv[1] == "async":
        do_async = True
        no_lockfile = True

        amt = 10
        if len(sys.argv) > 2:
            amt = int(sys.argv[2])

        pool = ThreadPool(amt)
    else:
        pool = None

    try:
        rinstance = redis.StrictRedis(host='localhost')
    except:
        rinstance = None

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

    #jsond = json.loads(myjson)
    jsond = util.ujson.loads(myjson)
    #print(jsond)

    if "no_dl" in jsond["config"] and jsond["config"]["no_dl"]:
        sys.exit()

    prefix = "~/Pictures/social/"
    if "prefix" in util.tokens:
        prefix = util.tokens["prefix"]
    if "dl_prefix" in jsond["config"] and len(jsond["config"]["dl_prefix"]) > 0:
        prefix = jsond["config"]["dl_prefix"]
    home = os.path.abspath(os.path.expanduser(prefix))

    generator = jsond["config"]["generator"]
    thedirgen = home + "/" + generator + "/"
    thedirbase = thedirgen + sanitize_path(jsond["author"]) + "/"

    is_index = False
    if "is_index" in jsond["config"] and jsond["config"]["is_index"]:
        is_index = True

    no_videodl = False
    if "no_videodl" in jsond["config"] and jsond["config"]["no_videodl"]:
        no_videodl = True

    if not is_index:
        if not os.path.exists(thedirbase):
            os.makedirs(thedirbase, exist_ok=True)
            filesbase = []
        else:
            filesbase = os.listdir(thedirbase)
        dirs = getdirs(thedirbase)
    else:
        filesbase = []
        dirs = []

    current_id = 1
    all_entries = len(jsond["entries"])

    for entry in jsond["entries"]:
        if not running:
            break

        our_id = current_id
        current_id = current_id + 1

        if (not entry["images"] or len(entry["images"]) <= 0) and (not entry["videos"] or len(entry["videos"]) <= 0):
            continue

        if is_index:
            thedirbase = thedirgen + sanitize_path(entry["author"]) + "/"
            if not os.path.exists(thedirbase):
                os.makedirs(thedirbase, exist_ok=True)
                filesbase = []
            else:
                filesbase = os.listdir(thedirbase)
            dirs = getdirs(thedirbase)

        entry_caption = entry["caption"]
        if "media_caption" in entry:
            entry_caption = entry["media_caption"]

        """authorcaption = ""
        if "author" in entry and entry["author"] != jsond["author"]:
            authorcaption = "[@" + entry["author"] + "] "

        if not entry_caption or len(entry_caption) == 0:
            newcaption = ""
        else:
            #oldcaption = " " + old_fsify(entry_caption)
            newcaption = " " + authorcaption + old_fsify(entry_caption)"""
        newcaption = sanitize_caption(entry_caption, entry)

        newdate = datetime.datetime.fromtimestamp(entry["date"]).isoformat()

        if "album" in entry and entry["album"]:
            similardirs = []

            oldthedir = thedirbase + old_fsify_album(entry["album"]) + "/"
            similardirs.append(oldthedir)
            oldthedir = thedirbase + fsify_album_oldbase(entry["album"]) + "/"
            similardirs.append(oldthedir)

            thedir = thedirbase + fsify_album(entry["album"]) + "/"

            similardir = None
            if "similaralbum" in entry:
                similardir = thedirbase + fsify_album(entry["similaralbum"]) + "/"
                similardirs.append(oldthedir)

            if not os.path.exists(thedir):
                renamed_similar = False
                for similardir in similardirs:
                    if similardir == thedir or not os.path.exists(similardir):
                        continue
                    print("Renaming " + similardir + " to " + thedir)
                    os.rename(similardir, thedir)
                    if similardir in dirs:
                        dirs.remove(similardir)
                    if similardir[:-1] in dirs: # to remove the trailing /
                        dirs.remove(similardir[:-1])
                    dirs.append(thedir)
                    files = os.listdir(thedir)
                    renamed_similar = True
                    break

                if not renamed_similar:
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

            if debug:
                print("[DEBUG] " + str(our_id) + " " + str(i))
                pprint.pprint(entry)

            #imageurl = geturl(image)
            imageurl = image

            ext = getext(imageurl)

            ##if ext:
            ##    dotext = "." + ext
            ##else:
            ##    dotext = ""

            suffix = getsuffix(i, entry["images"])

            #output = "(%s)%s%s%s" % (newdate, newcaption, suffix, dotext)
            output = sanitize_path("(%s)%s%s" % (newdate, newcaption, suffix))

            similaroutput = None
            if "similarcaption" in entry:
                newsimilarcaption = sanitize_caption(entry["similarcaption"], entry)
                similaroutput = sanitize_path("(%s)%s%s" % (newdate, newsimilarcaption, suffix))

            fullout = thedir + output

            exists = False
            for file_ in files:
                if similar_filename(file_, output) and check_image(os.path.join(thedir, file_)):
                    exists = True
                    break

            if exists and not overwrite:
                if debug:
                    print("[DEBUG] exists")
                continue

            similar = []
            if similaroutput:
                for file_ in files:
                    if similar_filename(file_, similaroutput) and check_image(os.path.join(thedir, file_)):
                        similar.append(os.path.join(thedir, file_))

            #if os.path.exists(fullout):
            #    continue

            exists = False
            for file_ in filesbase:
                if similar_filename(file_, output) and check_image(os.path.join(thedirbase, file_)):
                    exists = True
                    break

            renamed = False
            if exists:
                if debug:
                    print("[DEBUG] similar exists")

                oext = getext(thedirbase + file_, True)
                if not ext or True: # hackish
                    if oext:
                        if thedirbase + file_ != fullout + "." + oext:
                            os.rename(thedirbase + file_, fullout + "." + oext)
                            renamed = True
                    else:
                        if thedirbase + file_ != fullout:
                            os.rename(thedirbase + file_, fullout)
                            renamed = True
                            print("WARNING: no extension for " + file_)
                else:
                    if thedirbase + file_ != fullout:
                        os.rename(thedirbase + file_, fullout)
                        renamed = True

                if renamed:
                    print("[RN:IMAGE] " + output +" (%i/%i)" % (our_id, all_entries))
                    continue

            if image_exists(output, dirs) and not overwrite:
                continue

            sys.stdout.write("[DL:IMAGE] " + output + " (%i/%i)... " % (our_id, all_entries))
            sys.stdout.flush()

            download_options = {
                "addext": ext,
                "similar": similar
            }
            download_image(pool, imageurl, fullout, download_options)
            ##if ext == "":
            ##    download_image(pool, imageurl, fullout, {"addext": True})
            ##else:
            ##    download_image(pool, imageurl, fullout, {"addext": False})
            #print ("Downloaded image " + output + " (%i/%i)" % (our_id, all_entries))
            print("Done")


        if not entry["videos"] or no_videodl:
            entry["videos"] = []

        for i, video in enumerate(entry["videos"]):
            if not running:
                break
            #ext = getext(video["video"])

            live_video = False
            if "live" in video and video["live"]:
                live_video = True
                #continue

            streamlink_live = False
            if "live_streamlink" in video and video["live_streamlink"]:
                streamlink_live = True

            suffix = getsuffix(i, entry["videos"])

            video_urls = video["video"]
            if type(video_urls) not in (list, tuple):
                video_urls = [video_urls]
            if "video_dash" in video:
                if video["video_dash"][0] == "<":
                    video["video_dash"] = "data:application/dash+xml," + urllib.parse.quote(video["video_dash"], safe="")
                video_urls.insert(0, video["video_dash"])
            if len(video_urls) == 0:
                print("0 videos")
                continue
            urls = []
            for video_url in video_urls:
                #urls.append(quote_url(video_url))
                urls.append(video_url)
            mymatch = re.match(r".*twitter.com/i/videos/(?P<id>[0-9]*)", urls[0])
            if mymatch:
                urls[0] = "http://twitter.com/i/videos/tweet/%s" % mymatch.group("id")

            output = sanitize_path("(%s)%s%s" % (newdate, newcaption, suffix))
            fullout = thedir + output

            if "coauthors" in entry and type(entry["coauthors"]) == list:
                try:
                    for coauthor in entry["coauthors"]:
                        coauthor_filename = fullout + ".mp4.coauthor." + coauthor
                        if not os.path.exists(coauthor_filename):
                            open(coauthor_filename, 'a').close()
                except Exception:
                    pass

            exists = False
            existing_file = None
            for file_ in files:
                fullpath = os.path.join(thedir, file_)
                if file_.startswith(output):  # and similar_filename(file_, output):
                    #if not live_video:
                    #    if similar_filename(file_, output) and check_video(fullpath):
                    #        exists = True
                    #        break
                    #else:
                    #    #print(file_)
                    if re.search(r"\.tdownload\.[0-9]*$", file_):
                        #print("TDOWNLOAD")
                        process = file_.split(".")[-1]
                        if not process_exists(process):
                            print("Process for " + str(fullpath) + " doesn't exist")
                            try:
                                os.unlink(fullpath)
                            except Exception as e:
                                print(e)
                        else:
                            exists = True
                            break
                    elif similar_filename(file_, output) and check_video(fullpath):
                        exists = True
                        existing_file = fullpath
                        break

            if exists and not overwrite:
                continue

            if live_video:
                if "no_livedl" in jsond["config"] and jsond["config"]["no_livedl"]:
                    continue

                sys.stdout.write("[DL:LIVE] " + output + " (%i/%i)... " % (our_id, all_entries))
                sys.stdout.flush()

                fullout = fullout + ".mp4"

                livelock = fullout + ".tdownload." + str(os.getpid())
                open(livelock, 'a').close()

                livelocks.append(livelock)

                cmdline = [sys.executable, os.path.join(os.path.dirname(__file__), "iglivedl.py"), urls[0], "--output", fullout]

                if "no_live_cleanup" in util.tokens and util.tokens["no_live_cleanup"]:
                    cmdline.append("--no-cleanup")

                run_subprocess(cmdline)
                print("Done")
                continue

            if streamlink_live:
                if "no_livedl" in jsond["config"] and jsond["config"]["no_livedl"]:
                    continue

                sys.stdout.write("[DL:LIVE] " + output + " (%i/%i)... " % (our_id, all_entries))
                sys.stdout.flush()

                fullout = fullout + ".mp4"

                livelock = fullout + ".tdownload." + str(os.getpid())
                open(livelock, 'a').close()

                livelocks.append(livelock)

                cmdline = ["streamlink", "--default-stream", "best", "--hls-live-restart", "--hls-segment-threads", "3"]

                if "headers" in video and type(video["headers"]) == dict:
                    for header in video["headers"]:
                        cmdline.append("--http-header")
                        cmdline.append(header + "=" + video["headers"][header])

                cmdline.append(urls[0])
                cmdline.append("-o")
                cmdline.append(fullout)

                run_subprocess(cmdline, wait=False)
                print("Done")
                continue

            sys.stdout.write("[DL:VIDEO] " + output + " (%i/%i)... " % (our_id, all_entries))
            sys.stdout.flush()

            if (jsond["config"]["generator"] == "instagram" and "/f/instagram/v/" in urls[0]) or re.search(r"\.mp4(?:\?.*)?$", urls[0]):
                if not re.search(r"\.mp4(?:\?.*)?$", urls[0]):
                    fullout = fullout + ".mp4"

                #if os.path.exists(fullout):
                if video_exists(output, dirs):
                    continue

                download_video(pool, urls, fullout)
            else:
                newfullout = fullout + ".%(ext)s"

                """p = subprocess.Popen(["youtube-dl", url, "-o", fullout])

                if not do_async:
                    p.wait()"""
                livelock = fullout + ".tdownload." + str(os.getpid())
                open(livelock, 'a').close()

                livelocks.append(livelock)

                if exists and existing_file:
                    os.remove(existing_file)

                cmdline = ["youtube-dl", urls[0], "-o", newfullout]

                if "headers" in video and type(video["headers"]) == dict:
                    for header in video["headers"]:
                        cmdline.append("--add-header")
                        cmdline.append(header + ":" + video["headers"][header])

                run_subprocess(cmdline)

            #print("Downloaded video " + output + " (%i/%i)" % (our_id, all_entries))
            print("Done")
            sys.stdout.flush()

    if do_async:
        pool.wait_completion()

    our_id = 1
    all_entries = len(similar_queue)
    for similar_file in similar_queue:
        sys.stdout.write("[SIMILAR] Removing " + os.path.basename(similar_file) + " (%i/%i) ... " % (our_id, all_entries))
        our_id += 1
        sys.stdout.flush()
        try:
            os.remove(similar_file)
        except Exception as e:
            print(e)
        print("Done")

    for sub in subprocesses:
        sub.wait()

    if lockfile:
        try:
            os.unlink(lockfile)
        except Exception as e:
            print(e)

    for livelock in livelocks:
        try:
            os.unlink(livelock)
        except Exception as e:
            print(e)

    if not has_errors:
        print("[FINAL] Done")
    else:
        print("[FINAL,ERRORS] Done:")
        pprint.pprint(error_files)

    sys.stdout.flush()
