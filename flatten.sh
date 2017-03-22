#!/bin/sh
find "$@" -mindepth 2 -type f -exec mv -t "$@" -i '{}' +