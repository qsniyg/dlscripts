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

    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset()

        if charset:
            return response.read().decode(charset)
        else:
            return response.read()


if __name__ == "__main__":
    url = sys.argv[1]

    no_retweet = False
    if len(sys.argv) > 2 and sys.argv[2] == "no_retweet":
        no_retweet = True

    data = download(url)
    #data = download("file:///tmp/weibo.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    username = soup.select("h3.username")[0].text
    #description = soup.select("div.info .glyphicon-user")[0].parent.text

    statuses = soup.select(".weibos > .status")

    myjson = {
        "title": username,
        "author": username,
        "config": {
            "generator": "weibo"
        },
        "entries": []
    }

    for status in statuses:
        block = status.select("blockquote .status")
        if block and len(block) > 0:
            if no_retweet:
                continue
            status = block[0]

        lotspic = status.select(".lotspic_list")
        if not lotspic or len(lotspic) < 1:
            lotspic = status.select(".thumbs")
            if not lotspic or len(lotspic) < 1:
                continue

        status_word = status.select(".status_word")
        if not status_word or len(status_word) < 1:
            caption = ""
        else:
            caption = get_string(status_word[0])

        dateel = status.select("small span a")[0]
        datetext = dateel["title"]

        author = status.select(".screen_name")[0].text

        try:
            date = parse(datetext)
        except Exception as e:
            if "小时前" in datetext:
                hoursago = int(datetext.replace("小时前", ""))
                date = datetime.datetime.now() - datetime.timedelta(hours=hoursago)
            elif "分钟前" in datetext:
                minutesago = int(datetext.replace("分钟前", ""))
                date = datetime.datetime.now() - datetime.timedelta(minutes=minutesago)
            else:
                continue

        images = []
        for pic in lotspic[0].select("img"):
            if pic.has_attr("data-rel"):
                images.append(pic["data-rel"])
            else:
                images.append(re.sub(r"(//[^/]*\.cn/)[a-z]*/", "\\1large/", pic["src"]))

        myjson["entries"].append({
            "caption": caption,
            "date": date,
            "author": author,
            "images": images,
            "videos": []
        })

    print(ujson.dumps(myjson))
