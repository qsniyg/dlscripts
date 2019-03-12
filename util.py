try:
    import ujson
except ImportError:
    import json as ujson
import os
import urllib
import urllib.parse
import urllib.request
import http
import queue
import threading
import sys
import datetime

running = True

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


def quote_url(link):
    link = urllib.parse.unquote(link).strip()
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(link)
    path = urllib.parse.quote(path)
    link = urllib.parse.urlunsplit((scheme, netloc, path, query, fragment)).replace("%3A", ":")
    return link


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


def download_real(url, *args, **kwargs):
    url = quote_url(url)
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    if "timeout" in kwargs:
        download_timeout = kwargs["timeout"]
    else:
        download_timeout = 30

    if "noheaders" in kwargs and kwargs["noheaders"]:
        pass
    else:
        request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
        request.add_header('Pragma', 'no-cache')
        request.add_header('Cache-Control', 'max-age=0')
        request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

    with urllib.request.urlopen(request, timeout=download_timeout) as response:
        charset = response.headers.get_content_charset()

        if charset:
            return response.read().decode(charset)
        else:
            return response.read()


def getrequest(url, *args, **kargs):
    request = urllib.request.Request(quote_url(url))
    if (".photobucket.com" not in url and
        ".tinypic.com" not in url and
       (".fbcdn.net" not in url and "/instagram." not in url)):
        request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
        request.add_header('Pragma', 'no-cache')
        request.add_header('Cache-Control', 'max-age=0')
        request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    if "end_range" in kargs and kargs["end_range"] > 0:
        request.add_header('Range', 'bytes=%s-%s' % (kargs["start_range"], kargs["end_range"]))
    return request


def download_file(url, output):
    running = True
    timeout_s = 30
    thresh_resume = 8
    thresh_same_resume = 3

    our_timeout = timeout_s
    retval = -1

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

                    retval = output

                    try:
                        read_file = response.read()
                    except http.client.IncompleteRead as e:
                        read_file = e.partial

                    if not out_file:
                        out_file = open(retval, "wb")
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
                retval = 200
                break

        except urllib.error.HTTPError as e:
            print(e)
            retval = e.code
            if e.code == 404 or e.code == 403 or e.code == 410:  # 410: instagram
                return retval
        except Exception as e:
            print(e)

    return retval

def download(url, *args, **kwargs):
    #return re.sub(r"^.*?<html", "<html", download_real(url), flags=re.S)
    return download_real(url, *args, **kwargs)


if __name__ == "__main__":
    print("don't execute this file")
    exit()

tokens = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "tokens.json"), "rb") as f:
        tokens = ujson.loads(f.read())
except Exception as e:
    pass


class Logger(object):
    def __init__(self, origstream, filename="Default.log"):
        self.terminal = origstream
        try:
            self.log = open(filename, "a")
        except Exception:
            self.log = None

    def write(self, message):
        self.terminal.write(message)
        if self.log:
            try:
                self.log.write(message)
            except Exception:
                pass
        self.flush()

    def flush(self):
        self.terminal.flush()
        if self.log:
            try:
                self.log.flush()
            except Exception:
                pass


defaultlogpath = os.path.expanduser('~/.cache/dlscripts/')
os.makedirs(defaultlogpath, exist_ok=True)


def enable_logging():
    sys.stdout = Logger(sys.stdout, defaultlogpath + str(datetime.datetime.now().isoformat()) + "." + str(os.getpid()) + ".olog")
    sys.stderr = Logger(sys.stderr, defaultlogpath + str(datetime.datetime.now().isoformat()) + "." + str(os.getpid()) + ".elog")

if tokens.get("log") is True:
    enable_logging()
