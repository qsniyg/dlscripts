from imgurpython import ImgurClient
import pprint
import sys
import os
import ujson
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import util

client_id = util.tokens["imgur_id"]
client_secret = util.tokens["imgur_secret"]

client = ImgurClient(client_id, client_secret)

username = "b940722"
if len(sys.argv) > 1:
    username = sys.argv[1]

get_images = False
get_album = False
if len(sys.argv) > 2:
    if sys.argv[2] == "images":
        get_images = True
    elif sys.argv[2] == "album":
        get_album = True
    elif sys.argv[2] == "credits":
        sys.stderr.write(pprint.pformat(client.__dict__) + "\n")
        exit()

def paginate(t, f):
    all_ = []

    offset = 0
    page = 0

    while True:
        sys.stderr.write("\r" + t + " (%i, %i)" % (offset, page))
        curr = f(page)

        all_ = all_ + curr

        if len(curr) <= 0:
            sys.stderr.write("\n")
            return all_

        offset = len(all_)
        page += 1


def parse_image(image, albumname):
    if image.title:
        caption = image.title
    else:
        caption = image.id

    images = [image.link]
    videos = []
    if image.animated and image.type == "image/gif" and image.size >= 20*1024*1024 and image.hasattr("mp4"):
        videos = [image.mp4]

    if albumname:
        return {
            "caption": caption,
            "date": image.datetime,
            "images": images,
            "videos": videos,
            "album": albumname
        }
    else:
        return {
            "caption": caption,
            "date": image.datetime,
            "images": images,
            "videos": videos
        }

if get_album:
    album_name = username
    album = client.get_album(username)

    username = album.account_url

    myjson = {
        "title": username,
        "author": username,
        "config": {
            "generator": "imgur"
        },
        "entries": []
    }

    albumname = album.title

    text = albumname

    sys.stderr.write("\rFetching " + text)
    images = client.get_album_images(album.id)

    sys.stderr.write("\rParsing " + text + "  \r")
    for image in images:
        myjson["entries"].append(parse_image(image, albumname))

    sys.stderr.write("\rDone " + text + "      \n")
    print(ujson.dumps(myjson))
    exit()

myjson = {
    "title": username,
    "author": username,
    "config": {
        "generator": "imgur"
    },
    "entries": []
}

if get_images:
    all_images = paginate("Images", lambda x: client.get_account_images(username, page=x))
    for image in all_images:
        myjson["entries"].append(parse_image(image, None))
    print(ujson.dumps(myjson))
    exit()


all_albums = paginate("Albums", lambda x: client.get_account_albums(username, page=x))

albumi = 0
for album in all_albums:
    albumi += 1
    albumname = album.title

    text = albumname + " (%i/%i)" % (albumi, len(all_albums))

    sys.stderr.write("\rFetching " + text)
    images = client.get_album_images(album.id)

    sys.stderr.write("\rParsing " + text + "  \r")
    for image in images:
        myjson["entries"].append(parse_image(image, albumname))

    sys.stderr.write("\rDone " + text + "      \n")

print(ujson.dumps(myjson))
