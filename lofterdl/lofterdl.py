import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import re


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


def processdata(author, soup, url):
    postid = re.sub(".*/post/.*_(.*)$", "\\1", url)

    titletag = soup.select("title")[0]
    title = titletag.text
    title = re.sub("- *" + author + " *$", "", title)

    newtitle = postid + " " + title

    datestr = soup.select("a.date")[0].text
    date = parse(datestr)

    album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title

    content = soup.select(".ct > .ctc.box")[0]

    images = []

    for img in content.find_all("img"):
        images.append(re.sub("\?.*", "", img["src"]))

    return {
        "caption": newtitle,
        "similarcaption": title,
        "date": date,
        "album": album,
        "author": author,
        "images": images,
        "videos": []
    }


if __name__ == "__main__":
    url = sys.argv[1]

    data = download(url)
    soup = bs4.BeautifulSoup(data, 'lxml')

    authortag = soup.select(".m-cprt > a")[0]
    author = authortag.text

    myjson = {
        "title": author,
        "author": author,
        "config": {
            "generator": "lofter"
        },
        "entries": []
    }

    posts = soup.select(".m-postlst .m-post")
    if len(posts) > 0:
        i = 1
        for post in posts:
            link = post.select("a")[0]["href"]
            sys.stderr.write("(" + str(i) + "/" + str(len(posts)) + ") Downloading " + link + " ... ")
            sys.stderr.flush()

            newdata = download(link)
            newsoup = bs4.BeautifulSoup(newdata, 'lxml')

            sys.stderr.write("done\n")
            sys.stderr.flush()

            myjson["entries"].append(processdata(author, newsoup, link))

            i += 1
    else:
        myjson["entries"].append(processdata(author, soup, url))

    print(ujson.dumps(myjson))
