import bs4
import ujson
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import re
import html
import pprint


def download_real(url, *args, **kwargs):
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    #request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    #request.add_header('Pragma', 'no-cache')
    #request.add_header('Cache-Control', 'max-age=0')
    #request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset()

        if charset:
            return response.read().decode(charset)
        else:
            return response.read()


def download(url):
    #return re.sub(r"^.*?<html", "<html", download_real(url), flags=re.S)
    return download_real(url)


def main():
    search_raw = sys.argv[1]
    search_url = urllib.parse.quote(search_raw)

    cursor = None
    total = None

    myjson = {
        "title": search_raw,
        "author": search_raw,
        "config": {
            "generator": "gfycat"
        },
        "entries": []
    }

    while True:
        if total:
            sys.stderr.write("\rDownloading %i / %i ..." % (
                len(myjson["entries"]),
                total
            ))
        else:
            sys.stderr.write("\rDownloading ...")

        url = "https://api.gfycat.com/v1test/gfycats/search"
        url += "?count=100"
        url += "&search_text=" + search_url

        if cursor:
            url += "&cursor=" + cursor

        data_raw = download(url)

        if total:
            sys.stderr.write("\rProcessing %i / %i ..." % (
                len(myjson["entries"]),
                total
            ))
        else:
            sys.stderr.write("\rProcessing ...")

        data = ujson.loads(data_raw)

        if not "found" in data:
            break

        total = data["found"]

        for cat in data["gfycats"]:
            myjson["entries"].append({
                "caption": cat["gfyNumber"] + " " + cat["title"],
                "date": cat["createDate"],
                "author": search_raw,
                #"images": [cat["gifUrl"]],
                "images": [cat["max5mbGif"]],
                "videos": []
            })

        if data["cursor"] == "":
            break

        cursor = data["cursor"]

    sys.stderr.write("\n")
    sys.stderr.flush()

    print(ujson.dumps(myjson))


if __name__ == "__main__":
    main()
