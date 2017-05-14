import bs4
import ujson
import demjson
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import util
import urllib.request
from dateutil.parser import parse
import googleapiclient.discovery
from oauth2client.client import GoogleCredentials
from pprint import pprint
import re

api_key = util.tokens["blogger_key"]

once = False


def getmyjson(blogname):
    return {
        "title": blogname,
        "author": blogname,
        "config": {
            "generator": "blogger"
        },

        "entries": []
    }


def get_selector(soup, selectors):
    tag = None

    for selector in selectors:
        tag = soup.select(selector)
        if tag and len(tag) > 0:
            break
        else:
            tag = None

    return tag


def parse_entry(info, content):
    images = []

    imagetag = get_selector(content, [
        ".separator a img",
        "img"
    ])

    if not imagetag:
        return None

    parent = None
    for img in imagetag:
        if not img.has_attr("src"):
            continue
        if "blogspot" in img["src"]:
            parent = img.parent
            for parent_i in img.parents:
                if parent_i and parent_i.name == "a":
                    parent = parent_i
                    break

            images.append(parent["href"])
        else:
            images.append(img["src"])

    author = info["author"]
    date = info["date"]
    caption = info["caption"]
    album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + caption

    return {
        "caption": caption,
        "album": album,
        "author": author,
        "date": date,
        "images": images,
        "videos": []
    }


def html_getjson(data):
    jsondatare = re.search(r"_WidgetManager._SetDataContext\( *(?P<json>.*?) *\);\n", str(data))
    if jsondatare is None:
        return None

    #jsondata = bytes(jsondatare.group("json"), 'utf-8').decode('unicode-escape')
    #jsondata = bytes(jsondatare.group("json"), 'utf-8').decode('utf-8')
    jsondata = str(jsondatare.group("json"))
    #decoded = ujson.loads(jsondata)
    decoded = demjson.decode(jsondata)

    return decoded


def getblogname_api(blog):
    return blog["name"]


def getblogname_html(jsondata):
    return jsondata[0]["data"]["title"]


def getpostinfo_api(blog, post):
    return {
        "caption": post["title"],
        "date": parse(post["published"]),
        "author": getblogname_api(blog)
    }


def getpostinfo_html(soup, jsondata):
    date = parse(soup.select("abbr[itemprop='datePublished']")[0]["title"])
    #author = soup.select("*[itemprop='author'] *[itemprop='name']")[0].text
    return {
        "caption": jsondata[0]["data"]["pageName"],
        "date": date,
        "author": getblogname_html(jsondata)
    }


def exec_api(url):
    service = googleapiclient.discovery.build('blogger', 'v3',
                                              developerKey=api_key)

    blogsapi = service.blogs()
    blog = blogsapi.getByUrl(url=url, view="READER").execute()

    postsapi = service.posts()

    myjson = getmyjson(getblogname_api(blog))

    posts_req = postsapi.list(blogId=blog["id"], maxResults=500)

    while posts_req is not None:
        posts = posts_req.execute()

        for post in posts["items"]:
            content = bs4.BeautifulSoup(post["content"], 'lxml')
            entry = parse_entry(getpostinfo_api(blog, post), content)
            if entry:
                myjson["entries"].append(entry)

        sys.stderr.write("\r" + str(len(myjson["entries"])) + " / " + str(blog["posts"]["totalItems"]))

        if once:
            break

        posts_req = postsapi.list_next(posts_req, posts)

    sys.stderr.write("\n")

    return myjson


def exec_html(url):
    data = util.download(url)
    jsondata = html_getjson(data)
    blogname = getblogname_html(jsondata)

    soup = bs4.BeautifulSoup(data, 'lxml')
    postbody = soup.select(".entry-content")[0]

    myjson = getmyjson(blogname)
    entry = parse_entry(getpostinfo_html(soup, jsondata), postbody)
    if entry:
        myjson["entries"].append(entry)

    return myjson


if __name__ == "__main__":
    url = sys.argv[1]

    once = False
    if len(sys.argv) > 2 and sys.argv[2] == "once":
        once = True

    if url.endswith(".html"):
        print(ujson.dumps(exec_html(url)))
    else:
        print(ujson.dumps(exec_api(url)))


if __name__ == "__main__" and False:
    url = sys.argv[1]

    once = False
    if len(sys.argv) > 2 and sys.argv[2] == "once":
        once = True

    service = googleapiclient.discovery.build('blogger', 'v3',
                                              developerKey=api_key)

    blogsapi = service.blogs()
    blog = blogsapi.getByUrl(url=url, view="READER").execute()

    #pprint(blog)

    postsapi = service.posts()

    myjson = {
        "title": blog["name"],
        "author": blog["name"],
        "config": {
            "generator": "blogger"
        },

        "entries": []
    }

    posts_req = postsapi.list(blogId = blog["id"], maxResults = 500)

    while posts_req is not None:
        posts = posts_req.execute()

        for post in posts["items"]:
            caption = post["title"]
            date = parse(post["published"])
            album = "[" + str(date.year)[-2:] + str(date.month).zfill(2) + str(date.day).zfill(2) + "] " + caption
            author = post["author"]["displayName"]

            content = bs4.BeautifulSoup(post["content"], 'lxml')

            images = []

            for img in content.select(".separator a img"):
                parent = img.parent
                for parent_i in img.parents:
                    if parent_i and parent_i.name == "a":
                        parent = parent_i
                        break

                images.append(parent["href"])

            myjson["entries"].append({
                "caption": caption,
                "album": album,
                #"author": author,
                "author": blog["name"],
                "date": date,
                "images": images,
                "videos": []
            })

        sys.stderr.write("\r" + str(len(myjson["entries"])) + " / " + str(blog["posts"]["totalItems"]))

        if once:
            break
        #posts_req = None
        posts_req = postsapi.list_next(posts_req, posts)

    sys.stderr.write("\n")
    print(ujson.dumps(myjson))
    exit()

    #data = download(url)

    soup = bs4.BeautifulSoup(data, 'lxml')

    #authortag = soup.find("meta", attrs={"name": "author"})
    #author = authortag["content"]

    titletag = soup.find("meta", attrs={"property": "og:title"})
    title = titletag["content"]

    #print(author)
    #print(title)

    #content = soup.select(".post_content .hentry")[0]
    content = soup.select(".post-body.entry-content")[0]

    images = []

    for img in content.select(".separator a img"):
        images.append(img.parent["href"])

    #print(images)

    datestr = soup.select(".timestamp-link .published")[0]["title"]
    date = parse(datestr)

    myjson = {
        "title": title,
        "author": author,
        "config": {
            "generator": "blogger"
        },
        "entries": [
            {
                "caption": title,
                "album": title,
                "date": date,
                "author": author,
                "images": images,
                "videos": []
            }
        ]
    }

    print(ujson.dumps(myjson))
