#!/usr/bin/env python3

import os, sys, glob, requests, datetime, gzip, json, enum, getopt
from utils import fetchActors, fetchGear, fetchDamageEvents, fetchAbilityEvents, fetchReportList, fetchReportSummary # graphql queries
from utils import MagicSchool, enchantData
from jsonpath_ng import jsonpath, parse
from terminaltables import AsciiTable
from variables import apiKey

verbose = False
MAX_REPORTS = 50000

class FriendlyActor:
    def __init__(self, actor: dict):
        self.id = actor.get('id')
        self.name = actor.get('name')
        self.gear = actor.get('gear')
        self.gearValues = self.getGearValues()

    def getGearValues(self):
        hitValue = 89  # Hit from talents
        spellPenValue = 0
        for item in self.gear:
            itemID = item.get('id')
            hitValue += enchantData.get(item.get('permanentEnchant'), 0)
            for jsonItem in jsonItems:
                if jsonItem['id'] == itemID:
                    if 'spellHit' in jsonItem:
                        hitValue += jsonItem['spellHit']
                    if 'spellPenetration' in jsonItem:
                        spellPenValue += jsonItem['spellPenetration']
        if hitValue > 99:
            hitValue = 99
        return {'spellHit': hitValue, 'spellPen': spellPenValue}
        
class DebuffEvent:
    def __init__(self, sTime: int, eTime: int, mod: float = 1.1):
        self.sTime = sTime
        self.eTime = eTime
        self.mod = mod

    def getValue(self, time: int, damage: float):
        isTimed = self.sTime <= time <= self.eTime
        return damage * self.mod if isTimed else -1


