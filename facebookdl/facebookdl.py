import facebook
import requests
import pprint
import sys
sys.path.append("..")
import util
from dateutil.parser import parse
import ujson


# https://developers.facebook.com/tools/explorer/
access_token = util.tokens["facebook_access"]

user = 'Eunjunghk'

if len(sys.argv) > 1:
    user = sys.argv[1]

graph = facebook.GraphAPI(access_token)
profile = graph.get_object(user)
albums = graph.get_connections(profile['id'], 'albums?limit=100')

#pprint.pprint(profile)

myjson = {
    "title": profile["username"],
    "author": profile["username"],
    "config": {
        "generator": "facebook"
    },
    "entries": []
}

all_albums = []

pagecnt = 0

#exit()
while True:
    try:
        sys.stderr.write("\rAlbums page " + str(pagecnt))
        pagecnt = pagecnt + 1

        all_albums = all_albums + albums["data"]
        albums = requests.get(albums['paging']['next']).json()
    except KeyError:
        break

sys.stderr.write("\n")

#pprint.pprint(all_albums)

for album in all_albums:
    all_photos = []

    albumname = album["name"]
    albumdate = parse(album["created_time"])
    albumdatestr = str(albumdate.year)[-2:] + str(albumdate.month).zfill(2) + str(albumdate.day).zfill(2)
    albumdatestr += ":"
    albumdatestr += str(albumdate.hour).zfill(2) + str(albumdate.minute).zfill(2) + str(albumdate.second).zfill(2)
    newalbumname = "(" + albumdatestr + ") " + albumname

    try:
        photos = graph.get_connections(album["id"], "photos?limit=100")
    except facebook.GraphAPIError as e:
        sys.stderr.write("Skipping " + albumname + " (" + album["id"] + ") " + str(e) + "\n")
        continue

    pagecnt = 0

    while True:
        try:
            sys.stderr.write("\rPage " + str(pagecnt) + " for album " + albumname)
            pagecnt = pagecnt + 1

            all_photos = all_photos + photos["data"]
            photos = requests.get(photos["paging"]["next"]).json()
        except KeyError:
            break

    sys.stderr.write("\n")

    unnamed_ids = {}

    for photo in all_photos:
        date = parse(photo["updated_time"])

        image = photo["images"][0]["source"]

        if "name" in photo:
            caption = photo["name"]
        else:
            if photo["updated_time"] in unnamed_ids:
                unnamed_id = unnamed_ids[photo["updated_time"]]
            else:
                unnamed_ids[photo["updated_time"]] = 0
                unnamed_id = 0

            caption = "unnamed " + str(unnamed_id)

            unnamed_ids[photo["updated_time"]] += 1

        myjson["entries"].append({
            "caption": caption,
            "date": date,
            "album": newalbumname,
            "author": profile["username"],
            "images": [image],
            "videos": []
        })

print(ujson.dumps(myjson))
