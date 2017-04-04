import bs4
import ujson
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import re
import html
import pprint

# for news1: http://news1.kr/search_front/search.php?query=[...]&collection=front_photo&startCount=[0,20,40,...]

quick = True

def download_real(url, *args, **kwargs):
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    request.add_header('Pragma', 'no-cache')
    request.add_header('Cache-Control', 'max-age=0')
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

    with urllib.request.urlopen(request, timeout=60) as response:
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


def get_title(myjson, soup):
    return html.unescape(soup.find("meta", attrs={"property": "og:title"})["content"])


def get_author(url):
    if "naver." in url:
        return "naver"
    if ".joins.com" in url:
        return "joins"
    if "news1.kr/" in url:
        return "news1"

    return None


def ascii_only(string):
    return ''.join([i if ord(i) < 128 else ' ' for i in string])


def parse_date(date):
    date = re.sub("오후 *([0-9]*:[0-9]*)", "\\1PM", date)
    date = ascii_only(date)
    date = re.sub("\( *\)", "", date)
    date = re.sub("^ *$", "", date)
    if not date:
        return None
    #sys.stderr.write(date + "\n")
    return parse(date)


def get_date(myjson, soup):
    datetag = get_selector(soup, [
        ".article_info .author em",
        ".article_tit .write_info .write"
    ])

    if not datetag:
        sys.stderr.write("no recognizable date\n")
        return

    date = None
    for date_tag in datetag:
        if myjson["author"] == "naver":
            if not "오후" in date_tag.text:
                continue
            date = parse(date_tag.text.replace("오후", ""))
        else:
            date = parse_date(date_tag.text)

    return date


def get_images(myjson, soup):
    imagestag = get_selector(soup, [
        "#adiContents img",
        ".article img",
        "#article img",
        ".articletext img",
        "#_article table[align='center'] img",
        "#_article img.view_photo",
        "#_article .article_photo img",
        "#articleBody img",
        "#articleBody .iframe_img img:nth-of-type(2)",
        "#newsContent .iframe_img img:nth-of-type(2)",
        "#articeBody .img_frame img",
        "#textBody img",
        "#news_contents img",
        "#arl_view_content img",
        ".articleImg img",
        "#newsViewArea img",
        "#articleContent img",
        "#articleContent #img img",
        "#newsContent img.article-photo-mtn",
        "#article_content img",
        "div[itemprop='articleBody'] img",
        "div[itemprop='articleBody'] img.news1_photo",
        "div[itemprop='articleBody'] div[rel='prettyPhoto'] img",
        "div[itemprop='articleBody'] .centerimg img",
        "div[itemprop='articleBody'] .center_image img",
        ".center_image > img",
        ".article_view img",
        "img#newsimg",
        ".article_photo img",
        ".articlePhoto img",
        "#__newsBody__ .he22 td > img",
        ".article_image > img",
        "#CmAdContent img",
        ".article_outer .main_image p > img, .article_outer .post_body p img",
        ".article-img img",
        ".portlet .thumbnail img",
        "#news_textArea img",
        ".news_imgbox img",
        ".view_txt img",
        "#IDContents img",
        "#view_con img",
        "#newsEndContents img",
        ".articleBox img",
        ".rns_text img",
        "#article_txt img",
        "#ndArtBody .imgframe img",
        ".view_box center img",
        ".newsbm_img_wrap > img",
        ".article .detail img",
        "#articeBody img"
    ])

    if not imagestag:
        return

    images = []
    for image in imagestag:
        images.append(get_max_quality(image["src"]))

    return images


def get_description(myjson, soup):
    desc_tag = get_selector(soup, [
        "#article_content #adiContents"
    ])

    if not desc_tag:
        return

    return "\n".join(list(desc_tag[0].strings))


def get_article_url(url):
    return url


