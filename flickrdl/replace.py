import sys
import re
import ujson

if len(sys.argv) < 3:
    sys.stderr.write("replace.py base better > new\n")
    exit()

error_opt = False
if len(sys.argv) > 3 and sys.argv[1] == "error":
    error_opt = True
    del(sys.argv[1])


def get_id(image):
    match = re.search(".*flickr\.com.*/(?P<id>[^_/]*)_(?P<secret>[^_/]*)_[a-z]\.[^/]*$", image)
    if not match:
        # not flickr
        return None
    return match.group("id")


sys.stderr.write("Loading base file " + sys.argv[1] + "... ")
with open(sys.argv[1]) as f:
    base_file = ujson.load(f)
sys.stderr.write("done\n")

argc = 2
better_files = []
while argc < len(sys.argv):
    sys.stderr.write("Loading better file " + sys.argv[argc] + "... ")
    with open(sys.argv[argc]) as f:
        better_files.append(ujson.load(f))
    sys.stderr.write("done\n")
    argc += 1

better_index = {}
sys.stderr.write("Indexing better files... ")
bt = 0
for better_file in better_files:
    for entry in better_file["entries"]:
        for image in entry["images"]:
            bt += 1

            id = get_id(image)
            if not id:
                continue

            better_index[id] = image

bi = len(better_index)
bp = (bi / bt) * 100
sys.stderr.write("done (%i/%i, %i%%)\n" % (bi, bt, bp))

sys.stderr.write("Replacing... ")
replaced = 0
ol = 0
nf = []
ni = []

for entry_i in range(len(base_file["entries"])):
    entry = base_file["entries"][entry_i]
    for image_i in range(len(entry["images"])):
        ol += 1
        image = entry["images"][image_i]

        id = get_id(image)
        if id == None:
            nf.append(image)
            continue

        if id not in better_index:
            ni.append(image)
            continue

        entry["images"][image_i] = better_index[id]
        replaced += 1
    base_file["entries"][entry_i] = entry

rp = (replaced / ol) * 100
sys.stderr.write("done (%i/%i, %i%% | NF: %i | NI: %i)\n" % (replaced, ol, rp, len(nf), len(ni)))

if error_opt:
    for image in ni:
        print(image)
else:
    print(ujson.dumps(base_file))
