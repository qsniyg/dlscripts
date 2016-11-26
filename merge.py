import ujson
import sys

if __name__ == "__main__":
    jsons = []

    for arg in sys.argv[1:]:
        sys.stderr.write("Loading " + arg + "... ")
        with open(arg) as f:
            jsons.append(ujson.load(f))
        sys.stderr.write("done\n")

    if len(jsons) <= 0:
        exit()

    feed = jsons[0]

    for feedi in jsons[1:]:
        feed["entries"].extend(feedi["entries"])

    print(ujson.dumps(feed))