class Report:
    def __init__(self, options, reportCode: str, spec: dict, encounterID: int, enemyIDs: list):
        self.options = options
        self.reportCode = reportCode
        self.spec = spec
        self.spellIDQuery = 'ability.id in ({})'.format(', '.join(str(spell) for spell in self.spec.get('spellIDs')))
        self.encounterID = encounterID
        self.enemyIDs = enemyIDs
        self.actors, self.enemyID = self.getActors()
        self.curseEvents = self.getCurseUptime()
        self.damageModifiers = self.getDamageModifiers()

    def getActors(self):
        actorList = []
        try:
            actors = fetchActors(self.reportCode). \
                get('data', {}). \
                get('reportData', {}). \
                get('report', {}). \
                get('masterData', {}). \
                get('actors', [])
        except AttributeError:
            return [[], []]
        try:
            gear = fetchGear(self.reportCode, self.encounterID). \
                get('data', {}). \
                get('reportData', {}). \
                get('report', {}). \
                get('events', {}). \
                get('data', [])
        except AttributeError:
            return [[], []]

        if actors == None:
            return [[], []]

        for actor in filter(lambda a: a.get('icon') == self.spec.get('icon'), actors):
            try:
                actor['gear'] = next(a for a in gear if a.get('sourceID') == actor.get('id')).get('gear')
            except Exception:
                continue
            actorList.append(FriendlyActor(actor))
        try:
            enemyID = sorted(list(filter(lambda a: a.get('gameID') in self.enemyIDs, actors)),
                             key=lambda a: a.get('id'))
            enemyID = enemyID[-1].get('id')
        except:
            enemyID = 0
        return [actorList, enemyID]

    # FIXME: dumb hack for shazzrahs deaden magic. should clean up someday, but not today.
    def getDeadenMagicUptime(self):  
        if not self.enemyID:
            return []
            
        url = "https://classic.warcraftlogs.com:443/v1/report/tables/buffs/{reportCode}?start=0&end=999999999999&hostility=1&by=source&abilityid={abilityID}&encounter={encounterID}&api_key={apiKey}".format(
            reportCode=self.reportCode, abilityID=19714, encounterID=self.encounterID, apiKey=apiKey)

        try:
            response = requests.get(url)
            response.close()
            data = response.json()
            data = next(filter(lambda event: event.get('id') == self.enemyID, data.get('auras', [])))
            events = [DebuffEvent(event.get('startTime'), event.get('endTime')) for event in data.get('bands')]
            return events
        except:
            return []

    def getCurseUptime(self):  # Selects only one entry for simplicity
        if not self.enemyID:
            return []
            
        if self.spec.get('curseID') == None:
            return []

        url = "https://classic.warcraftlogs.com:443/v1/report/tables/debuffs/{reportCode}?start=0&end=999999999999&hostility=1&by=source&abilityid={abilityID}&encounter={encounterID}&api_key={apiKey}".format(
            reportCode=self.reportCode, abilityID=self.spec.get('curseID'), encounterID=self.encounterID, apiKey=apiKey)

        try:
            response = requests.get(url)
            response.close()
            data = response.json()
            data = next(filter(lambda event: event.get('id') == self.enemyID, data.get('auras', [])))
            events = [DebuffEvent(event.get('startTime'), event.get('endTime')) for event in data.get('bands')]
            return events
        except:
            return []

    def getDamageModifiers(self):
        debuffEvents = []
        for dmgMod in self.spec.get('dmgMods'):
            url = "https://classic.warcraftlogs.com:443/v1/report/events/debuffs/{reportCode}?start=0&end=999999999999&hostility=1&by=source&abilityid={abilityID}&encounter={encounterID}&api_key={apiKey}".format(
                reportCode=self.reportCode, abilityID=dmgMod.get('id'), encounterID=self.encounterID, apiKey=apiKey)
            try:
                response = requests.get(url)
                response.close()
                data = response.json().get('events', [])
            except:
                return []

            stackCount = 0
            startingTiming = 0
            for event in filter(lambda e: e.get('targetID') == self.enemyID, data):
                if event.get('type') == 'applydebuff':
                    startingTiming = event['timestamp'] + 1
                    stackCount = 1
                if event.get('type') == 'applydebuffstack':
                    debuffEvents.append(
                        DebuffEvent(startingTiming, event.get('timestamp'), 1 + stackCount * dmgMod.get('modifier')))
                    startingTiming = event.get('timestamp') + 1
                    stackCount += 1
                if event.get('type') == 'removedebuff':
                    debuffEvents.append(
                        DebuffEvent(startingTiming, event.get('timestamp'), 1 + stackCount * dmgMod.get('modifier')))
                    stackCount = 0
        return debuffEvents

    def mapPartialValue(self, damage):
        if 22 < damage < 28:
            return 25
        if 47 < damage < 53:
            return 50
        if 72 < damage < 78:
            return 75
        if 97 < damage < 103:
            return 100
        return -1

    def getCurrentActor(self, id):
        return next(filter(lambda actor: actor.id == id, self.actors))

    def getCurrentTimestamp(self, time, damage, debuffList, defaultMod=-1):
        if damage == 0:
            return 0
        for debuffClass in debuffList:
            tempDamage = debuffClass.getValue(time, damage)
            if tempDamage > 0:
                return tempDamage
        #  Return -1 if current check is for curse, return unmodified damage if current check is for damage multipliers
        if defaultMod > 0:
            return damage * defaultMod
        else:
            return -1

    def getDamageEvents(self):
        hitData = {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}
        try:
            events = fetchDamageEvents(self.reportCode, self.encounterID, self.spec.get('name'), self.spellIDQuery). \
                get('data', {}). \
                get('reportData', {}). \
                get('report', {}). \
                get('events', {}). \
                get('data', [])
        except AttributeError:
            print('attributeError - reportCode: ' + self.reportCode + ', encounterID: ' + str(self.encounterID) + ', spec: ' + self.spec.get('name'))
            return hitData
        events = list(filter(lambda event: event.get('sourceID') in [actor.id for actor in self.actors] and
                                           event.get('targetID') == self.enemyID and not event.get('tick'), events))
        for event in events:
            actor = self.getCurrentActor(event.get('sourceID'))
            gearValues = actor.getGearValues()
            hitValue = gearValues['spellHit']
            spellPenValue = gearValues['spellPen']
            #hitData = {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}

            # skip players with spell penetration gear
            if spellPenValue > 0:
                continue

            # get damage event
            damage = event.get('unmitigatedAmount', 0) * self.spec.get('hitTypes').get(event.get('hitType'), 1)

            # handle shazzrah hack for Deaden Magic 
            if self.enemyIDs[0] == 12264: 
                deadenMagicDamage = self.getCurrentTimestamp(event.get('timestamp'), damage, self.getDeadenMagicUptime())
                if deadenMagicDamage > 0:
                    continue

            # handle curses. if skipCurses is set, we'll ignore the cast
            curseDamage = self.getCurrentTimestamp(event.get('timestamp'), damage, self.curseEvents)
            if self.options.get('skipCurses'):
                if curseDamage > 0:
                    continue
            else:
                damage = curseDamage

            if damage == 0: # miss
                hitData[0] += 1
                continue
            elif damage < 0: 
                continue
            else:
                damage = self.getCurrentTimestamp(event.get('timestamp'), damage, self.damageModifiers, 1)
                eventAmount = event.get('amount')
                partial = self.mapPartialValue(eventAmount * 100 / damage)
                if partial > 0:
                    #print('damage = ' + str(damage) + ', eventAmount = ' + str(eventAmount) + ', partial = ' + str(partial))
                    hitData[partial] += 1
        return hitData

