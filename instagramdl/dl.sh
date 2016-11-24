#!/bin/sh
cat "$@" |\
    jq -r '
(. | length) as $array_length |
0 as $i |
to_entries | .[] | [
  (
    (if .value.is_photo
     then
       .value.image
     else
       .value.videos[0]
     end) | .url
  ),
  ((if (.value.caption | length) == 0
  then
    ""
  else
    " " + .value.caption
  end) | gsub("\n"; " ") | gsub("\""; "") | gsub("/"; " (slash) "))[:50],
  .value.taken_at,
  (.key + 1 | tostring) + "/" + ($array_length | tostring)
] |
"echo \"" + .[3] + "\";wget -q --show-progress " + (.[0] | tojson) + " -O " + ("(" + (.[2] | todate) + ")" + .[1] + "." + (.[0] | match("[^?]*\\.([^?/]*)")["captures"][0]["string"]) | tojson)' |\
    while read line;
    do
        #echo "$line"
        eval "$line"
    done
#cat "$@" | jq '.[] | [((if .is_photo then .image else .videos[0] end) | .url), .caption, .taken_at]' | while read line
#do
#    echo "$line"
#done
