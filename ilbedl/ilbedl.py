import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import re
import pprint


def download(url, *args, **kwargs):
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    request.add_header('Pragma', 'no-cache')
    request.add_header('Cache-Control', 'max-age=0')
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset()

        if charset:
            return response.read().decode(charset)
        else:
            return response.read()


if __name__ == "__main__":
    url = sys.argv[1]

    data = download(url)
    #data = download("file:///tmp/ilbe.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    content_imgs = soup.select(".contentBody img")
    title = soup.select(".titleAndUser .title a")[0].text
    permalink = soup.select(".dateAndCount .uri a")[0]["href"]
    date = parse(soup.select(".dateAndCount .date")[0].text.strip())

    id_ = re.sub(r".*ilbe\.com/([^/]*)/?.*", "\\1", permalink)

    name = "[" + str(id_) + "] " + title

    images = []
    for image in content_imgs:
        if image.has_attr("data-original"):
            images.append(image["data-original"])
        else:
            images.append(image["src"])

    myjson = {
        "title": name,
        "author": name,
        "config": {
            "generator": "ilbe"
        },
        "entries": [
            {
                "caption": "",
                "date": date,
                "author": name,
                "images": images,
                "videos": []
            }
        ]
    }

    print(ujson.dumps(myjson))
