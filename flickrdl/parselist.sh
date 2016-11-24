jq -r '.entries[] | (.photos | tostring) + "\t" + .id + "\t" + .title._content'
