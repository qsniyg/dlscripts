import bs4
import ujson
import sys
import urllib.request
from dateutil.parser import parse
import re
import html


def download_real(url, *args, **kwargs):
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


def download(url):
    return re.sub(r"^.*?<html", "<html", download_real(url), flags=re.S)


if __name__ == "__main__":
    url = sys.argv[1]

    #data = re.sub(r"^.*?<html", "<html", download(url), flags=re.S)
    #data = download(url)
    #data = download("file:///tmp/tistory.html")

    #soup = bs4.BeautifulSoup(data, 'lxml')

    articles = []
    if "/tag/" in url or "/search/" in url or "/category/" in url:
        sys.stderr.write("Listing... ")
        data = download(url)
        soup = bs4.BeautifulSoup(data, 'lxml')

        parent_selectors = [
            "#searchList li a",
            ".searchList ol li a",
            ".list_box li > a",
            "ol.article_post li a",
            "#content #s_list #masonry ul li.box > a",
            "#content .entry_slist ol li > a",
            "#content #content-inner .list ul li > a"
        ]

        parenttag = None
        for selector in parent_selectors:
            parenttag = soup.select(selector)
            if parenttag and len(parenttag) > 0:
                #parenttag = parenttag[0]
                break

        for a in parenttag:
            articles.append(urllib.parse.urljoin(url, a["href"]))

        sys.stderr.write("done\n")
    else:
        articles = [url]

    myjson = {
        "title": None,
        "author": None,
        "config": {
            "generator": "tistory"
        },
        "entries": []
    }

    article_i = 1
    for article_url in articles:
        basetext = "(%i/%i) " % (article_i, len(articles))
        article_i += 1

        sys.stderr.write(basetext + "Downloading %s... " % article_url)
        sys.stderr.flush()
        try:
            data = download(article_url)
        except:
            sys.stderr.write("failed!\n")
            sys.stderr.flush()
            continue

        sys.stderr.write("\r" + basetext + "Processing  %s... " % article_url)
        sys.stderr.flush()

        soup = bs4.BeautifulSoup(data, 'lxml')

        jsondata = soup.find(attrs={"type": "application/ld+json"}).text
        jsondecode = ujson.loads(jsondata)

        sitetitle = html.unescape(soup.find("meta", attrs={"property": "og:site_name"})["content"])
        myjson["title"] = sitetitle
        myjson["author"] = sitetitle
        #author = html.unescape(jsondecode["author"]["name"])
        author = sitetitle
        title = html.unescape(jsondecode["headline"])
        #title = html.unescape(soup.find("meta", attrs={"property": "og:title"})["content"])
        date = parse(jsondecode["datePublished"])
        album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title

        article_selectors = [
            ".entry .article",
            ".article_post",
            "#content",
            "#mArticle"
        ]

        for selector in article_selectors:
            articletag = soup.select(selector)
            if articletag and len(articletag) > 0:
                articletag = articletag[0]
                break

        #articletag = soup.select(".entry .article")
        #if articletag and len(articletag) > 0:
        #    articletag = articletag[0]
        #else:
        #    articletag = soup.select(".article_post")
        #    if articletag and len(articletag) > 0:
        #        articletag = articletag[0]
        #    else:
        #        articletag = soup.select("#content")[0]

        lightboxes = articletag.findAll(attrs={"data-lightbox": True})
        images = []

        for lightbox in lightboxes:
            images.append(lightbox["data-url"].replace("/image/", "/original/").replace("/attach/", "/original/"))
            #images.append(re.sub("/image/", "/original/", lightbox["data-url"]))

        imageblocks = articletag.select(".imageblock img")

        for image in imageblocks:
            if "onclick" in image:
                url = re.sub("^open_img\(['\"](.*)['\"]\)$", "\\1", image["onclick"])

            url = re.sub("/image/", "/original/", image["src"])

            if url not in images:
                images.append(url)

        myjson["entries"].append({
            "caption": title,
            "album": album,
            "date": date,
            "author": author,
            "images": images,
            "videos": []
        })

        sys.stderr.write("done\n")
        sys.stderr.flush()

        #myjson = {
        #    "title": sitetitle,
        #    "author": sitetitle,
        #    "config": {
        #        "generator": "tistory"
        #    },
        #    "entries": [
        #        {
        #            "caption": title,
        #            "album": album,
        #            "date": date,
        #            "author": author,
        #            "images": images,
        #            "videos": []
        #        }
        #    ]
        #}

    print(ujson.dumps(myjson))