def printUsage():
    print(
        '''
Usage: main.py [-h | -d | -a | -r <file.json>] | [OPTIONS] <TARGETS>

-h                      Show usage and exit (this screen)
-d                      Display all zone information and exit (zones, encounters, enemies)
-r                      Display results from <file.json>
-a                      Display all results                       

OPTIONS
-v                      Verbose output (DEFAULT: False)
-q                      Quiet mode. (DEFAULT: False)
-w                      Write results to the `results` directory (DEFAULT: False)
-c                      Skip casts with a curse active (DEFAULT: False)
-i                      Enemies to ignore delimited by comma (DEFAULT: None)
-s  <spellCastLimit>    Stop scraping a school after number of casts reaches <spellCastLimit> (DEFAULT: 1000)
-m  <magicSchoolNames>  Magic school names delimited by comma (DEFAULT: arcane,fire,frost,nature,shadow)

TARGETS
-e  <enemyID>           Scrape one <enemyID> OR
-n  <encounterID>       Scrape all enemies in <encounterID> OR
-z  <zoneID>            Scrape all enemies in <zoneID>

EXAMPLE
 Scrape arcane and nature resistance of Shazzrah:
   `main.py -m arcane,nature -e 12264` 
        '''
    )


# parse input arguments and return a dictionary with everything the main program needs
def getOptions(argv):
    options = {
        "quiet": False,
        "verbose": False,
        "skipCurses": False,
        "writeResults": False,
        "spellCastLimit": 1000,
        "zoneID": None,
        "zoneName": None,
        "ignoreEnemies": [],
        "encounters": [],
        "specs": [],
    }
    
    # parse args
    try:
        opts,args = getopt.getopt(sys.argv[1:], "hqdwar:s:vcm:e:i:z:n:")
    except getopt.GetoptError:
        printUsage()
        sys.exit(2)

    # temp values
    magicSchoolNames = 'arcane,fire,frost,nature,shadow'
    enemyID = None
    zoneID = None
    encounterID = None

    for opt, arg in opts:
        if opt == '-h':
            printUsage()
            sys.exit(0)
        elif opt == '-a':
            displayAllResults()
            sys.exit(0)
        elif opt == '-d':
            displayZoneInfo()
            sys.exit(0)
        elif opt == '-r':
            with open(arg) as f:
                resultsJson = json.load(f)
            table_instance = AsciiTable(resultsJson.get('tables'), resultsJson.get('enemyName'))
            print(table_instance.table)
            sys.exit(0)
        elif opt == '-w':
            options['writeResults'] = True
        elif opt == '-i':
            for x in arg.split(','):
                options['ignoreEnemies'].append(int(x))
        elif opt == '-v':
            options['verbose'] = True
        elif opt == '-q':
            options['verbose'] = False
            options['quiet'] = True
        elif opt == '-c':
            print('Ignoring casts with a curse active')
            options['skipCurses'] = True
        elif opt == '-s':
            options['spellCastLimit'] = int(arg)
        elif opt == '-m':
            magicSchoolNames = arg.lower()
        elif opt == '-z':
            zoneID = int(arg)
        elif opt == '-n':
            encounterID = int(arg)
        elif opt == '-e':
            enemyID = int(arg)

    # build up specs based on selected magic schools. each magic school
    # is associated with a certain player spec, spells, curses, etc
    for x in magicSchoolNames.split(','):
        spec = {
            'name': None,
            'icon': None,
            'magicSchool': None,
            'hitTypes': None,
            'curseID': None,
            'spellIDs': [],
            'dmgMods': []
        }
        magicSchoolName = x.lower().strip()
        if magicSchoolName == 'arcane':
            spec['name'] = 'Balance'
            spec['icon'] = 'Druid-Balance'
            spec['magicSchool'] = MagicSchool.Arcane
            spec['curseID'] = 17937 # Curse of Shadow
            spec['spellIDs'] = [25298, 9876, 9835] # Starfire Rank 7, Starfire Rank 6, Moonfire Rank 10
            spec['hitTypes'] = {
                1: 1,  # hitType = 1, hit
                2: 2.0,  # hitType = 2, crit (vegeance talent makes crit * 2)
                14: 0,  # hitType = 14, resist
                16: 1,  # hitType = 16, partial hit
                17: 2.0  # hitType = 17, partial crit (vengeance talent makes crit * 2)
            }
            options['specs'].append(spec)
        elif magicSchoolName == 'fire':
            spec['name'] = 'Fire'
            spec['icon'] = 'Mage'
            spec['magicSchool'] = MagicSchool.Fire 
            spec['curseID'] = 11722  # Curse of Elements
            spec['spellIDs'] = [10151, 10207, 10199]  # Fireball, Scorch, Fire Blast
            spec['dmgMods'] = [
                {'type': 'stackable', 'id': 22959, 'modifier': 0.03},  # Improved Scorch
                {'type': 'simple', 'id': 23605, 'modifier': 0.15},  # Nightfall
            ]
            spec['hitTypes'] = {
                1: 1,  # hitType = 1, hit
                2: 1.5,  # hitType = 2, crit
                14: 0,  # hitType = 14, resist
                16: 1,  # hitType = 16, partial hit
                17: 1.5  # hitType = 17, partial crit
            }
            options['specs'].append(spec)
        elif magicSchoolName == 'frost':
            spec['name'] = 'Frost'
            spec['icon'] = 'Mage-Frost'
            spec['magicSchool'] = MagicSchool.Frost
            spec['curseID'] = 11722  # Curse of Elements
            spec['spellIDs'] = [116, 25304, 10181] # Frostbolt Rank 1, Frostbolt Rank 11, Frostbolt Rank 10
            spec['hitTypes'] = {
                1: 1,  # hitType = 1, hit
                2: 1.5,  # hitType = 2, crit
                14: 0,  # hitType = 14, resist
                16: 1,  # hitType = 16, partial hit
                17: 1.5  # hitType = 17, partial crit
            }
            # TODO: any dmgmods?
            options['specs'].append(spec)
        elif magicSchoolName == 'nature':
            #spec['name'] = 'Balance'
            #spec['icon'] = 'Druid-Balance'
            #spec['spellIDs'] = [9912] # Wrath Rank 8

            spec['name'] = 'Elemental'
            spec['icon'] = 'Shaman-Elemental'
            spec['spellIDs'] = [15208] # Lightning Bolt Rank 10

            spec['magicSchool'] = MagicSchool.Nature
            spec['curseID'] = None
            spec['hitTypes'] = {
                1: 1,  # hitType = 1, hit
                2: 2.0,  # hitType = 2, crit (elemental fury talent makes crit * 2)
                14: 0,  # hitType = 14, resist
                16: 1,  # hitType = 16, partial hit
                17: 2.0  # hitType = 17, partial crit (elemental fury talent makes crit * 2)
            }
            options['specs'].append(spec)
        elif magicSchoolName == 'shadow':
            spec['name'] = 'Destruction'
            spec['icon'] = 'Warlock-Destruction'
            spec['magicSchool'] = MagicSchool.Shadow
            spec['curseID'] = 17937 # Curse of Shadow
            spec['spellIDs'] = [25307, 11661] # shadow bolt rank 9 and 10
            # TODO: any dmgMods? 

            spec['hitTypes'] = {
                1: 1,  # hitType = 1, hit
                2: 1.5,  # hitType = 2, crit
                14: 0,  # hitType = 14, resist
                16: 1,  # hitType = 16, partial hit
                17: 1.5  # hitType = 17, partial crit
            }
            options['specs'].append(spec)
        else:
            print('ERROR: Invalid magic school name: ' + magicSchoolName)
            printUsage()
            sys.exit(4)
        
    # handle zone, encounters and enemies
    with open('zone.json') as zone_data:
        zones = json.load(zone_data)

    # by zone
    if zoneID != None:
        for zone in zones:
            if zone['id'] == zoneID:
                options['zoneID'] = zone['id']
                options['zoneName'] = zone['name']
                options['encounters'] = zone['encounters']
        
        if options['zoneID'] == None:
            print('ERROR: Invalid zoneID: ' + str(zoneID))
            print('')
            print('Try -l to find a valid zoneID')
            sys.exit(4)
    # by encounter
    elif encounterID != None:
        for zone in zones:
            for encounter in zone['encounters']:
                if encounter['id'] == encounterID:
                    options['zoneID'] = zone['id']
                    options['zoneName'] = zone['name']
                    options['encounters'].append(encounter)
        
        if len(options['encounters']) == 0:
            print('ERROR: Invalid encounterID: ' + str(encounterID))
            print('')
            print('Try -l to find a valid encounterID')
            sys.exit(4)
    # by enemy
    elif enemyID != None:
        for zone in zones:
            for encounter in zone['encounters']:
                for enemy in encounter['enemies']:
                    if enemyID == enemy['id']:
                        options['zoneID'] = zone['id']
                        options['zoneName'] = zone['name']
                        options['encounters'].append({
                            'id': encounter['id'],
                            'name': encounter['name'],
                            'enemies': [ {'id': enemy['id'], 'name': enemy['name'], 'level': enemy['level']} ]
                        })
    else:
        print('ERROR: Must specify a zone, encounter or enemy')
        printUsage()
        sys.exit(3)

    if len(options['encounters']) == 0:
        print('ERROR: Failed to find any encounters')
        sys.exit(3)

    return(options)

