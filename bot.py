#!/usr/bin/env python3

import math
from traceback import print_exc
from typing import Optional, Dict, List, Union, Tuple

import numpy
from tqdm import tqdm
import time
import json

import requests
from bs4 import BeautifulSoup

import urllib
from io import BytesIO
from websocket import create_connection
from websocket import WebSocketConnectionClosedException
from PIL import ImageColor
from PIL import Image
import numpy as np
import random

# Behold, the dirtiest code I ever wrote
# This hacky hack serves as a bridge for urllib in Python 2 and Python 3
try:
    urllib.urlopen
except AttributeError as err:
    urllib.urlopen = urllib.request.urlopen

DAY = 86400
HOUR = 3600
VERSION = "0.5.2"

CANVAS_IDS     = [   0,    1,    2,    3]
CANVAS_XOFFSET = [   0, 1000,    0, 1000]
CANVAS_YOFFSET = [   0,    0, 1000, 1000]
CANVAS_XSIZE   = [1000, 1000, 1000, 1000]
CANVAS_YSIZE   = [1000, 1000, 1000, 1000]
CanvasIdMap = None

max_x = int(max(xoffset+xsize for xoffset, xsize in zip(CANVAS_XOFFSET, CANVAS_XSIZE)))
max_y = int(max(yoffset+ysize for yoffset, ysize in zip(CANVAS_YOFFSET, CANVAS_YSIZE)))
currentData = np.zeros([max_x, max_y, 4], dtype=np.uint8) # should hold current state of canvas at all times

