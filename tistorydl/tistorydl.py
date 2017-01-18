import bs4
import ujson
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import re
import html

page_url = None

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


def get_full_image(img):
    return urllib.parse.urljoin(page_url, img.replace("/image/", "/original/").replace("/attach/", "/original/").replace("/media/", "/original/"))


if __name__ == "__main__":
    url = sys.argv[1]
    page_url = url

    #data = re.sub(r"^.*?<html", "<html", download(url), flags=re.S)
    #data = download(url)
    #data = download("file:///tmp/tistory.html")

    #soup = bs4.BeautifulSoup(data, 'lxml')

    articles = []
    if "/tag" in url or "/search" in url or "/category" in url or url.endswith("tistory.com") or url.endswith("tistory.com/"):
        sys.stderr.write("Listing... ")
        data = download(url)
        soup = bs4.BeautifulSoup(data, 'lxml')

        parent_selectors = [
            "#searchList li a",
            ".searchList ol li a",
            ".list_box li > a",
            "ol.article_post li a",
            "#masonry ul li.box > a",
            "#content .entry_slist ol li > a",
            "#content #content-inner .list ul li > a",
            "#result li > a",
            "ul.list_search li > a",
            ".list_wrap div.article_skin div.list_content a",
            ".gallery_ul li.grid-item > a",
            "section div.fixed_img_col ul li > a"
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
            "#mArticle",
            "#article"
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

        images = []
        videos = []

        articlestr = str(articletag)
        re_images = re.findall("(https?://cfile\d+\.uf\.tistory\.com/(image|attach|original)/\w+)", articlestr)

        for image in re_images:
            url = get_full_image(image[0])

            if url not in images:
                images.append(url)

        #re_videos = re.findall("https?://cfile\d+\.uf\.tistory\.com/media/\w+", articlestr)

        #for video in re_videos:
        #    url = get_full_image(video)

        #    if url not in videos:
        #        videos.append({
        #            "image": None,
        #            "video": url
        #        })

        lightboxes = articletag.findAll(attrs={"data-lightbox": True})


        for lightbox in lightboxes:
            image = get_full_image(lightbox["data-url"])
            if image not in images:
                images.append(image)
            #images.append(re.sub("/image/", "/original/", lightbox["data-url"]))

        #imageblocks = articletag.select(".imageblock img")
        imageblocks = articletag.select("p img, .imageblock img")

        for image in imageblocks:
            if "onclick" in image:
                url = re.sub("^open_img\(['\"](.*)['\"]\)$", "\\1", image["onclick"])

            url = image["src"]

            url = get_full_image(url)

            if url not in images:
                images.append(url)

        videotags = articletag.select("video")

        for video in videotags:
            if video.has_attr("src"):
                url = video["src"]
            else:
                sources = video.select("source")
                if len(sources) > 0:
                    url = sources[0]["src"]
                else:
                    continue

            videos.append({
                "image": None,
                "video": get_full_image(url)
            })

        myjson["entries"].append({
            "caption": title,
            "album": album,
            "date": date,
            "author": author,
            "images": images,
            "videos": videos
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