# display all results (amalgamated)
def displayAllResults():
    table_data_without_curses = []
    table_data_without_curses.append(('enemy', 'arcane', 'fire', 'frost', 'nature', 'shadow'))

    table_data_with_curses = []
    table_data_with_curses.append(('enemy', 'arcane', 'fire', 'frost', 'nature', 'shadow'))
    
    with open('zone.json') as zone_data:
        zones = json.load(zone_data)

    for zone in zones:
        for encounter in zone['encounters']:
            for enemy in encounter['enemies']:
                enemyName = enemy.get('name') + ' (' + str(enemy.get('id')) + ')'
                resultsWithCurses = 'results/withCurses/' + str(enemy.get('id')) + '.json'
                if os.path.exists(resultsWithCurses):
                    with open(resultsWithCurses) as f:
                        resultsJson = json.load(f)
                    tableJson = resultsJson.get('tables')
                    table_data_with_curses.append((
                        enemyName,
                        tableJson[1][1],
                        tableJson[2][1],
                        '?', #tableJson[3][1], # frost is broke right now
                        tableJson[4][1],
                        tableJson[5][1]
                    ))
                
                resultsWithoutCurses = 'results/withoutCurses/' + str(enemy.get('id')) + '.json'
                if os.path.exists(resultsWithoutCurses):
                    with open(resultsWithoutCurses) as f:
                        resultsJson = json.load(f)
                    tableJson = resultsJson.get('tables')
                    table_data_without_curses.append((
                        enemyName,
                        tableJson[1][1],
                        tableJson[2][1],
                        '?', #tableJson[3][1], # frost is broke right now
                        tableJson[4][1],
                        tableJson[5][1]
                    ))
                
    table_instance = AsciiTable(table_data_without_curses, 'Resistances (without curses)')
    print(table_instance.table)
                    
