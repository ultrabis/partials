import sys, os, enum, time, json, requests
from jsonpath_ng import jsonpath, parse
from datetime import datetime
from variables import apiUrl, headers

# these values match the `type` field in WCL's `abilities()`
class MagicSchool(enum.Enum):
    Invalid = 0
    Physical = 1
    Holy = 2
    Fire = 4
    Nature = 8
    Frost = 16
    Shadow = 32
    Arcane = 64

def fetchGraphQL(query):
    try:
        response = requests.post(
            apiUrl, json={'query': query}, headers=headers, timeout=60).json()
        if response.get('errors'):
            return None
        else:
            return response
    except Exception as e:
        print(e)
        print('Sleeping', datetime.now())
        time.sleep(60)
        fetchGraphQL(query)

def fetchAbilityEvents(reportCode: str, encounterID: int, targetID: int, abilityID: int, abilityTypes: list = []):
    typeString = ''
    abilityCount = len(abilityTypes)
    if abilityCount > 0:
        typeString = ' and type in ('
        i = 1
        for abilityType in abilityTypes:
            typeString += '\\"' + abilityType + '\\"'
            if i < abilityCount: 
                typeString += ','
            else:
                typeString += ')'
            i += 1

    query = '''
    {{
      reportData {{
        report(code: "{reportCode}") {{
          events(dataType: All, startTime: 0, endTime: 999999999999, encounterID: {encounterID}, filterExpression: "ability.id = {abilityID}{typeString}") {{
            nextPageTimestamp
            data
          }}
        }}
      }}
    }}
    '''.format(reportCode=reportCode, encounterID=encounterID, abilityID=abilityID, typeString=typeString)
    
    return list(filter(lambda event: event.get('targetID') == targetID, [
        match.value for match in 
            parse('$.data.reportData.report.events.data[*]').find(fetchGraphQL(query))
    ]))

def fetchActors(reportCode: str) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportCode}") {{
                masterData(translate: false) {{
                    actors {{
                        id
                        name
                        type
                        subType
                        icon
                        gameID
                    }}
                }}
            }}
        }}
    }}
    '''.format(reportCode=reportCode)
    #print('query: ' + query)
    return fetchGraphQL(query)

def fetchPlayers(reportCode: str) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportCode}") {{
                masterData(translate: false) {{
                    actors(type: "Player") {{
                        id
                        name
                        type
                        subType
                        icon
                        gameID
                    }}
                }}
            }}
        }}
    }}
    '''.format(reportCode=reportCode)
    #print('query: ' + query)
    return fetchGraphQL(query)

def fetchReportSummary(reportCode: str):
    query = '''
    {{
        reportData {{
            report(code: "{reportCode}") {{
                masterData(translate: false) {{
                    actors(type: "Player") {{
                        icon
                    }},
                    abilities {{
                        gameID
                        type
                    }}
                }}
            }}
        }}
    }}
    '''.format(reportCode=reportCode)
    response = fetchGraphQL(query)

    abilities = [
        match.value for match in 
          parse('$.data.reportData.report.masterData.abilities[*]').find(response)
    ]

    actors = [
        match.value for match in 
          parse('$.data.reportData.report.masterData.actors[*]').find(response)
    ]

    # filter out stuff like melee and add to spells list
    spellIDsSet = set()
    for ability in abilities:
        if int(ability.get('type')) > 2: 
            spellIDsSet.add(ability.get('gameID'))

    iconSet = set()
    for actor in actors:
        if actor.get('icon') != 'Unknown-null' and actor.get('icon') != 'Unknown':
            iconSet.add(actor.get('icon'))

    return {
        'code': reportCode,
        'spellIDs': list(spellIDsSet),
        'icons': list(iconSet)    
    }    

def fetchSpellIDs(reportCode: str) -> dict:
    # fetch abilities
    query = '''
    {{
        reportData {{
            report(code: "{reportCode}") {{
                masterData(translate: false) {{
                    abilities {{
                        gameID
                        name
                        type
                    }}
                }}
            }}
        }}
    }}
    '''.format(reportCode=reportCode)
    abilities = [
        match.value for match in 
          parse('$.data.reportData.report.masterData.abilities[*]').find(fetchGraphQL(query))
    ]

    # filter out stuff like melee and add to spells list
    spellIDs = []
    for ability in abilities:
        if int(ability.get('type')) > 2: 
            spellIDs.append(ability.get('gameID'))
    return spellIDs

def fetchGear(url: str, encounterID: int) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportUrl}")  {{
                events(
                    dataType: CombatantInfo, 
                    endTime: 99999999999, 
                    startTime: 0,
                    encounterID: {encounterID}
                ) {{
                    data
                    nextPageTimestamp
                }}
            }}
        }}
    }}
    '''.format(reportUrl=url, encounterID=encounterID)
    return fetchGraphQL(query)


def fetchDamageEvents(reportCode: str, encounterID, spec: str, abilityQuery: str) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportCode}") {{
                events(
                    dataType: DamageDone,
                    startTime: 0,
                    endTime: 999999999999,
                    encounterID: {encounterID},
                    filterExpression: "source.spec='{spec}' and {abilityQuery}"
                ) {{
                    nextPageTimestamp
                    data
                }}
            }}
        }}
    }}
    '''.format(reportCode=reportCode, encounterID=encounterID, spec=spec, abilityQuery=abilityQuery)
    #print(query)
    return fetchGraphQL(query)


def fetchReportList(zone: int, page: int, limit: int = 100) -> dict:
    query = """query {
      reportData {
        reports(zoneID: """ + str(zone) + """, limit: """ + str(limit) + """, page: """ + str(page) + """) {
          data {
            code
          }
          from
          to
          has_more_pages
        }
      }
    }"""
    return fetchGraphQL(query)


enchantData = {
    2588: 1,  # Mage ZG enchant
}

zanzilRingSet = [19893, 19905]

