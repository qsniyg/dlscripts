import json
import sys

if __name__ == "__main__":
    myjson = sys.stdin.read()
    sys.stdin.close()

    jsond = json.loads(myjson)

    newjson = {
        "author": jsond[0]["username"],
        "config": {
            "generator": "instagram"
        },
        "entries": []
    }

    for entry in jsond:
        videos = []

        image = entry["images"][0]["url"]
        images = [image]

        if entry["is_video"]:
            videos = [{
                "image": image,
                "video": entry["videos"][0]["url"]
            }]
            images = []

        newjson["entries"].append({
            "author": entry["username"],
            "caption": entry["caption"],
            "date": entry["taken_at"],
            "images": images,
            "videos": videos
        })

    print(json.dumps(newjson))