# List all bosses (-l option)
def displayZoneInfo(zoneID=0):
    with open('zone.json') as zone_data:
        zoneData = json.load(zone_data)

    for zone in zoneData:
        if zoneID != 0 and zoneID != zone['id']:
            continue

        print('# Zone: {} ({})'.format(zone['name'], zone['id']))
        for encounter in zone['encounters']:
            print('## Encounter: {} ({})'.format(encounter['name'], encounter['id']))
            for enemy in encounter['enemies']:
                print('### Enemy: {} ({})'.format(enemy['name'], enemy['id']))
        print('')

# for every report in a zone, create a summary and add it to a giant array. then save the array
# as a JSON file in `cache/`. then gzip it so github doesn't get mad.
#
# a report summary contains the report code, the specs present in raid, and the spellIDs cast.
#
# when scraping we'll read this cache file instead of querying the report codes from WCL.
# not only do we save time on the query, we can also skip entire reports if the spec or
# spells we require aren't present.
def getJSONFromGZIPFile(FilePath):
    f = gzip.open(FilePath, 'rb')
    file_content = f.read()
    return(json.loads(file_content))

def getReportSummaries(options):
    zoneID = options['zoneID']
    reportSummariesTEMP = 'cache/' + str(zoneID) + '.json'
    reportSummariesGZIP = 'cache/' + str(zoneID) + '.json.gz'
    
    if os.path.exists(reportSummariesGZIP):
        if options['verbose']: print('Cache exists (' + reportSummariesGZIP + '), skipping...')
        return getJSONFromGZIPFile(reportSummariesGZIP)

    print('Caching report summaries for zone to temp file' + str(zoneID) + ' to ' + reportSummariesTEMP)

    reportSummaries = []
    hasMorePages = True
    page = 0
    totalReportsDone = 0
    while hasMorePages:

        if totalReportsDone >= MAX_REPORTS:
            print('Maximum reports reached (' + str(MAX_REPORTS) + ')')
            break
            
        page += 1
        print('Fetching page ' + str(page) + ' for zone ' + str(zoneID))
        zoneReports = fetchReportList(zoneID, page)
        hasMorePages = zoneReports.get('data').get(
            'reportData').get('reports').get('has_more_pages')
        reportCodesExpr = parse('$.data.reportData.reports.data[*].code')
        reportCodes = [
            match.value for match in reportCodesExpr.find(zoneReports)]

        reportCodeCounter = 0
        reportCodeCount = len(reportCodes)
        for reportCode in reportCodes:
            reportCodeCounter += 1
            print('- caching report summary ' + str(reportCodeCounter) + ' of ' + str(reportCodeCount) + ' (' + reportCode + ')')

            reportSummary = fetchReportSummary(reportCode)
            reportSummaries.append(reportSummary)
            totalReportsDone += 1

    out_file = open(reportSummariesTEMP, "w")
    json.dump(reportSummaries, out_file)
    out_file.close()

    print('wrote ' + str(len(reportSummaries)) + ' report codes to temp file' + reportSummariesTEMP)
    with open(reportSummariesTEMP, 'rb') as f_in, gzip.open(reportSummariesGZIP, 'wb') as f_out:
        f_out.writelines(f_in)
    print('writing gzip file to ' + reportSummariesGZIP)

    return getJSONFromGZIPFile(reportSummariesGZIP)

