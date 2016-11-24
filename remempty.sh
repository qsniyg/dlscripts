find "$@" -type d | while read line; do [ ! -d "$line" ] && line="$line "; NUM=`ls -1 "$line" | wc -l`; [ "$NUM" -ne 0 ] && continue; rm -rf "$line"; done
