import bs4
import ujson
import sys
sys.path.append("..")
import util
import urllib.request
from dateutil.parser import parse
import googleapiclient.discovery
from oauth2client.client import GoogleCredentials
from pprint import pprint

api_key = util.tokens["blogger_key"]


if __name__ == "__main__":
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
