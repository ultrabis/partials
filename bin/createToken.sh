#!/bin/bash

CLIENT_ID="$1"
CLIENT_SECRET="$2"

if [ "$CLIENT_ID" == "" -o "$CLIENT_SECRET" == "" ]; then
  echo "Usage: createSecrets <CLIENT_ID> <CLIENT_TOKEN>"
  echo ""
  exit 1
fi

curl -u ${CLIENT_ID}:${CLIENT_SECRET} -d grant_type=client_credentials https://www.warcraftlogs.com/oauth/token
