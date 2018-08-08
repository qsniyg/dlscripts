import flickrapi
import pprint
import ujson
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import util
import re

api_key = util.tokens["flickr_key"]
api_secret = util.tokens["flickr_secret"]

targetusername = None

if len(sys.argv) > 1:
    targetusername = sys.argv[1]


flickr = flickrapi.FlickrAPI(api_key, api_secret, format='parsed-json')

if not flickr.token_valid(perms='read'):
    flickr.get_request_token(oauth_callback='oob')

    authorize_url = flickr.auth_url(perms='read')
    print(authorize_url)

    verifier = input('Verifier code: ')
    flickr.get_access_token(verifier)


list_opt = False
info_opt = False
if len(sys.argv) > 2:
    if sys.argv[2] == "list":
        list_opt = True
    elif sys.argv[2] == "info":
        info_opt = True

        match = re.search("/(?P<id>[^_/]*)_(?P<secret>[^_/]*)_[a-z]\.[^/]*$", sys.argv[1])
        if not match:
            sys.stderr.write("Valid URL?\n")
            exit()

        sys.stderr.write("ID: " + match.group("id") + ", secret: " + match.group("secret") + "\n")

        pprint.pprint(flickr.photos.getInfo(photo_id=match.group("id"), secret=match.group("secret")))
        exit()


rset = None
rsetname = None

if "@S:" in targetusername:
    splitted = targetusername.split("@S:")
    targetusername = splitted[0]
    rset = splitted[1]

if "@N" in targetusername:
    user = flickr.people.getInfo(user_id=targetusername)["person"]
else:
    user = flickr.people.findByUserName(username=targetusername)["user"]

userid = user["id"]
username = user["username"]["_content"]

if rset:
    rset_api = flickr.photosets.getInfo(user_id = userid,
                                        photoset_id = rset)
    rsetname = rset_api["photoset"]["title"]["_content"]

photos = []
page_i = 1

if list_opt:
    sys.stderr.write("Listing\n")

while True:
    if list_opt:
        photos_api = flickr.photosets.getList(user_id = userid,
                                              per_page = 500,
                                              page = page_i)["photosets"]
    else:
        if rset:
            photos_api = flickr.photosets.getPhotos(user_id = userid,
                                                    photoset_id = rset,
                                                    per_page = 500,
                                                    page = page_i,
                                                    extras = "original_format,date_upload,url_k,url_h,url_b,url_c,url_z,url_n,url_m,url_t")["photoset"]
        else:
            photos_api = flickr.people.getPublicPhotos(user_id = userid,
                                                       safe_search = 3,
                                                       per_page = 500,
                                                       page = page_i,
                                                       extras = "original_format,date_upload,url_k,url_h,url_b,url_c,url_z,url_n,url_m,url_t")["photos"]
            if not photos_api:
                break

    sys.stderr.write("\r" + str(page_i) + " / " + str(photos_api["pages"]))

    if list_opt:
        photos = photos + photos_api["photoset"]
    else:
        photos = photos + photos_api["photo"]

    page_i = page_i + 1
    if page_i > photos_api["pages"]:
        break

sys.stderr.write("\n" + str(len(photos)) + "\n")
#pprint.pprint(photos)
#exit()

myjson = {
    "title": username,
    "author": username,
    "config": {
        "generator": "flickr"
    },
    "entries": []
}

if list_opt:
    myjson["entries"] = photos
    print(ujson.dumps(myjson))
    exit()

def build_photo_url(photo):
    if "originalsecret" in photo:
        return "https://farm%i.staticflickr.com/%s/%s_%s_o.%s" % (
            photo["farm"],
            photo["server"],
            photo["id"],
            photo["originalsecret"],
            photo["originalformat"]
        )

    if "url_k" in photo:
        return photo["url_k"]
    if "url_h" in photo:
        return photo["url_h"]
    if "url_b" in photo:
        return photo["url_b"]
    if "url_c" in photo:
        return photo["url_c"]
    if "url_n" in photo:
        return photo["url_n"]
    if "url_m" in photo:
        return photo["url_m"]
    if "url_t" in photo:
        return photo["url_t"]

    return None

#photos = photos_api["photos"]["photo"]
for photo in photos:
    newcaption = str(photo["id"]) + " " + photo["title"]
    newcaption = newcaption.strip()
    myentry = {
        "caption": newcaption,
        "similarcaption": photo["title"],
        "date": int(photo["dateupload"]),
        "author": username,
        "images": [build_photo_url(photo)],
        "videos": [],
    }

    if myentry["images"][0] == None:
        sys.stderr.write("Skipping image " + photo["title"] + "\n")
        continue

    if rset:
        myentry["album"] = rsetname

    myjson["entries"].append(myentry)

print(ujson.dumps(myjson))
