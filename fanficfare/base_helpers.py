from __future__ import absolute_import
import re
import logging
logger = logging.getLogger(__name__)
import pkg_resources, json, io
import unicodedata


# Normalize word
def normalize_word(word):
    nfkd_normalized = unicodedata.normalize('NFKD', word)
    without_accents = "".join([c for c in nfkd_normalized if not unicodedata.combining(c)])
    return without_accents.lower().replace(" ", "")


# Load dictionary files
def get_mapping(language):
    cache_key = f"mapping_cache_{language}"
    if cache_key in globals():
        return globals()[cache_key]

    mapping = {}

    # Read JSON file from package
    with pkg_resources.resource_stream(__name__, f"dic_tags_{language}.json") as jsonfile:
        data = json.load(io.TextIOWrapper(jsonfile, encoding='utf-8'))
        for word, tag in data.items():
            normalized_word = normalize_word(word)
            if normalized_word not in mapping:
                mapping[normalized_word] = []
            else:
                logger.debug("Tag repetida %s", normalized_word)
            mapping[normalized_word].extend(tag)
        logger.debug("Loaded %d entries from %s dictionary", len(mapping), language)
    jsonfile.close()

    globals()[cache_key] = mapping
    return mapping


def get_characters():
    cache_key = "characters_cache"
    if cache_key in globals():
        return globals()[cache_key]
    
    characters = {}

    # Read JSON file from package
    with pkg_resources.resource_stream(__name__, "dic_characters.json") as jsonfile:
        data = json.load(io.TextIOWrapper(jsonfile, encoding='utf-8'))
        for word, tag in data.items():
            if word not in characters:
                characters[word] = []
            characters[word].append(tag)
        logger.debug("Loaded %d entries from characters dictionary", len(characters))
    jsonfile.close()

    characters = {re.compile(pattern, re.IGNORECASE): name for pattern, name in characters.items()}

    globals()[cache_key] = characters
    return characters


def get_weird_ships():
    cache_key = "weird_ships_cache"
    if cache_key in globals():
        return globals()[cache_key]
    
    weird_ships = {}

    # Read JSON file from package
    with pkg_resources.resource_stream(__name__, "dic_weird_shipnames.json") as jsonfile:
        data = json.load(io.TextIOWrapper(jsonfile, encoding='utf-8'))
        for word, tag in data.items():
            if word not in weird_ships:
                weird_ships[word] = []
            weird_ships[word].append(tag)
        logger.debug("Loaded %d entries from weird ships dictionary", len(weird_ships))
    jsonfile.close()

    weird_ships = {re.compile(pattern, re.IGNORECASE): name for pattern, name in weird_ships.items()}

    globals()[cache_key] = weird_ships
    return weird_ships


def get_relationships():
    cache_key = "relationships_cache"
    if cache_key in globals():
        return globals()[cache_key]
    
    relationships = {}

    # Read JSON file from package
    with pkg_resources.resource_stream(__name__, "dic_relationships.json") as jsonfile:
        data = json.load(io.TextIOWrapper(jsonfile, encoding='utf-8'))
        for word, tag in data.items():
            if word not in relationships:
                relationships[word] = []
            relationships[word].append(tag)
        logger.debug("Loaded %d entries from weird ships dictionary", len(relationships))
    jsonfile.close()

    relationships = {re.compile(pattern, re.IGNORECASE): name for pattern, name in relationships.items()}

    globals()[cache_key] = relationships
    return relationships


def get_pairings():
    cache_key = "pairings_cache"
    if cache_key in globals():
        return globals()[cache_key]
    
    pairings = {}

    # Read JSON file from package
    with pkg_resources.resource_stream(__name__, "dic_characters_to_ship.json") as jsonfile:
        data = json.load(io.TextIOWrapper(jsonfile, encoding='utf-8'))
        for word, tag in data.items():
            if word not in pairings:
                pairings[word] = tag
        logger.debug("Loaded %d entries from pairings dictionary", len(pairings))
    jsonfile.close()

    globals()[cache_key] = pairings
    return pairings


# Remove extra info from character names
def remove_extra_info(value):
    if value != "Original Character(s)":
        value = re.sub(r'\s*\((Naruto|Boruto)\)', '', value, flags=re.IGNORECASE)
        value = re.sub(r'^((mentions of)|mentioned|future|past|nice|birb|protective|wingwomen|boy|girl)!?\s*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\s*(-\s*)?(\(Naruto\)-centric|Friendship|Freeform|Character(\(s\)|s)?|mentions?|\(?mentioned\)?|\(\s*maybe\s*\))$', '', value, flags=re.IGNORECASE)
        value = value.strip()
    return value


# Character names
def normalize_character_name(tag):

    characters_dic = get_characters()

    save_tag = tag
    #Character match can search for just one name
    tag = re.match(r'^([^|]*)', remove_extra_info(tag)).group(1).strip()

    for pattern, character in characters_dic.items():
        match = pattern.match(tag)
        if match:
            character_name = character[0]
            tag = None
            break
    else:
        character_name = None
        tag = save_tag

    return character_name, tag


