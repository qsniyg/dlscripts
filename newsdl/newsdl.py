import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import re
import html
import pprint


def download_real(url, *args, **kwargs):
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


def get_selector(soup, selectors):
    tag = None

    for selector in selectors:
        tag = soup.select(selector)
        if tag and len(tag) > 0:
            break
        else:
            tag = None

    return tag


def get_title(soup):
    return html.unescape(soup.find("meta", attrs={"property": "og:title"})["content"])


def get_author(url, soup):
    if "naver." in url:
        return "naver"

    return None


def get_max_quality(url):
    if "naver." in url:
        url = re.sub("\?.*", "", url)
        #if "imgnews" not in url:
        # do blogfiles
    return url


def main():
    url = sys.argv[1]

    data = download(url)
    #data = download("file:///tmp/naver.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    myjson = {
        "title": None,
        "author": None,
        "config": {
            "generator": "news"
        },
        "entries": []
    }

    author = get_author(url, soup)

    if not author:
        sys.stderr.write("unknown site\n")
        return

    title = get_title(soup)

    myjson["title"] = author
    myjson["author"] = author

    datetag = get_selector(soup, [
        ".article_info .author em"
    ])

    if not datetag:
        sys.stderr.write("no recognizable date\n")
        return

    date = parse(datetag[0].text.replace("오후", ""))

    album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title

    imagestag = get_selector(soup, [
        "#articeBody img"
    ])

    if not imagestag:
        sys.stderr.write("no recognizable images\n")
        return

    images = []
    for image in imagestag:
        images.append(get_max_quality(image["src"]))

    myjson["entries"].append({
        "caption": title,
        "album": album,
        "date": date,
        "author": author,
        "images": images,
        "videos": [] # for now
    })

    print(ujson.dumps(myjson))

if __name__ == "__main__":
    main()
