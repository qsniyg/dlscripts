cat "$@" | jq -r '.entries[] | (.photos | tostring) + " photos	" + .id + "	" + .title._content' | sort -rh
