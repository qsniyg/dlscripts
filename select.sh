jq '.entries |= [(.[] | select('"$@"'))]'
