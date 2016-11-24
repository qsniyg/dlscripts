import vk
import pprint
import sys
import functools
import ujson
import xml.sax.saxutils

session = vk.Session()
api = vk.API(session)

username = 'tara_qri'
if len(sys.argv) > 1:
    username = sys.argv[1]

user_info = api.groups.getById(group_id=username)


def paginate(t, f):
    all_ = []

    offset = 0
    page = 0

    while True:
        sys.stderr.write("\r" + t + " (%i, %i)" % (offset, page))
        curr = f(offset)

        all_ = all_ + curr

        if len(curr) <= 0:
            sys.stderr.write("\n")
            return all_

        offset = len(all_)
        page += 1


def photo_sort(a, b):
    if not a.startswith("src"):
        if not b.startswith("src"):
            return -1
        else:
            return -1

    if not b.startswith("src"):
        return 1

    if a == b:
        return 0

    if a == "src":
        return -1

    if b == "src":
        return 1

    if a == "src_small":
        return -1

    if b == "src_small":
        return 1

    if a == "src_big":
        return -1

    if b == "src_big":
        return 1

    counta = a.count("x")
    countb = b.count("x")

    if counta > countb:
        return 1
    elif counta == countb:
        return 0
    elif counta < countb:
        return -1

    return 0


def get_max_photo(d):
    #print(list(d.keys()))
    #print(sorted(list(d.keys()), key=functools.cmp_to_key(photo_sort)))
    max_photo_key = sorted(d.keys(), key=functools.cmp_to_key(photo_sort))[-1]
    return d[max_photo_key]

uid = str(-int(user_info[0]['gid']))
all_albums = paginate("Album list", lambda x: api.photos.getAlbums(owner_id=uid, count=1000, offset=x))
#all_photos = paginate("Photo list", lambda x: api.photos.get(owner_id=uid, count=1000, offset=x, album_id="wall"))

#albums = api.photos.getAlbums(owner_id=str(-int(user_info[0]['gid'])), count=1000)
#all_photos = api.photos.get(owner_id=uid, count=1000, album_id="wall")

myjson = {
    "title": user_info[0]["screen_name"],
    "author": user_info[0]["screen_name"],
    "config": {
        "generator": "vk"
    },
    "entries": []
}

albumi = 0
for album in all_albums:
    albumi += 1

    albumname = xml.sax.saxutils.unescape(album["title"])
    photos = paginate("(%i/%i) " % (albumi, len(all_albums)) + albumname, lambda x: api.photos.get(owner_id=uid, count=1000, offset=x, album_id=album["aid"]))
    for photo in photos:
        caption = xml.sax.saxutils.unescape(photo["text"])
        if not caption or len(caption) <= 0:
            caption = str(photo["pid"])

        myjson["entries"].append({
            "caption": caption,
            "date": photo["created"],
            "images": [get_max_photo(photo)],
            "videos": [],
            "album": albumname
        })

print(ujson.dumps(myjson))
#for photo in all_photos:
    #print(get_max_photo(photo))
