#!/usr/bin/env python

import requests
import datetime
import json
from utils import getActors, getGear, getDamageEvents, reportListQuery, enchantData, hitTypes
from variables import apiKey

curseID = 11722  # Curse of Elements
damageModID = 22959  # Improved Scorch
dpsDebuffValue = 0.03  # Improved Scorch
spellIDs = [10151, 10207, 10199]  # Fireball, Scorch, Fire Blast
spellIDquery = 'ability.id in ({})'.format(', '.join(str(spell) for spell in spellIDs))

fight = {
    'encounterID': 709,
    'enemyIDs': [15263]  # wowhead boss ID
}

# read item database into jsonData
with open('item.json') as json_data:
    jsonData = json.load(json_data)

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
            itemId = item.get('id')
            hitValue += enchantData.get(item.get('permanentEnchant'), 0)
            for jsonItem in jsonData:
                if jsonItem['id'] == itemId:
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
    def __init__(self, url: str, encounterInfo: dict):
        self.url = url
        self.encounterID = encounterInfo.get('encounterID')
        self.enemyIDs = encounterInfo.get('enemyIDs')
        self.actors, self.enemyID = self.getActors()
        self.curseEvents = self.getCurseUptime()
        self.damageModifiers = self.getDamageModifiers()

    def getActors(self):
        actorList = []
        try:
            actors = getActors(self.url). \
                get('data', {}). \
                get('reportData', {}). \
                get('report', {}). \
                get('masterData', {}). \
                get('actors', [])
        except AttributeError:
            return [[], []]
        try:
            gear = getGear(self.url, self.encounterID). \
                get('data', {}). \
                get('reportData', {}). \
                get('report', {}). \
                get('events', {}). \
                get('data', [])
        except AttributeError:
            return [[], []]
        for actor in filter(lambda a: a.get('icon') == 'Mage', actors):
            try:
                actor['gear'] = next(a for a in gear if a.get('sourceID') == actor.get('id')).get('gear')
            except Exception:
                continue
            actorList.append(FriendlyActor(actor))
        try:
            enemyID = sorted(list(filter(lambda a: a.get('gameID') in self.enemyIDs, actors)), key=lambda a: a.get('id'))
            enemyID = enemyID[-1].get('id')
        except:
            enemyID = 0
        return [actorList, enemyID]

    def getCurseUptime(self):  # Selects only one entry for simplicity
        if not self.enemyID:
            return []
        url = "https://classic.warcraftlogs.com:443/v1/report/tables/debuffs/{reportUrl}?start=0&end=999999999999&hostility=1&by=source&abilityid={abilityID}&encounter={encounterID}&api_key={apiKey}".format(
            reportUrl=self.url, abilityID=curseID, encounterID=self.encounterID, apiKey=apiKey)
        response = requests.get(url)
        response.close()
        data = response.json()
        try:
            data = next(filter(lambda event: event.get('id') == self.enemyID, data.get('auras', [])))
            events = [DebuffEvent(event.get('startTime'), event.get('endTime')) for event in data.get('bands')]
            return events
        except:
            return []

    def getDamageModifiers(self):
        url = "https://classic.warcraftlogs.com:443/v1/report/events/debuffs/{reportUrl}?start=0&end=999999999999&hostility=1&by=source&abilityid={abilityID}&encounter={encounterID}&api_key={apiKey}".format(
            reportUrl=self.url, abilityID=damageModID, encounterID=self.encounterID, apiKey=apiKey)
        response = requests.get(url)
        response.close()
        data = response.json().get('events', [])
        stackCount = 0
        debuffEvents = []
        startingTiming = 0
        for event in filter(lambda e: e.get('targetID') == self.enemyID, data):
            if event.get('type') == 'applydebuff':
                startingTiming = event['timestamp'] + 1
                stackCount = 1
            if event.get('type') == 'applydebuffstack':
                debuffEvents.append(
                    DebuffEvent(startingTiming, event.get('timestamp'), 1 + stackCount * dpsDebuffValue))
                startingTiming = event.get('timestamp') + 1
                stackCount += 1
            if event.get('type') == 'removedebuff':
                debuffEvents.append(
                    DebuffEvent(startingTiming, event.get('timestamp'), 1 + stackCount * dpsDebuffValue))
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
        hitData = {}
        try:
            events = getDamageEvents(self.url, self.encounterID, spellIDquery). \
            get('data', {}). \
            get('reportData', {}). \
            get('report', {}). \
            get('events', {}). \
            get('data', [])
        except AttributeError:
            return {89: {0: 0, 25: 0, 50: 0, 75: 0, 100: 0}}
        events = list(filter(lambda event: event.get('sourceID') in [actor.id for actor in self.actors] and
                                           event.get('targetID') == self.enemyID and not event.get('tick'), events))
        for event in events:
            actor = self.getCurrentActor(event.get('sourceID'))
            gearValues = actor.getGearValues()
            hitValue = gearValues['spellHit']
            # spellPenValue = gearValues['spellPen']
            hitData.setdefault(hitValue, {0: 0, 25: 0, 50: 0, 75: 0, 100: 0})
            timestamp = event.get('timestamp')
            damage = event.get('unmitigatedAmount', 0) * hitTypes.get(event.get('hitType'), 1)
            if not event.get('unmitigatedAmount'):
                print(event)
            # multiply if crit or make damage 0 if miss
            damage = self.getCurrentTimestamp(timestamp, damage, self.curseEvents)
            if damage == 0:
                hitData[hitValue][0] += 1
                continue
            elif damage < 0:
                continue
            else:
                damage = self.getCurrentTimestamp(timestamp, damage, self.damageModifiers, 1)
                partial = self.mapPartialValue(event.get('amount') * 100 / damage)
                if partial > 0:
                    hitData[hitValue][partial] += 1
        return hitData


