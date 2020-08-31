# partials

This tool attempts to determine the resistance values of enemies by scraping Warcraft Logs.

## Results

You can find the latest results in `resistances.txt`

- The values are *actual* resistance, not effective. This means:
    - These are the values *before* any curse is applied
    - Level based resistances are *not* included
- Scraping was limited to 50,000 reports and 1,000 casts per magic school to save time
    - This is enough to determine if an enemy has any resistances, but...
    - There *seems* to be 1-10 points of variance due to this sample size
- More details per enemy can be found in `results/`
    - Additional details include number of casts, misses, and partials per school.
    - To display a detailed table per enemy: `./main.py -r results/enemyid.json`

## Setup / Running 

- Requires python with modules:
    - `python -m pip install requests datetime jsonpath-ng terminaltables`
- Finally run `./main.py -h` for usage information
- To do your own scrapes, must setup `variables.txt` with your api key/token
    - uses both v1 and v2 api's so both keys are needed
    - can use the tool `bin/createToken.sh` to help

## Known issues 

- Frost isn't supported yet. Binary spells don't partial resist.
- Shazzrah may be incorrect due to his `Deaden Magic` ability.
- Some enemies may not have enough data / time to scrape yet.
- Some enemies have mechanics that fudge the numbers
    - Chromaggus, Ossirian, 
