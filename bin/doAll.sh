#!/usr/bin/env bash

# we're skipping the following:
# - buru the gorger (doesn't get enough casts)
# - buru's trash mobs
ignoreEnemies="15379,15514,15521"

for zone in 1000 1001 1002 1003 1004 1005; do
  # -q quiet mode, -c skip curses, -w write results
  nohup python -u ./main.py -qcw -z $zone -i $ignoreEnemies > logs/$zone.log 2>&1 &
done
