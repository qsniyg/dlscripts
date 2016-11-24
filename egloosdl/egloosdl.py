import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse


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

    soup = bs4.BeautifulSoup(data, 'lxml')

    authortag = soup.find("meta", attrs={"name": "author"})
    author = authortag["content"]

    titletag = soup.find("meta", attrs={"property": "og:title"})
    title = titletag["content"]

    #print(author)
    #print(title)

    content = soup.select(".post_content .hentry")[0]

    images = []

    for img in content.find_all("img"):
        images.append(img["src"])

    #print(images)

    datestr = soup.select(".post_title_date .published")[0]["title"]
    date = parse(datestr)

    myjson = {
        "title": author,
        "author": author,
        "config": {
            "generator": "egloo"
        },
        "entries": [
            {
                "caption": title,
                "date": date,
                "author": author,
                "images": images,
                "videos": []
            }
        ]
    }

    print(ujson.dumps(myjson))