def reportSummaryHasSpellForSpec(reportSummary, spec):
    return True in [a in spec.get('spellIDs') for a in reportSummary.get('spellIDs')]

def reportSummaryHasIconForSpec(reportSummary, spec):
    for icon in reportSummary.get('icons'):
        if icon == spec.get('icon'):
            return True

    return False

def reachedSpellCastLimit(options, hitTables, magicSchool):
    if magicSchool == MagicSchool.Arcane:
        hitTable = hitTables[0]
    elif magicSchool == MagicSchool.Fire:
        hitTable = hitTables[1]
    elif magicSchool == MagicSchool.Frost:
        hitTable = hitTables[2]
    elif magicSchool == MagicSchool.Nature:
        hitTable = hitTables[3]
    elif magicSchool == MagicSchool.Shadow:
        hitTable = hitTables[4]

    return (hitTable[0] + hitTable[25] + hitTable[50] + hitTable[75] + hitTable[100]) >= options.get('spellCastLimit')


# Returns the actual target resistance using the partial average percent.
# Actual resistance a.k.a 'resistance' does *not* include level based resistances.
#
# It's nonsensical to include level based resistances in a report of boss resistances,
# because they're not innate to the boss, but rather a calculation done at the time of
# spell cast. 
def getResFromPartialAverage(partialPercent, magicSchool, playerLevel:int = 60, targetLevel:int = 63):
    # get the level based resistances
    if magicSchool == MagicSchool.Frost:
        resFromLevel = 0
    else:
        if targetLevel > playerLevel:
            levelDiff = targetLevel - playerLevel 
        else:
            levelDiff = 0

        resFromLevel = levelDiff * 8

    # convert partial percent to resistance and remove level based resistances
    res = max(round((partialPercent * 4) - resFromLevel, 2), 0)
    if verbose: print(
        'res=' +
        str(res) +
        'partialAvg%=' +
        str(partialPercent) +
        ', resFromLevel=' +
        str(resFromLevel) + ''
    )
    return res

