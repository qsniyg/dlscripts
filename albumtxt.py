import ujson
import sys
import os

def fsify_base(text):
    return text.replace("\n", " ").replace("\r", " ").replace("/", "(slash)")

def fsify_album(text):
    return fsify_base(text)[:100].strip()

if len(sys.argv) < 2:
    print("Need output directory")
    exit()

myjson = sys.stdin.read()
sys.stdin.close()

jsond = ujson.loads(myjson)

for entry in jsond["entries"]:
    with open(os.path.join(sys.argv[1], fsify_album(entry["album"]) + ".txt"), "a", encoding="utf-8") as file:
        for image in entry["images"]:
            file.write(image + "\n")
