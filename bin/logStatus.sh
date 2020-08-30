#!/usr/bin/env bash

for file in logs/*; do
  #echo "file: $file"
  #echo "out: $out"
  out="$(tail -n 1 $file)"
  if echo $out | grep -vq "Processing report"; then
    echo "$(basename $file): Needs looking at ($out)"
    continue
  fi

  curr="$(echo $out | cut -d\- -f 2 | cut -d' ' -f 4)"
  total="$(echo $out | cut -d\- -f 2 | cut -d' ' -f 6)"

  if [ "$curr" != "$total" ]; then
    echo "$(basename $file): Still working ($curr of $total)"
    continue
  fi

  #echo "curr: $curr"
  #echo "total: $total"
done
