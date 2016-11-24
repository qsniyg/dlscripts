import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import datetime
import re


def get_string(element):
    if type(element) is bs4.element.NavigableString:
        return str(element.string)
    elif element.name == "img":
        return element["title"]
    else:
        string = ""

        for i in element.children:
            string += get_string(i)

        return string


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
    #data = download("file:///tmp/wordpress.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    #username = soup.select("h3.username")[0].text
    username = re.sub("https?://([^.]*)\..*", "\\1", soup.find("meta", attrs={"property": "og:url"})["content"])
    date = parse(soup.select("time.published")[0]["datetime"])
    caption = soup.find("meta", attrs={"property": "og:title"})["content"]
    #description = soup.select("div.info .glyphicon-user")[0].parent.text

    content = soup.select("div.entry-content")[0]

    myjson = {
        "title": username,
        "author": username,
        "config": {
            "generator": "wordpress"
        },
        "entries": []
    }

    imgi = 0
    for img in content.findAll("img"):
        imgi = imgi + 1

        url = re.sub("\?.*", "", img["src"])

        if img.has_attr("alt") and len(img["alt"]) > 0:
            imgcaption = img["alt"]
        else:
            imgcaption = "img" + str(imgi)

        myjson["entries"].append({
            "caption": imgcaption,
            "date": date,
            "author": username,
            "album": caption,
            "images": [url],
            "videos": []
        })

    print(ujson.dumps(myjson))