SET_PIXEL_QUERY = \
    """mutation setPixel($input: ActInput!) {
  act(input: $input) {
    data {
      ... on BasicMessage {
        id
        data {
          ... on GetUserCooldownResponseMessageData {
            nextAvailablePixelTimestamp
            __typename
          }
          ... on SetPixelResponseMessageData {
            timestamp
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

COLOR_MAP = {
    "#6D001AFF":  0,
    "#BE0039FF":  1,
    "#FF4500FF":  2,
    "#FFA800FF":  3,
    "#FFD635FF":  4,
    "#FFF8B8FF":  5,
    "#00A368FF":  6,
    "#00CC78FF":  7,
    "#7EED56FF":  8,
    "#00756FFF":  9,
    "#009EAAFF": 10,
    "#00CCC0FF": 11,
    "#2450A4FF": 12,
    "#3690EAFF": 13,
    "#51E9F4FF": 14,
    "#493AC1FF": 15,
    "#6A5CFFFF": 16,
    "#94B3FFFF": 17,
    "#811E9FFF": 18,
    "#B44AC0FF": 19,
    "#E4ABFFFF": 20,
    "#DE107FFF": 21,
    "#FF3881FF": 22,
    "#FF99AAFF": 23,
    "#6D482FFF": 24,
    "#9C6926FF": 25,
    "#FFB470FF": 26,
    "#000000FF": 27,
    "#515252FF": 28,
    "#898D90FF": 29,
    "#D4D7D9FF": 30,
    "#FFFFFFFF": 31,
}
COLOR_NAMES_MAP = {
    "#6D001AFF": 'Burgundy',
    "#BE0039FF": 'Dark Red',
    "#FF4500FF": 'Red',
    "#FFA800FF": 'Orange',
    "#FFD635FF": 'Yellow',
    "#FFF8B8FF": 'Pale Yellow',
    "#00A368FF": 'Dark Green',
    "#00CC78FF": 'Green',
    "#7EED56FF": 'Light Green',
    "#00756FFF": 'Dark Teal',
    "#009EAAFF": 'Teal',
    "#00CCC0FF": 'Light Teal',
    "#2450A4FF": 'Dark Blue',
    "#3690EAFF": 'Blue',
    "#51E9F4FF": 'Light Blue',
    "#493AC1FF": 'Indigo',
    "#6A5CFFFF": 'Periwinkle',
    "#94B3FFFF": 'Lavender',
    "#811E9FFF": 'Dark Purple',
    "#B44AC0FF": 'Purple',
    "#E4ABFFFF": 'Pale Purple',
    "#DE107FFF": 'Magenta',
    "#FF3881FF": 'Pink',
    "#FF99AAFF": 'Light Pink',
    "#6D482FFF": 'Dark Brown',
    "#9C6926FF": 'Brown',
    "#FFB470FF": 'Biege',
    "#000000FF": 'Black',
    "#515252FF": 'Dark Grey',
    "#898D90FF": 'Grey',
    "#D4D7D9FF": 'Light Grey',
    "#FFFFFFFF": 'White',
}

rgb_colors_array = []

def init_rgb_colors_array():
    global rgb_colors_array
    
    # generate array of available rgb colors we can use
    for color_hex, color_index in COLOR_MAP.items():
        rgb_array = ImageColor.getcolor(color_hex, "RGBA")
        rgb_colors_array.append(rgb_array)


init_rgb_colors_array()

def image_to_npy(img):
    return np.asarray(img).transpose((1, 0, 2))


rPlaceTemplatesGithubLfs = True
rPlaceTemplateBaseUrl = "https://media.githubusercontent.com/media/r-ainbowroad/minimap/d/main" if rPlaceTemplatesGithubLfs else "https://raw.githubusercontent.com/r-ainbowroad/minimap/d/main"

def getRPlaceTemplateUrl(templateName, ttype):
    return f'{rPlaceTemplateBaseUrl}/{templateName}/{ttype}.png'


rPlaceTemplateNames = []
rPlaceTemplates = {}
def addRPlaceTemplate(templateName, options):
    rPlaceTemplates[templateName] = {
        'canvasUrl': getRPlaceTemplateUrl(templateName, "canvas"),
        'botUrl'   : getRPlaceTemplateUrl(templateName, "bot" ) if options['bot' ] else None,
        'maskUrl'  : getRPlaceTemplateUrl(templateName, "mask") if options['mask'] else None,
    }
    rPlaceTemplateNames.append(templateName)


addRPlaceTemplate("mlp"         , {'bot': True, 'mask': True})
addRPlaceTemplate("r-ainbowroad", {'bot': True, 'mask': True})
addRPlaceTemplate("spain"       , {'bot': True, 'mask': True})
addRPlaceTemplate("phoenixmc"   , {'bot': True, 'mask': True})

# globals
rPlaceTemplateName: Optional[str] = None
rPlaceTemplate: Optional[dict] = None
maskData: Optional[np.ndarray] = None
templateData: Optional[np.ndarray] = None
rPlaceMask: Optional[np.ndarray] = None

def setRPlaceTemplate(templateName):
    global rPlaceTemplateName
    global rPlaceTemplate
    template = rPlaceTemplates.get(templateName, None)
    if template is None:
        print("Invalid /r/place template name:", templateName)
        print(f"Must be one of {rPlaceTemplates.keys()}")
        return
    
    rPlaceTemplateName = templateName
    rPlaceTemplate = template


# Fetch template, returns a Promise<Uint8Array>, on error returns the response object
def fetchTemplate(url):
    # return unsignedInt8Array[W, H, C] of the URL
    im = urllib.urlopen(f'{url}?t={time.time()}').read()# load raw file
    im = image_to_npy(Image.open(BytesIO(im)).convert("RGBA"))# raw -> intMatrix([W, H, (RGBA)])
    assert im.dtype == 'uint8', f'got dtype {im.dtype}, expected uint8'
    assert im.shape[2] == 4, f'got {im.shape[2]} color channels, expected 4 (RGBA)'
    return im


def updateTemplate():
    global templateData
    global maskData
    rPlaceTemplateUrl = rPlaceTemplate['botUrl'] if rPlaceTemplate['botUrl'] is not None else rPlaceTemplate['canvasUrl']
    
    try:
        templateData = fetchTemplate(rPlaceTemplateUrl)# [W, H, (RGBA)]
    except Exception as err:
        print("Error updating template")
        raise err
    
    # Also update mask if needed
    maskData = np.zeros(templateData.shape, dtype=numpy.uint8)
    if rPlaceTemplate['maskUrl'] is not None:
        try:
            submask = fetchTemplate(rPlaceTemplate['maskUrl'])# [W, H, (RGBA)]
            maskData[:submask.shape[0], :submask.shape[1]] = submask
            
            #loadMask()
        except Exception as err:
            print_exc()
            print("Error updating mask:\n", err)


#
# Pick a pixel from a list of buckets
#
# The `position` argument is the position in the virtual pool to be selected.  See the
# docs for `selectRandomPixelWeighted` for information on what this is hand how it
# works
#
# @param {Map<number, [number, number][]>} buckets
# @param {number} position
# @return {[number, number]}
#
def pickFromBuckets(buckets: Dict[int, List], position):
    # All of the buckets, sorted in order from highest priority to lowest priority
    orderedBuckets = [*buckets.items()] # Convert map to array of tuples
    orderedBuckets = sorted(orderedBuckets, key=lambda x: x[0]) # Order by key (priority) ASC
    orderedBuckets = reversed(orderedBuckets) # Order by key (priority) DESC
    orderedBuckets = [l for k, l in orderedBuckets] # Drop the priority, leaving an array of buckets
    
    # list[list[(x: int, y: int)]], inside each bucket is a [x, y] coordinate.
    # Each bucket corresponds to a different prority level.
    
    # Select the position'th element from the buckets
    for bucket in orderedBuckets:
        if len(bucket) <= position:
            position -= len(bucket)
        else:
            return bucket[position]
    
    # If for some reason this breaks, just return a random pixel from the largest bucket
    largestBucket = orderedBuckets[orderedBuckets.index(max(len(b) for b in orderedBuckets))]
    return random.choice(largestBucket)


FOCUS_AREA_SIZE = 75
#
# Select a random pixel weighted by the mask.
#
# The selection algorithm works as follows:
# - Pixels are grouped into buckets based on the mask
# - A virtual pool of {FOCUS_AREA_SIZE} of the highest priority pixels is defined.
#   - If the highest priority bucket contains fewer than FOCUS_AREA_SIZE pixels, the
#     next highest bucket is pulled from, and so on until the $FOCUS_AREA_SIZE pixel
#     threshold is met.
# - A pixel is picked from this virtual pool without any weighting
#
# This algorithm avoids the collision dangers of only using one bucket, while requiring
# no delays, and ensures that the size of the selection pool is always constant.
#
# Another way of looking at this:
# - If >= 75 pixels are missing from the crystal, 100% of the bots will be working there
# - If 50 pixels are missing from the crystal, 67% of the bots will be working there
# - If 25 pixels are missing from the crystal, 33% of the bots will be working there
#
# @param {[number, number][]} diff
# @return {[number, number]}
#
def selectRandomPixelWeighted(diff):
    # Build the buckets
    buckets = {}
    totalAvailablePixels = 0
    for coords in diff:
        (x, y) = coords
        maskValue = int(maskData[x, y, 1]) # brightness of mask coresponds to priority
        if maskValue == 0: continue # zero priority = ignore
        
        totalAvailablePixels += 1
        bucket = buckets.get(maskValue, None)
        if bucket is None:
            buckets[maskValue] = [coords]
        else:
            bucket.append(coords)
    
    # Select from buckets
    # Position represents the index in the virtual pool that we are selecting
    position = math.floor(random.random() * min([FOCUS_AREA_SIZE, totalAvailablePixels]))
    pixel = pickFromBuckets(buckets, position)
    return pixel

#
# Select a random pixel.
#
# @param {[number, number][]} diff
# @return {{x: number, y: number}}
#
def selectRandomPixel(diff):
    if rPlaceTemplate['maskUrl'] is None or maskData is None:
        pixel = random.choice(diff)
    else:
        pixel = selectRandomPixelWeighted(diff)
    
    (x, y) = pixel
    return x, y


def rgb_to_hex(rgb):
    return ("#%02x%02x%02x%02x" % rgb).upper()


# function to find the closest rgb color from palette to a target rgb color
def closest_color(target_rgb, rgb_colors_array_in):
    r, g, b, a = target_rgb
    color_diffs = []
    for color in rgb_colors_array_in:
        cr, cg, cb, _ = color
        color_diff = math.sqrt((float(r) - cr) ** 2 + (float(g) - cg) ** 2 + (float(b) - cb) ** 2)
        color_diffs.append((color_diff, color))
    return min(color_diffs, key=lambda x: x[0])[1]

def getDiff(currentData, templateData):
    assert currentData.shape == templateData.shape, f'got {currentData.shape} and {templateData.shape} for currentData and templateData shapes'
    assert currentData.shape[2] == 4, f'got {currentData.shape[2]} color channels, expected 4'
    # [W, H, (RGBA)], [W, H, (RGBA)]
    diff = []
    
    for x in range(currentData.shape[0]):
        for y in range(currentData.shape[1]):
            curr_pixel = currentData[x, y]# [R,G,B,A]
            temp_pixel = templateData[x, y]# [R,G,B,A]
            opacity = temp_pixel[3]
            if opacity == 0.0:
                continue
            if np.not_equal(curr_pixel[:3], temp_pixel[:3]).any():
                diff.append([x, y])
    print(f'Total Damage: {len(diff) / (templateData[:, :, 3] != 0.0).sum():.1%}', len(diff), (templateData[:, :, 3] != 0.0).sum())
    return diff


class Placer:
    REDDIT_URL = "https://www.reddit.com"
    LOGIN_URL = REDDIT_URL + "/login"
    INITIAL_HEADERS = {
        "accept"            :
            "*/*",
        "accept-encoding"   :
            "gzip, deflate, br",
        "accept-language"   :
            "en-US,en;q=0.9",
        "content-type"      :
            "application/x-www-form-urlencoded",
        "origin"            :
            REDDIT_URL,
        "sec-ch-ua"         :
            '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile"  :
            "?0",
        "sec-ch-ua-platform":
            '"Windows"',
        "sec-fetch-dest"    :
            "empty",
        "sec-fetch-mode"    :
            "cors",
        "sec-fetch-site"    :
            "same-origin",
        "user-agent"        :
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36"
    }
    
    def __init__(self):
        self.client = requests.session()
        self.client.headers.update(self.INITIAL_HEADERS)
        
        self.token = None
    
    def login(self, username: str, password: str):
        # get the csrf token
        r = self.client.get(self.LOGIN_URL)
        time.sleep(1)
        
        login_get_soup = BeautifulSoup(r.content, "html.parser")
        csrf_token = login_get_soup.find("input",
                                         {"name": "csrf_token"})["value"]
        
        # authenticate
        r = self.client.post(self.LOGIN_URL,
                             data={
                                 "username"  : username,
                                 "password"  : password,
                                 "dest"      : self.REDDIT_URL,
                                 "csrf_token": csrf_token
                             })
        time.sleep(1)
        
        print(r.content)
        assert r.status_code == 200
        
        # get the new access token
        r = self.client.get(self.REDDIT_URL)
        data_str = BeautifulSoup(r.content, features="html5lib").find(
            "script", {
                "id": "data"
            }).contents[0][len("window.__r = "):-1]
        data = json.loads(data_str)
        self.token = data["user"]["session"]["accessToken"]
    
    def get_board(self):
        print("Getting board(s)")
        boardimg = [None, None, None, None]
        ws = create_connection("wss://gql-realtime-2.reddit.com/query", origin="https://hot-potato.reddit.com")
        ws.send(
            json.dumps({
                "type"   : "connection_init",
                "payload": {
                    "Authorization": "Bearer " + self.token
                },
            }))
        ws.recv()
        
        ws.send(
            json.dumps({
                "id"     : "1",
                "type"   : "start",
                "payload": {
                    "variables"    : {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category" : "CONFIG",
                            }
                        }
                    },
                    "extensions"   : {},
                    "operationName":
                        "configuration",
                    "query"        :
                        "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on ConfigurationMessageData {\n          colorPalette {\n            colors {\n              hex\n              index\n              __typename\n            }\n            __typename\n          }\n          canvasConfigurations {\n            index\n            dx\n            dy\n            __typename\n          }\n          canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        ws.recv()
        
        ws.send(
            json.dumps({
                "id"     : "2",
                "type"   : "start",
                "payload": {
                    "variables"    : {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category" : "CANVAS",
                                "tag"      : "0",
                            }
                        }
                    },
                    "extensions"   : {},
                    "operationName":
                        "replace",
                    "query"        :
                        "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        
        while boardimg[0] == None:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    print("Got 1st canvas: {}".format(msg["data"]["name"]))
                    boardimg[0] = BytesIO(urllib.urlopen(msg["data"]["name"]).read())
                    break

        ws.send(
            json.dumps({
                "id"     : "2",
                "type"   : "start",
                "payload": {
                    "variables"    : {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category" : "CANVAS",
                                "tag"      : "1",
                            }
                        }
                    },
                    "extensions"   : {},
                    "operationName":
                        "replace",
                    "query"        :
                        "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        
        while boardimg[1] == None:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    print("Got 2nd canvas: {}".format(msg["data"]["name"]))
                    boardimg[1] = BytesIO(requests.get(msg["data"]["name"], stream=True).content)
                    break

        ws.send(
            json.dumps({
                "id"     : "2",
                "type"   : "start",
                "payload": {
                    "variables"    : {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category" : "CANVAS",
                                "tag"      : "2",
                            }
                        }
                    },
                    "extensions"   : {},
                    "operationName":
                        "replace",
                    "query"        :
                        "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        
        while boardimg[2] == None:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    print("Got 3rd canvas: {}".format(msg["data"]["name"]))
                    boardimg[2] = BytesIO(requests.get(msg["data"]["name"], stream=True).content)
                    break

        ws.send(
            json.dumps({
                "id"     : "2",
                "type"   : "start",
                "payload": {
                    "variables"    : {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category" : "CANVAS",
                                "tag"      : "3",
                            }
                        }
                    },
                    "extensions"   : {},
                    "operationName":
                        "replace",
                    "query"        :
                        "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        
        while boardimg[3] == None:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    print("Got 4th canvas: {}".format(msg["data"]["name"]))
                    boardimg[3] = BytesIO(requests.get(msg["data"]["name"], stream=True).content)
                    break
        
        ws.close()
                
        return boardimg
    
    def place_tile(self, canvas: int, x: int, y: int, color: int):
        headers = self.INITIAL_HEADERS.copy()
        headers.update({
            "apollographql-client-name"   : "mona-lisa",
            "apollographql-client-version": "0.0.1",
            "content-type"                : "application/json",
            "origin"                      : "https://hot-potato.reddit.com",
            "referer"                     : "https://hot-potato.reddit.com/",
            "sec-fetch-site"              : "same-site",
            "authorization"               : "Bearer " + self.token
        })
        
        r = requests.post("https://gql-realtime-2.reddit.com/query",
                          json={
                              "operationName": "setPixel",
                              "query"        : SET_PIXEL_QUERY,
                              "variables"    : {
                                  "input": {
                                      "PixelMessageData": {
                                          "canvasIndex": canvas,
                                          "colorIndex" : color,
                                          "coordinate" : {
                                              "x": x,
                                              "y": y
                                          }
                                      },
                                      "actionName"      : "r/replace:set_pixel"
                                  }
                              }
                          },
                          headers=headers)
        
        if r.json()["data"] is None:
            try:
                waitTimems = math.floor(
                    r.json()["errors"][0]["extensions"]["nextAvailablePixelTs"])
                print("placing failed: rate limited")
            except IndexError:
                waitTimems = 10000
        else:
            waitTimems = math.floor(r.json()["data"]["act"]["data"][0]["data"]
                                  ["nextAvailablePixelTimestamp"])
            print("placing succeeded")
        
        return waitTimems / 1000


def AbsCoordToCanvasCoord(x: int, y: int):
    global CanvasIdMap
    if CanvasIdMap is None:
        max_x = int(max(xoffset+xsize for xoffset, xsize in zip(CANVAS_XOFFSET, CANVAS_XSIZE)))
        max_y = int(max(yoffset+ysize for yoffset, ysize in zip(CANVAS_YOFFSET, CANVAS_YSIZE)))
        CanvasIdMap = np.zeros([max_x, max_y], dtype=np.uint8)
        for canvas_id, xoffset, yoffset, xsize, ysize in zip(CANVAS_IDS, CANVAS_XOFFSET, CANVAS_YOFFSET, CANVAS_XSIZE, CANVAS_YSIZE):
            CanvasIdMap[xoffset:xoffset + xsize, yoffset:yoffset + ysize] = canvas_id
    
    canvas_id = int(CanvasIdMap[x, y])
    cx = x - CANVAS_XOFFSET[canvas_id]
    cy = y - CANVAS_YOFFSET[canvas_id]
    return cx, cy, canvas_id

def CanvasCoordToAbsCoord(cx: int, cy: int, canvas_id: int):
    x = cx + CANVAS_XOFFSET[canvas_id]
    y = cy + CANVAS_YOFFSET[canvas_id]
    return x, y

def AttemptPlacement(place: Placer, diffcords: Optional[List[Tuple[int, int]]] = None):
    if diffcords is None:
        # Find pixels that don't match template
        diffcords = getDiff(currentData, templateData) # list([x, y], ...)
    
    if len(diffcords):# if img doesn't perfectly match template
        # Pick mismatched pixel to modify
        x, y = selectRandomPixel(diffcords) # select random pixel?
        
        # Send request to correct pixel that doesn't match template
        cx, cy, canvas_id = AbsCoordToCanvasCoord(x, y)
        hex_color = rgb_to_hex(closest_color(templateData[x, y], rgb_colors_array)) # find closest colour in colour map
        timestampOfSafePlace = place.place_tile(int(canvas_id), cx, cy, COLOR_MAP[hex_color]) # and convert hex_color to color ID for request
        
        # add random delay after placing tile (to reduce chance of bot detection)
        timestampOfSafePlace += random.uniform(5, 30)
        print(f"Placed Pixel '{COLOR_NAMES_MAP.get(hex_color, hex_color)}' at [{x}, {y}]. Can next place in {timestampOfSafePlace - time.time():.1f} seconds")
        
        return timestampOfSafePlace
    
    return time.time() + random.uniform(5, 30)


def init_webclient(botConfig):
    place = Placer()
    place.login(botConfig.username, botConfig.password)
    return place


def updateTemplateState(templateName: str):
    setRPlaceTemplate(templateName) # set current Template to "mlp" (the default)
    # python not async so must manually call updateTemplate() periodically
    updateTemplate()


def updateCanvasState(ids: Union[int, List[int]]):
    global currentData
    if type(ids) is int:
        ids = [ids]
    
    canvases = place.get_board()

    # load current state of canvas
    for canvas_id in ids:
        xoffset = CANVAS_XOFFSET[canvas_id]
        yoffset = CANVAS_YOFFSET[canvas_id]
        xsize   = CANVAS_XSIZE[canvas_id]
        ysize   = CANVAS_YSIZE[canvas_id]
        canvas = image_to_npy(Image.open(canvases[canvas_id]).convert("RGBA"))# raw -> intMatrix([W, H, (RGBA)])
        currentData[xoffset:xoffset + xsize, yoffset:yoffset + ysize] = canvas


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("username", nargs="?")
    parser.add_argument("password", nargs="?")
    parser.add_argument("template", nargs="?", default='mlp')
    args = parser.parse_args()
    botConfig = args

    place = init_webclient(botConfig)
    updateTemplateState(botConfig.template)
    
    timestampOfPlaceAttempt = 0
    time_to_wait = 0
    need_init = False
    while True:
        try:
            if need_init:
                place = init_webclient(botConfig)
            
            upstreamVersion = urllib.urlopen('https://CloudburstSys.github.io/place.conep.one/version.txt?t={}'.format(time.time())).read().decode("utf-8").replace("\n", "")

            if(VERSION != upstreamVersion):
                # Out of date!
                print("-------------------------------\nHello. Thanks for running our MLP r/place Python bots (PonyPixel).\nThese bots are now non-functional as r/place is over.\nWe succeeded. You can run `python checkDamage.py` to see the final damage levels.\nI recommend uninstalling PonyPixel now as it serves no purpose...\nUnless you wish to deconstruct it and learn Python.\nI have a donation link at https://ko-fi.com/cloudburstsys if you want to donate to me, however it is not required\nThank you soldier. Pony on.")
                print("\a-------------------------------\nBOT IS OUT OF DATE!\nPlease repull the bot (git pull) and restart your bots.")
                exit(3)

            for _ in tqdm(range(math.ceil(time_to_wait)), desc='waiting'): # fancy progress bar while waiting
                time.sleep(1)
            
            try:
                updateTemplate()
                updateCanvasState([0, 1, 2, 3])
                timestampOfPlaceAttempt = AttemptPlacement(place)
            except WebSocketConnectionClosedException:
                print("\aWebSocket connection refused. Auth issue.")
                exit(1)
            
            time_to_wait = timestampOfPlaceAttempt - time.time()
            if time_to_wait > DAY:
                print("\a-------------------------------\nBOT BANNED FROM R/PLACE\nPlease generate a new account and rerun.")
                exit(2)
            
            time.sleep(5)
        except KeyboardInterrupt:
            print('KeyboardInterrupt: Exiting Application')
            break
        except Exception as err:
            print("-------------------------------")
            print_exc() # print stack trace
            print("-------------------------------\nNON-TERMINAL ERROR ENCOUNTERED\nBot is reviving. Please wait...")
            time.sleep(15)
            need_init = True
