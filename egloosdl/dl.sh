#!/bin/sh

ID=`echo "$@" | sed 's:.*/\([^/]*\)$:\1:g'`
NAME=`echo "$@" | sed 's:[^/]*/*\([^/]*\)\.egloos.*:\1:g'`

jsonfile="$NAME"_"$ID".json
python egloosdl.py "$@" > "$jsonfile" && echo "$jsonfile"