# Relationships
def normalize_ship (value, error = False):

    # check if relationship is in fact a tag
    def search_relationship_tag(tag):
    
        relationships_dic = get_relationships()

        for pattern, relationship in relationships_dic.items():
            match = pattern.match(tag)
            if match:
                ship = relationship[0]
                return ship


    # search for wrong shipnames or special cases, not covered by the generic search
    def search_weird_shipnames(ship):

        characters = []
        weird_ships_dic = get_weird_ships()

        for pattern, weird_ship in weird_ships_dic.items():
            match = pattern.match(ship)
            if match:
                characters = weird_ship[0]
                break
        
        if characters != []:
            return characters, True
        else:
            return [], True


    def search_characters(characters_search, error = False):
        if len(characters_search) < 2:
            # Not enough characters to search
            return [], True
        
        for character in characters_search:
            character_found = normalize_character_name(character.strip())[0]
            if character_found == None:
                # Error
                return [], True
            else:
                characters.append(character_found)

        return characters, error
    

    def character_sort_key(character):
        pattern = r'original\s+(?:\w+\s+)?character(?:s)?'  # Regular expression pattern to match variations
        if re.search(pattern, character, re.IGNORECASE):
            return 1  # Sort "Original Character(s)" or its variations as the last element
        else:
            return 0  # Sort other elements as normal


    value = value.lower()

    ship = tag = None
    characters_search = []
    characters = []
    romance = True

    # Check if pairing is a tag
    tag_search = search_relationship_tag(value)
    if tag_search != None:
        return tag_search, None, None

    # Remove extra information from value
    value = re.sub(r'\s*(-\s*)?freeform$', '', value, flags=re.IGNORECASE)
    value = re.sub(r'^(menção!?|mencion|trisal|implied|mentioned|mentions(\s*of)?|slight|past|married|(un)?requited|one(\s*|-)?sided|minor|some|background|eventual|established|light|hints(\s*of)?)\s*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\s*(-\s*)?(relationship|friendship|\(?minor\)?|\(?one(\s*|-)?sided\)?|à un seul côté|\(?implied\)?|\(?mentionn?(ed)?\)?|hints|past|mencion|\(?background\)?|\?)?$', '', value, flags=re.IGNORECASE)

    # Check if pairing is a tag
    # Second time because it can be affected for extra tags
    tag_search = search_relationship_tag(value)
    if tag_search != None:
        return tag_search, None, None

    # Check if pairing is a weird shipname
    characters_search, romance = search_weird_shipnames(value)
    if characters_search != []:
        characters, error = search_characters(characters_search)

    if not characters:
        # It can be a friendship (Naruto & Hinata) or a romantic relationship (Naruto/Hinata)
        if '&' in value:
            characters_search = value.split("&")
            characters, error = search_characters(characters_search)
            romance = False
        elif 'and' in value:
            characters_search = value.split("and")
            characters, error = search_characters(characters_search)
            romance = False
        # Ships can be informed in different formats
        # First - Character1/Character2
        elif '/' in value:
            characters_search = value.split("/")
            characters, error = search_characters(characters_search)
        # Second - Character1xCharacter2
        elif 'x' in value:
            characters_search = value.split("x")
            characters, error = search_characters(characters_search)
        elif '×' in value:
            characters_search = value.split("×")
            characters, error = search_characters(characters_search)
        # Third - Char1Char2
        else:
            i = 0
            value = remove_extra_info(value)
            while i < len(value):
                for j in range(i+1, len(value)+1):
                    token = value[i:j]
                    character_found = normalize_character_name(token.strip())[0]
                    if character_found:
                        characters.append(character_found)
                        i = j  # continue search from next character
                        break
                else:
                    error = True
                    break

    characters = list(set(characters))
    characters = sorted(characters)
    characters.sort(key=character_sort_key)
 
    if len(characters) < 2:
        # Not enough characters found
        error = True

    if error == True:
        return None, [], None
    else:
        characters = [char for char in characters if char]
        if len(characters) < 2:
            return [], characters, []
        if romance == True:
            ship = "/".join([remove_extra_info(name) for name in characters])
            if "Original Character(s)" not in characters:
                tag = get_pairings().get(ship)
                if tag == None:
                    logger.debug("Pairing not found: %s", ship)
                    tag = '?.'+ship
        else:
            ship = " & ".join([remove_extra_info(name) for name in characters])
   
    return ship, characters, tag


# Tags
def normalize_tag (tag, mapping):

    translation = []
    tags = []
    characters = []
    relationship = None

    if mapping:
        translation = mapping.get(normalize_word(tag))
        
    #No matter the language, if translation is empty, it can be a character or a ship
    if not translation:
        #Search for ships first
        relationship, characters, tag_ship = normalize_ship(tag)
        if relationship != None:
            if tag_ship:
                tags.append(tag_ship)
        #Not a ship, it can be a character
        else:
            character = normalize_character_name(tag)[0]
            if character != None:
                characters.append(character)

    if relationship == None and not characters:
        if not translation:
            logger.debug('Tag not found: %s', tag)
            tags.append('?.'+tag)
        else:
            if translation[0] != '':
                tags = translation

    return tags, characters, relationship