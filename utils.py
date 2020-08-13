import requests
import json
from datetime import datetime
import time
from variables import apiUrl, headers

#  "icon": "Mage-Frost" is frost spec
#  "icon": "Mage" is fire spec

#  Add id 'test' to wowhead gear search results and run, returns python formatted dict of item hit values
#  node for hitValues is 9 for armor, 8 for weapons
'''
let table = document.getElementById('test')
let childred = table.getElementsByClassName('listview-row')
let finalStr = ""
for (let row of childred) {
    let nodes = row.childNodes
    let childA = nodes[2].getElementsByTagName('a')[0]
    let name = childA.innerHTML
    let url = childA.href
    url = url.replace(/\D+/, "").replace(/\D+/, "")
    let hitValue = nodes[9].innerHTML
    finalStr += url + ': ' + hitValue + ', #  ' + name + "\n"
}
console.log(finalStr)
'''


def fetchGraphQL(query):
    try:
        response = requests.post(apiUrl, json={'query': query}, headers=headers).json()
        if response.get('errors'):
            return None
        else:
            return response
    except Exception as e:
        print(e)
        print('Sleeping', datetime.now())
        time.sleep(60)
        fetchGraphQL(query)


def getActors(url: str) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportUrl}") {{
                masterData(translate: true) {{
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
    '''.format(reportUrl=url)
    return fetchGraphQL(query)


def getGear(url: str, encounterID: int) -> dict:
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


def getDamageEvents(url: str, encounterID, abilityQuery: str) -> dict:
    query = '''
    {{
        reportData {{
            report(code: "{reportUrl}") {{
                events(
                    dataType: DamageDone,
                    startTime: 0,
                    endTime: 999999999999,
                    encounterID: {encounterID},
                    filterExpression: "source.spec='Fire' and {abilityQuery}"
                ) {{
                    nextPageTimestamp
                    data
                }}
            }}
        }}
    }}
    '''.format(reportUrl=url, encounterID=encounterID, abilityQuery=abilityQuery)
    return fetchGraphQL(query)


def reportListQuery(zone: int, page: int, limit: int = 100) -> dict:
    query = """query {
      reportData {
        reports(zoneID: """ + str(zone) + """, limit: """ + str(limit) + """, page: """ + str(page) + """) {
          data {
            code
          }
          from
          to
        }
      }
    }"""
    return fetchGraphQL(query)


def getItemJSON(id: int):
    with open('item.json') as json_data:
        data = json.load(json_data)

    for item in data:
        if item['id'] == id:
            return item

    return None

def getSpellHitFromJSON(id: int):
  itemJSON = getItemJSON(id)
  if itemJSON != None:
    if 'spellHit' in itemJSON:
        #print('item ' + str(id) + ' has ' + str(itemJSON['spellHit']) + ' spell hit')
        return itemJSON['spellHit']
  return 0

def getSpellPenFromJSON(id: int):
  itemJSON = getItemJSON(id)
  if itemJSON != None:
    if 'spellPenetration' in itemJSON:
        #print('item ' + str(id) + ' has ' + str(itemJSON['spellPenetration']) + ' spell pen')
        return itemJSON['spellPenetration']
  return 0

enchantData = {
    2588: 1,  # Mage ZG enchant
}

zanzilRingSet = [19893, 19905]

hitTypes = {
    1: 1,  # hitType = 1, hit
    2: 1.5,  # hitType = 2, crit
    14: 0,  # hitType = 14, resist
    16: 1,  # hitType = 16, partial hit
    17: 1.5  # hitType = 17, partial crit
}

'''
"encounters": [
      {
        "id": 709,
        "name": "The Prophet Skeram"
      },
      {
        "id": 710,
        "name": "Silithid Royalty"
      },
      {
        "id": 711,
        "name": "Battleguard Sartura"
      },
      {
        "id": 712,
        "name": "Fankriss the Unyielding"
      },
      {
        "id": 713,
        "name": "Viscidus"
      },
      {
        "id": 714,
        "name": "Princess Huhuran"
      },
      {
        "id": 715,
        "name": "Twin Emperors"
      },
      {
        "id": 716,
        "name": "Ouro"
      },
      {
        "id": 717,
        "name": "C'thun"
      }
    ],
'''