##################################################################
# processReport
##################################################################
def processReport(options, reportSummary, encounter, enemy, hitTables):
    reportCode = reportSummary.get('code')
    if options.get('skipCurses'):
        enemyName = enemy.get('name') + ' (without curses)'
    else:
        enemyName = enemy.get('name') + ' (with curses)'

    hitTableArcane = hitTables[0]
    hitTableFire = hitTables[1]
    hitTableFrost = hitTables[2]
    hitTableNature = hitTables[3]
    hitTableShadow = hitTables[4]

    changed = False
    for spec in options.get('specs'):
        magicSchool = spec.get('magicSchool')

        # check the spells used and specs present in the report summary
        # this will let us skip processing reports that don't have the
        # data we're looking for
        if not reportSummaryHasSpellForSpec(reportSummary, spec):
            if options['verbose']: print('Skipping ' + magicSchool.name + '. Report missing needed spells')
            continue

        if not reportSummaryHasIconForSpec(reportSummary, spec):
            if options['verbose']: print('Skipping ' + magicSchool.name + '. Report missing needed spec')
            continue

        if reachedSpellCastLimit(options, hitTables, magicSchool):
            if options['verbose']: print('Skipping ' + magicSchool.name + '. Spell cast limit reached.')
            continue

        # fetch damage events i.e. hitValues i.e. how many full hits, misses, and partials...
        # add them to our existing values in hitTable
        if options['verbose']: print(' --- processing ' + magicSchool.name)
        hitValues = Report(options, reportCode, spec, encounter.get('id'), [enemy.get('id')]).getDamageEvents()
        if magicSchool == MagicSchool.Arcane:
            hitTable = hitTables[0]
        elif magicSchool == MagicSchool.Fire:
            hitTable = hitTables[1]
        elif magicSchool == MagicSchool.Frost:
            hitTable = hitTables[2]
        elif magicSchool == MagicSchool.Nature:
            hitTable = hitTables[3]
        elif magicSchool == MagicSchool.Shadow:
            hitTable = hitTables[4]
        for x in hitValues: hitTable[x] = hitTable[x] + hitValues[x]
        changed = True

    # don't bother calculating, writing, and displaying results if nothing even changed
    if not changed:
        return(0)

    hitsArcane = hitTableArcane[25] + hitTableArcane[50] + hitTableArcane[75] + hitTableArcane[100]
    hitsFire = hitTableFire[25] + hitTableFire[50] + hitTableFire[75] + hitTableFire[100]
    hitsFrost = hitTableFrost[25] + hitTableFrost[50] + hitTableFrost[75] + hitTableFrost[100]
    hitsNature = hitTableNature[25] + hitTableNature[50] + hitTableNature[75] + hitTableNature[100]
    hitsShadow = hitTableShadow[25] + hitTableShadow[50] + hitTableShadow[75] + hitTableShadow[100]
    
    hitSumArcane = hitTableArcane[25] * 0.25 + hitTableArcane[50] * 0.5 + hitTableArcane[75] * 0.75 + hitTableArcane[100]
    hitSumFire = hitTableFire[25] * 0.25 + hitTableFire[50] * 0.5 + hitTableFire[75] * 0.75 + hitTableFire[100]
    hitSumFrost = hitTableFrost[25] * 0.25 + hitTableFrost[50] * 0.5 + hitTableFrost[75] * 0.75 + hitTableFrost[100]
    hitSumNature = hitTableNature[25] * 0.25 + hitTableNature[50] * 0.5 + hitTableNature[75] * 0.75 + hitTableNature[100]
    hitSumShadow = hitTableShadow[25] * 0.25 + hitTableShadow[50] * 0.5 + hitTableShadow[75] * 0.75 + hitTableShadow[100]

    missesArcane = hitTableArcane[0]
    missesFire = hitTableFire[0]
    missesFrost = hitTableFrost[0]
    missesNature = hitTableNature[0]
    missesShadow = hitTableShadow[0]

    castsArcane = hitsArcane + missesArcane
    castsFire = hitsFire + missesFire
    castsFrost = hitsFrost + missesFrost
    castsNature = hitsNature + missesNature
    castsShadow = hitsShadow + missesShadow

    if hitsArcane > 0: 
        partialAverageArcane = round(100 * (1 - hitSumArcane / hitsArcane), 2)
        resistArcane = getResFromPartialAverage(partialAverageArcane, MagicSchool.Arcane, 60, enemy.get('level'))
    elif castsArcane >= 50 and castsArcane == missesArcane:
        partialAverageArcane = 'IMMUNE'
        resistArcane = 'IMMUNE'
    else:
        partialAverageArcane = '?'
        resistArcane = '?'
        
    if hitsFire > 0: 
        partialAverageFire = round(100 * (1 - hitSumFire / hitsFire), 2)
        resistFire = getResFromPartialAverage(partialAverageFire, MagicSchool.Fire, 60, enemy.get('level'))
    elif castsFire >= 50 and castsFire == missesFire:
        partialAverageFire = 'IMMUNE'
        resistFire = 'IMMUNE'
    else:
        partialAverageFire = '?'
        resistFire = '?'

    if hitsFrost > 0:
        partialAverageFrost = round(100 * (1 - hitSumFrost / hitsFrost), 2)
        resistFrost = getResFromPartialAverage(partialAverageFrost, MagicSchool.Frost, 60, enemy.get('level'))
    elif castsFrost >= 50 and castsFrost == missesFrost:
        partialAverageFrost = 'IMMUNE'
        resistFrost = 'IMMUNE'
    else:
        partialAverageFrost = '?'
        resistFrost = '?'
        
    if hitsNature > 0:
        partialAverageNature = round(100 * (1 - hitSumNature / hitsNature), 2)
        resistNature = getResFromPartialAverage(partialAverageNature, MagicSchool.Nature, 60, enemy.get('level'))
    elif castsNature >= 50 and castsNature == missesNature:
        partialAverageNature = 'IMMUNE'
        resistNature = 'IMMUNE'
    else:
        partialAverageNature = '?'
        resistNature = '?'
        
    if hitsShadow > 0:
        partialAverageShadow = round(100 * (1 - hitSumShadow / hitsShadow), 2)
        resistShadow = getResFromPartialAverage(partialAverageShadow, MagicSchool.Shadow, 60, enemy.get('level'))
    elif castsShadow >= 50 and castsShadow == missesShadow:
        partialAverageShadow = 'IMMUNE'
        resistShadow = 'IMMUNE'
    else:
        partialAverageShadow = '?'
        resistShadow = '?'
    
    # note: the percentages used in the calculations reflect percent of damage done
    # but when we talk about partial resists we actually mean the opposite.
    # for e.g. a '75% partial' means that 75% damage was resisted.
    # so that's why 25 and 75 are swapped when displaying
    table_data = (
        ('school', 'res', '#', 'miss', 'full', '25%', '50%', '75%'),
        ('arcane', resistArcane, castsArcane, missesArcane, hitTableArcane[100], hitTableArcane[75], hitTableArcane[50], hitTableArcane[25]),
        ('fire', resistFire, castsFire, missesFire, hitTableFire[100], hitTableFire[75], hitTableFire[50], hitTableFire[25]),
        ('frost', resistFrost, castsFrost, missesFrost, hitTableFrost[100], hitTableFrost[75], hitTableFrost[50], hitTableFrost[25]),
        ('nature', resistNature, castsNature, missesNature, hitTableNature[100], hitTableNature[75], hitTableNature[50], hitTableNature[25]),
        ('shadow', resistShadow, castsShadow, missesShadow, hitTableShadow[100], hitTableShadow[75], hitTableShadow[50], hitTableShadow[25]),
    )
    
    if options.get('writeResults'):
        if options.get('skipCurses'):
            outputFile = 'results/withoutCurses/' + str(enemy.get('id')) + '.json'
        else:
            outputFile = 'results/withCurses/' + str(enemy.get('id')) + '.json'
            
        out_file = open(outputFile, "w")
        json.dump({
            'enemyID': enemy.get('id'),
            'enemyName': enemyName,
            'tables': table_data
        }, out_file)
        out_file.close()

    if options.get('quiet') == False:
        table_instance = AsciiTable(table_data, enemyName)
        print(table_instance.table)

