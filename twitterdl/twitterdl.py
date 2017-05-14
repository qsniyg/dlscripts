import tweepy
import pprint
import re
import os
import json
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import util
from calendar import timegm

try:
    from rfc822 import parsedate
except ImportError:
    from email.utils import parsedate


auth = tweepy.OAuthHandler(util.tokens["twitter_key"],
                           util.tokens["twitter_secret"])
auth.set_access_token(util.tokens["twitter_access_key"],
                      util.tokens["twitter_access_secret"])

#try:
#    redirect_url = auth.get_authorization_url()
#except tweepy.TweepError:
#    print('Error! Failed to get request token.')

#print(redirect_url)

username="tiara_pics"

if len(sys.argv) > 1:
    username = sys.argv[1]

once = False
if len(sys.argv) > 2 and sys.argv[2] == "once":
    once = True

api = tweepy.API(auth)

user_info = api.get_user(id=username)
#pprint.pprint(user_info.__dict__)
#exit()

all_tl = []
maxid = None

while True:
    tl = api.user_timeline(id=username, max_id=maxid, count=200)
    if not tl:
        break;

    all_tl = all_tl + tl
    maxid = tl[-1].id - 1

    sys.stderr.write("\r" + str(len(all_tl)) + " / " + str(user_info.statuses_count))

    if once:
        break

sys.stderr.write("\n")

myjson = {
    "title": user_info.screen_name,
    "author": user_info.screen_name,
    "config": {
        "generator": "twitter"
    },
    "entries": []
}

for obj in all_tl:
    caption = re.sub(" *http[^ ]*t\.co/[^ ]*", "", obj.text)
    #date = obj.created_at.timestamp()
    date = timegm(parsedate(obj._json["created_at"]))

    entrydict = {
        "caption": caption,
        "date": date,
        "author": obj.author.screen_name,
        "images": [],
        "videos": []
    }

    #pprint.pprint(obj.__dict__)

    if not "extended_entities" in obj.__dict__:
        continue

    for media in obj.__dict__["extended_entities"]["media"]:
        if media["type"] == "photo":
            #url = media["media_url"]
            #if not url.endswith(":large"):
            #    url += ":large"
            #entrydict["images"].append(url)
            url = media["media_url"]
            if url.endswith(":large"):
                url = url.replace(":large", ":orig")
            elif not url.endswith(":orig"):
                url += ":orig"
            entrydict["images"].append(url)
        elif media["type"] == "video" or media["type"] == "animated_gif":
            videodict = {
                "image": media["media_url"]
            }

            variants = media["video_info"]["variants"]

            max_bitrate = -1
            curr = None
            for variant in variants:
                if "bitrate" in variant and variant["bitrate"] > max_bitrate:
                    curr = variant

            if not curr:
                curr = variants[0]

            videodict["video"] = curr["url"]
            entrydict["videos"].append(videodict)

    myjson["entries"].append(entrydict)

print(json.dumps(myjson))
