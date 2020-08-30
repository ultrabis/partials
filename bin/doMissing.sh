#!/usr/bin/env bash

cd "$(dirname "${BASH_SOURCE[1]}")"

# round 1
missing="11502 15727 11583 15509 15276 15275 15517"

# round 2
missing2="13020 15084 15085 14509 15114 14515 11380"

# round 3
missing3="14834 13020 12017 11983 14601 11981 14020"

# round 4 (stuff that broke)
missing4="14509 15084"

# round 5 (final)
missing5="11583 11981 15084 15085"

for enemyid in $missing5; do
  nohup python -u ./main.py -m arcane,fire,nature,shadow -cw -e $enemyid > logs/$enemyid.log 2>&1 &
done
