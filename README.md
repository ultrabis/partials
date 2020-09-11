# partials

This tool attempts to determine the resistance values of enemies by scraping Warcraft Logs.

## TLDR

Spell penetration is worthless unless you're fighting Lucifron (Fire / Shadow), Gehennas (Fire / Shadow), or Shazzrah (Fire / Arcane). 

## Results

You can find the latest results in `resistances.txt`

- The values are *actual* resistance, not effective. This means:
    - These are the values *before* any curse is applied
    - Level based resistances are *not* included
- Scraping was limited to 50,000 reports and 1,000 casts per magic school to save time
    - This is enough to determine if an enemy has any resistances, but...
    - There *seems* to be 1-10 points of variance due to this sample size
- More details per enemy can be found in `logs/` and `results/`
    - Additional details include number of casts, misses, and partials per school.
    - To display a detailed table per enemy: `./main.py -r results/enemyid.json`

## Setup

- Requires python with modules:
    - `python -m pip install requests datetime jsonpath-ng terminaltables`
- To do your own scrapes, must setup `variables.txt` with your api key/token
    - uses both v1 and v2 api's so both keys are needed
    - can use the tool `bin/createToken.sh` to help
    
## Usage

```
Usage: main.py [-h | -d | -a | -r <file.json>] | [OPTIONS] <TARGETS>

-h                      Show usage and exit (this screen)
-d                      Display all zone information and exit (zones, encounters, enemies)
-r                      Display results from <file.json>
-a                      Display all results

OPTIONS
-v                      Verbose output (DEFAULT: False)
-q                      Quiet mode. (DEFAULT: False)
-w                      Write results to the 'results' directory (DEFAULT: False)
-c                      Skip casts with a curse active (DEFAULT: False)
-i                      Enemies to ignore delimited by comma (DEFAULT: None)
-s  <spellCastLimit>    Stop scraping a school after number of casts reaches <spellCastLimit> (DEFAULT: 1000)
-m  <magicSchoolNames>  Magic school names delimited by comma (DEFAULT: arcane,fire,frost,nature,shadow)

TARGETS
-e  <enemyID>           Scrape one <enemyID> OR
-n  <encounterID>       Scrape all enemies in <encounterID> OR
-z  <zoneID>            Scrape all enemies in <zoneID>

EXAMPLE
 Scrape arcane and nature resistance of Shazzrah: main.py -m arcane,nature -e 12264
```

## Known issues 

- Frost isn't supported yet. Binary spells don't partial resist.
- Shazzrah may be incorrect due to his `Deaden Magic` ability.
- Some enemies may not have enough data / time to scrape yet.
- Some enemies have mechanics that fudge the numbers
    - Chromaggus, Ossirian, Viscidius
