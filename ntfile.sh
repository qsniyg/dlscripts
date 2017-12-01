#!/bin/dash
sed -e 's/://g' -e 's/ $//g' -e 's/\.$//g' -e 's/</(/g' -e 's/>/)/g' -e 's/"/'"'"'/g' -e 's/?/？/g' -e 's/*/·/g' -e 's/|/❘/g' -e 's/\\/_/g'