def get_articles(myjson, soup):
    if myjson["author"] == "joins":
        if "isplusSearch" not in myjson["url"]:
            return
    elif myjson["author"] == "news1":
        if "search.php" not in myjson["url"]:
            return
    else:
        return

    articles = []

    parent_selectors = [
        # joins
        {
            "parent": "#news_list .bd ul li dl",
            "link": "dt a",
            "caption": "dt a",
            "date": "dt .date",
            "images": ".photo img",
            "description": "dd.s_read_cr"
        },
        {
            "parent": "#search_contents .bd ul li dl",
            "link": "dt a",
            "caption": "dt a",
            "date": ".date",
            "images": ".photo img"
        },
        # news1
        {
            "parent": ".search_detail ul li",
            "link": "a",
            "caption": "a > strong",
            "date": "a .date",
            "images": ".thumb img"
        }
    ]

    parenttag = None
    for selector in parent_selectors:
        parenttag = soup.select(selector["parent"])
        if parenttag and len(parenttag) > 0:
            #parenttag = parenttag[0]
            break

    if not parenttag:
        return []

    for a in parenttag:
        link = get_article_url(urllib.parse.urljoin(myjson["url"], a.select(selector["link"])[0]["href"]))

        date = 0
        if "date" in selector:
            for date_tag in a.select(selector["date"]):
                try:
                    date = parse_date(date_tag.text)
                    if date:
                        break
                except Exception as e:
                    pass

        caption = None
        if "caption" in selector:
            caption = a.select(selector["caption"])[0].text

        description = None
        if "description" in selector:
            description = a.select(selector["description"])[0].text

        author = get_author(link)

        images = []
        if "images" in selector:
            image_tags = a.select(selector["images"])
            for image in image_tags:
                images.append(get_max_quality(image["src"]))

        articles.append({
            "url": link,
            "date": date,
            "caption": caption,
            "description": description,
            "author": author,
            "images": images,
            "videos": []
        })

    return articles


def get_max_quality(url):
    if "naver." in url:
        url = re.sub("\?.*", "", url)
        #if "imgnews" not in url:
        # do blogfiles
    if ".joins.com" in url:
        url = re.sub("\.tn_.*", "", url)
    if "image.news1.kr" in url:
        url = re.sub("/[^/.]*\.([^/]*)$", "/original.\\1", url)
    return url


def do_url(url):
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    data = download(url)
    #data = download("file:///tmp/naver.html")

    soup = bs4.BeautifulSoup(data, 'lxml')

    myjson = {
        "title": None,
        "author": None,
        "url": url,
        "config": {
            "generator": "news"
        },
        "entries": []
    }

    author = get_author(url)

    if not author:
        sys.stderr.write("unknown site\n")
        return

    myjson["author"] = author
    myjson["title"] = author

    articles = get_articles(myjson, soup)
    if articles is not None:
        article_i = 1
        for article in articles:
            if article is None:
                sys.stderr.write("error with article\n")
                continue
            if quick:
                if not article["caption"] or article["date"] == 0:
                    sys.stderr.write("no salvageable information from search\n")
                    return

                if not article["author"]:
                    article["author"] = myjson["author"]
                elif article["author"] != myjson["author"]:
                    sys.stderr.write("different authors\n")
                    return

                myjson["entries"].append(article)
                continue
            article_url = article["url"]
            basetext = "(%i/%i) " % (article_i, len(articles))
            article_i += 1

            sys.stderr.write(basetext + "Downloading %s... " % article_url)
            sys.stderr.flush()

            newjson = None
            try:
                newjson = do_url(article_url)
            except Exception as e:
                pass
            if not newjson:
                sys.stderr.write("url: " + article_url + " is invalid\n")
                continue

            if newjson["author"] != myjson["author"]:
                sys.stderr.write("current:\n\n" +
                                 pprint.pformat(myjson) +
                                 "\n\nnew:\n\n" +
                                 pprint.pformat(newjson))
                continue

            sys.stderr.write("done\n")
            sys.stderr.flush()

            myjson["entries"].extend(newjson["entries"])
        return myjson

    title = get_title(myjson, soup)

    if not title:
        sys.stderr.write("no title\n")
        return

    date = get_date(myjson, soup)

    if not date:
        sys.stderr.write("no date\n")
        return

    album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + title

    images = get_images(myjson, soup)
    if not images:
        sys.stderr.write("no images\n")
        return

    description = get_description(myjson, soup)
    if not description:
        sys.stderr.write("no description\n")

    myjson["entries"].append({
        "caption": title,
        "description": description,
        "album": album,
        "url": url,
        "date": date,
        "author": author,
        "images": images,
        "videos": [] # for now
    })

    return myjson


def main():
    url = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "full":
        global quick
        quick = False
    myjson = do_url(url)
    print(ujson.dumps(myjson))


if __name__ == "__main__":
    main()
