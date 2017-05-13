import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import re
import html
import pprint

def quote_url(link):
    link = urllib.parse.unquote(link).strip()
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(link)
    path = urllib.parse.quote(path)
    link = urllib.parse.urlunsplit((scheme, netloc, path, query, fragment)).replace("%3A", ":")
    return link

def download_real(url, *args, **kwargs):
    url = quote_url(url)
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    request.add_header('Pragma', 'no-cache')
    request.add_header('Cache-Control', 'max-age=0')
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

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
    url = sys.argv[1]

    data = download(url)
    #data = download("file:///tmp/naver.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    jsondata = soup.find(attrs={"type": "application/ld+json"}).text
    jsondecode = ujson.loads(jsondata)

    myjson = {
        "title": None,
        "author": None,
        "config": {
            "generator": "tumblr"
        },
        "entries": []
    }

    urls = [None]

    if jsondecode["@type"] == "ItemList":
        urls = []
        for item in jsondecode["itemListElement"]:
            urls.append(item["url"])


    i = 0
    origurl = url
    for url in urls:
        if url:
            sys.stderr.write("\r[%i/%i] Downloading %s... " % (i+1, len(urls), url))
            i = i + 1
            data = download(url)
            soup = bs4.BeautifulSoup(data, 'lxml')
            jsondata = soup.find(attrs={"type": "application/ld+json"}).text
            jsondecode = ujson.loads(jsondata)
            sys.stderr.write("done\n")
        else:
            url = origurl

        videosel = soup.select(".tumblr_video_container > iframe")
        videos = []
        if len(videosel) > 0:
            if len(videosel) > 1:
                sys.stderr.write("FIXME: More than one video!\n")

            ogimage = soup.find("meta", attrs={"property": "og:image"})
            if not ogimage:
                sys.stderr.write("Couldn't find video thumbnail!\n")

            video_thumb = urllib.parse.urljoin(url, ogimage["content"])
            videourl = re.sub("[^/]*\.tumblr.com/", "vtt.tumblr.com/", video_thumb)
            videourl = re.sub("_[a-z]*[0-9]*\.[^/]*$", ".mp4", videourl)
            videos = [{"image": video_thumb, "video": videourl}]
            print(videourl)
            """sys.stderr.write("Downloading video page... ")
            videourl = videos[0]["src"]
            videodata = download(videourl)
            videosoup = bs4.BeautifulSoup(videodata)
            videosource = videosoup.select("source")
            if len(videosource) == 0:
                sys.stderr.write("Couldn't find video\n")

            if len(videosource) > 1:
                sys.stderr.write("FIXME: More than one video!\n")

            sys.stderr.write("done\n")
            pprint.pprint(videos)"""

        author = jsondecode["author"]
        myjson["title"] = author
        myjson["author"] = author

        date = parse(jsondecode["datePublished"])

        if "headline" not in jsondecode:
            title = "[" + re.search("/post/([0-9]*)", jsondecode["url"]).group(1) + "]"

            if "articleBody" in jsondecode:
                title += " " + jsondecode["articleBody"]
        else:
            title = jsondecode["headline"]
        album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title

        images = []

        if "image" in jsondecode:
            if "@list" in jsondecode["image"]:
                images = jsondecode["image"]["@list"]
            else:
                images = [jsondecode["image"]]

        if len(images) == 0 and len(videos) == 0:
            continue

        myjson["entries"].append({
            "caption": title,
            #"album": album,
            "date": date,
            "author": author,
            "images": images,
            "videos": videos
        })

    print(ujson.dumps(myjson))

if __name__ == "__main__":
    main()