table = {}
for i in range(89, 100):
    table.setdefault(i, {0: 0, 25: 0, 50: 0, 75: 0, 100: 0})

reportList = set()
page = 1
while page < 20:
    tempReports = reportListQuery(1005, page, 100).get('data').get('reportData').get('reports').get('data')
    reportList.update([report.get('code') for report in tempReports])
    print(page)
    page += 1

counter = 0
for report in reportList:
    tempValues = Report(report, fight).getDamageEvents()

    for k in tempValues:
        for l in tempValues[k]:
            table[k][l] = table[k][l] + tempValues[k][l]
    counter += 1
    print(datetime.datetime.now(), counter)
    for i in range(89, 100):
        totalCasts = table[i][0] + table[i][25] + table[i][50] + table[i][75] + table[i][100]
        if totalCasts == 0:
            continue
        # calc excluding expected partials
        expectedResists = int(totalCasts * (1 - i/100))
        castSum = table[i][25] * 0.25 + table[i][50] * 0.5 + table[i][75] * 0.75 + table[i][100]
        excludingResists = totalCasts - expectedResists
        if excludingResists < castSum:
            excludingResists = castSum
        resultPercent = round(100 * (1 - castSum / excludingResists), 2)
        print('Hit%: {}, avg. mitigation excluding expected miss chance: {}%'.format(i, resultPercent))
        print('Hit%: {}, # of casts: {}, Resist: {}, 25% done: {}, 50% done: {}, 75% done: {}, 100% done: {}'.format(i,
                                                                                                                     totalCasts,
                                                                                                                     table[
                                                                                                                         i][
                                                                                                                         0],
                                                                                                                     table[
                                                                                                                         i][
                                                                                                                         25],
                                                                                                                     table[
                                                                                                                         i][
                                                                                                                         50],
                                                                                                                     table[
                                                                                                                         i][
                                                                                                                         75],
                                                                                                                     table[
                                                                                                                         i][
                                                                                                                         100]))
