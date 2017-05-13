import json
import sys

if __name__ == "__main__":
    myjson = sys.stdin.read()
    sys.stdin.close()

    jsond = json.loads(myjson)

    author = None
    if "username" in jsond[0]:
        author = jsond[0]["username"]
    else:
        author = jsond[0]["user"]["username"]

    if not author:
        sys.stderr.write("no author\n")

    newjson = {
        "author": author,
        "config": {
            "generator": "instagram"
        },
        "entries": []
    }

    for entry in jsond:
        videos = []

        if "images" in entry:
            image = entry["images"][0]["url"]
            images = [image]
        else:
            image = entry["image_versions2"]["candidates"][0]["url"]
            images = [image]

        if "is_video" in entry:
            if entry["is_video"]:
                videos = [{
                    "image": image,
                    "video": entry["videos"][0]["url"]
                }]
                images = []
        else:
            if entry["video_versions"]:
                videos = [{
                    "image": image,
                    "video": entry["video_versions"][0]["url"]
                }]
                images = []

        caption = entry["caption"]
        if type(caption) == dict:
            caption = caption["text"]

        newjson["entries"].append({
            "author": author,
            "caption": caption,
            "date": entry["taken_at"],
            "images": images,
            "videos": videos
        })

    print(json.dumps(newjson))