##################################################################
# MAIN
##################################################################

#events = fetchAbilityEvents("6bN9dq2RxhVtTZfw", 667, 115, 19714, ['applybuff', 'removebuff'])
#print(events)
#exit(0)

# parse options
options = getOptions(sys.argv[1:]) 
if verbose == False:
    verbose = options.get('verbose')

# read item database into jsonItems
with open('item.json') as itemFile:
    jsonItems = json.load(itemFile)

reportSummaries = getReportSummaries(options)
for encounter in options['encounters']:
    if verbose: print(' - processing encounter ' + encounter.get('name') + ' (' + str(encounter.get('id')) + ')')
    for enemy in encounter['enemies']:
        if enemy.get('id') in options.get('ignoreEnemies'):
            if verbose: print(' -- ignoring enemy ' + enemy.get('name') + ' (' + str(enemy.get('id')) + ')')
            continue

        if verbose: print(' -- processing enemy ' + enemy.get('name') + ' (' + str(enemy.get('id')) + ')')
        hitTables = [
            {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}, # arcane
            {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}, # fire
            {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}, # frost
            {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}, # nature
            {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}  # shadow
        ]
        counter = 1
        count = len(reportSummaries)
        for reportSummary in reportSummaries:
            print('[{}] - Processing report {} of {}'.format(enemy.get('name'), counter, count))
            processReport(options, reportSummary, encounter, enemy, hitTables)
            counter += 1
