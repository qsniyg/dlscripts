#!/bin/sh

USER="$1"

cd "`dirname "$0"`"

shift
ARGS="$@"

if [ ! -e "$USER"_list.json ]; then
    echo "No list for $USER .. will download (press ENTER)"
    read
    python flickrdl.py "$USER" list > "$USER"_list.json
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

cat "$USER"_list.json | jq -r '.entries[] | (.id | tostring) + "###" + (.photos | tostring)' | while read line
do
    NUM=`echo "$line" | sed 's:.*###::g'`
    if [ $NUM -le 0 ]; then
        continue
    fi

    ID=`echo "$line" | sed 's:###.*::g'`
    #echo "$ID"

    if [ ! -e "$USER""@S:""$ID".json ]; then
        #echo "Set $ID exists"
        python flickrdl.py "$USER""@S:""$ID" > "$USER""@S:""$ID".json
        if [ $? -ne 0 ]; then
            exit 2
        fi
    fi

    cat "$USER""@S:""$ID".json | python ../download.py $ARGS
done
