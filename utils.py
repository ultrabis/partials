import requests
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


gearData = {
    21186: 1,  # Rockfury Bracers
    19682: 2,  # Bloodvine Vest
    21585: 1,  # Dark Storm Gauntlets
    19683: 1,  # Bloodvine Leggings
    19684: 1,  # Bloodvine Boots
    21838: 2,  # Garb of Royal Ascension
    21337: 1,  # Doomcaller's Circlet
    22267: 1,  # Spellweaver's Turban
    21335: 1,  # Doomcaller's Mantle
    21344: 1,  # Enigma Boots
    19374: 1,  # Bracers of Arcane Accuracy
    21347: 1,  # Enigma Circlet
    21348: 1,  # Tiara of the Oracle
    20686: 1,  # Abyssal Cloth Amice
    19929: 1,  # Bloodtinged Gloves
    11662: 1,  # Ban'thok Sash
    19388: 2,  # Angelista's Grasp
    22074: 1,  # Deathmist Mask
    19438: 1,  # Ringo's Blizzard Boots
    19999: 2,  # Bloodvine Goggles
    22496: 1,  # Frostfire Robe
    22498: 1,  # Frostfire Circlet
    20034: 1,  # Zandalar Illusionist's Robe
    20033: 1,  # Zandalar Demoniac's Robe
    16795: 1,  # Arcanist Crown
    22066: 1,  # Sorcerer's Gloves
    22506: 1,  # Plagueheart Circlet
    22507: 1,  # Plagueheart Shoulderpads
    22504: 1,  # Plagueheart Robe
    23291: 1,  # Knight-Lieutenant's Silk Walkers
    22077: 1,  # Deathmist Wraps
    16809: 1,  # Felheart Robes
    22502: 1,  # Frostfire Belt
    13956: 1,  # Clutch of Andros
    22860: 1,  # Blood Guard's Silk Walkers
    22497: 1,  # Frostfire Leggings
    16437: 1,  # Marshal's Silk Footwraps
    22231: 1,  # Kayser's Boots of Precision
    16539: 1,  # General's Silk Boots
    21273: 2,  # Blessed Qiraji Acolyte Staff
    22589: 2,  # Atiesh, Greatstaff of the Guardian
    21452: 1,  # Staff of the Ruins
    20536: 1,  # Soul Harvester
    22335: 1,  # Lord Valthalak's Staff of Command
    22807: 1,  # Wraith Blade
    19884: 2,  # Jin'do's Judgement
    21413: 1,  # Blade of Vaulted Secrets
    22800: 2,  # Brimstone Staff
    22820: 1,  # Wand of Fates
    22403: 1,  # Diana's Pearl Necklace
    12103: 1,  # Star of Mystaria
    19876: 1,  # Soul Corrupter's Necklace
    21709: 1,  # Ring of the Fallen God
    21417: 1,  # Ring of Unspoken Names
    19403: 1,  # Band of Forced Concentration
    22339: 1,  # Rune Band of Wizardry
    19893: 1,  # Zanzil's Seal
    19905: 1,  # Zanzil's Band
    23025: 1,  # Seal of the Damned
    23031: 1,  # Band of the Inevitable
    19379: 2,  # Neltharion's Tear
    22731: 1,  # Cloak of the Devoured
    19857: 1,  # Cloak of Consumption
    22330: 1,  # Shroud of Arcane Mastery
    23050: 1,  # Cloak of the Necropolis
}

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
