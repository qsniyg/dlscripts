find "$@" -type f | while read line; do mv "$line" "$@"/; done
