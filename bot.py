#!/usr/bin/env python3

import math
from enum import Enum
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
import random

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("username", nargs="?")
parser.add_argument("password", nargs="?")
args = parser.parse_args()
if args.username is None or args.password is None:
  import botConfig
else:
  botConfig = args


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


def rgb_to_hex(rgb):
    return ("#%02x%02x%02x%02x" % rgb).upper()


# function to find the closest rgb color from palette to a target rgb color
def closest_color(target_rgb, rgb_colors_array_in):
    r, g, b, a = target_rgb
    color_diffs = []
    for color in rgb_colors_array_in:
        cr, cg, cb, ca = color
        color_diff = math.sqrt((r - cr)**2 + (g - cg)**2 + (b - cb)**2 + (a - ca)**2)
        color_diffs.append((color_diff, color))
    return min(color_diffs)[1]

rgb_colors_array = []

class Color(Enum):
    BLACK = 27
    WHITE = 31


class Placer:
    REDDIT_URL = "https://www.reddit.com"
    LOGIN_URL = REDDIT_URL + "/login"
    INITIAL_HEADERS = {
        "accept":
        "*/*",
        "accept-encoding":
        "gzip, deflate, br",
        "accept-language":
        "en-US,en;q=0.9",
        "content-type":
        "application/x-www-form-urlencoded",
        "origin":
        REDDIT_URL,
        "sec-ch-ua":
        '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile":
        "?0",
        "sec-ch-ua-platform":
        '"Windows"',
        "sec-fetch-dest":
        "empty",
        "sec-fetch-mode":
        "cors",
        "sec-fetch-site":
        "same-origin",
        "user-agent":
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
                                 "username": username,
                                 "password": password,
                                 "dest": self.REDDIT_URL,
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
        print("Getting board")
        ws = create_connection("wss://gql-realtime-2.reddit.com/query", origin="https://hot-potato.reddit.com")
        ws.send(
            json.dumps({
                "type": "connection_init",
                "payload": {
                    "Authorization": "Bearer " + self.token
                },
            }))
        ws.recv()
        ws.send(
            json.dumps({
                "id": "1",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CONFIG",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName":
                    "configuration",
                    "query":
                    "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on ConfigurationMessageData {\n          colorPalette {\n            colors {\n              hex\n              index\n              __typename\n            }\n            __typename\n          }\n          canvasConfigurations {\n            index\n            dx\n            dy\n            __typename\n          }\n          canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))
        ws.recv()
        ws.send(
            json.dumps({
                "id": "2",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CANVAS",
                                "tag": "0",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName":
                    "replace",
                    "query":
                    "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }))

        file = ""
        while True:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    file = msg["data"]["name"]
                    break

        ws.close()

        boardimg = BytesIO(requests.get(file, stream=True).content)
        print("Got image:", file)

        return boardimg

    def place_tile(self, x: int, y: int, color: int):
        headers = self.INITIAL_HEADERS.copy()
        headers.update({
            "apollographql-client-name": "mona-lisa",
            "apollographql-client-version": "0.0.1",
            "content-type": "application/json",
            "origin": "https://hot-potato.reddit.com",
            "referer": "https://hot-potato.reddit.com/",
            "sec-fetch-site": "same-site",
            "authorization": "Bearer " + self.token
        })

        r = requests.post("https://gql-realtime-2.reddit.com/query",
                          json={
                              "operationName": "setPixel",
                              "query": SET_PIXEL_QUERY,
                              "variables": {
                                  "input": {
                                      "PixelMessageData": {
                                          "canvasIndex": 0,
                                          "colorIndex": color,
                                          "coordinate": {
                                              "x": x,
                                              "y": y
                                          }
                                      },
                                      "actionName": "r/replace:set_pixel"
                                  }
                              }
                          },
                          headers=headers)

        if r.json()["data"] == None:
            try:
              waitTime = math.floor(
                  r.json()["errors"][0]["extensions"]["nextAvailablePixelTs"])
              print("placing failed: rate limited")
            except:
              waitTime = 10000
        else:
            waitTime = math.floor(r.json()["data"]["act"]["data"][0]["data"]
                                  ["nextAvailablePixelTimestamp"])
            print("placing succeeded")

        return waitTime / 1000


color_map = {
    "#BE0039FF": 1, 
    "#FF4500FF": 2,  # bright red
    "#FFA800FF": 3,  # orange
    "#FFD635FF": 4,  # yellow
    "#00A368FF": 6,  # darker green
    "#00CC78FF": 7,
    "#7EED56FF": 8,  # lighter green
    "#00756FFF": 9,
    "#009EAAFF": 10,
    "#2450A4FF": 12,  # darkest blue
    "#3690EAFF": 13,  # medium normal blue
    "#51E9F4FF": 14,  # cyan
    "#493AC1FF": 15,
    "#6A5CFFFF": 16,
    "#811E9FFF": 18,  # darkest purple
    "#B44AC0FF": 19,  # normal purple
    "#FF3881FF": 22,
    "#FF99AAFF": 23,  # pink
    "#6D482FFF": 24,
    "#9C6926FF": 25,  # brown
    "#000000FF": 27,  # black
    "#898D90FF": 29,  # grey
    "#D4D7D9FF": 30,  # light grey
    "#FFFFFFFF": 31,  # white
}

def init_rgb_colors_array():
  global rgb_colors_array

  # generate array of available rgb colors we can use
  for color_hex, color_index in color_map.items():
    rgb_array = ImageColor.getcolor(color_hex, "RGBA")
    rgb_colors_array.append(rgb_array)
    
  print("available colors for palette (rgba): ", rgb_colors_array)

init_rgb_colors_array()

place = Placer()

version = "0.2.0"

def trigger():
  pix2 = Image.open(place.get_board()).convert("RGBA").load()

  rows = []
  thisRow = []

  # Behold, the dirtiest code I ever wrote
  # This hacky hack serves as a bridge for urllib in Python 2 and Python 3
  try:
    urllib.urlopen
  except:
    urllib.urlopen = urllib.request.urlopen

  def getData():
    im = urllib.urlopen('https://cloudburstsys.github.io/place.conep.one/canvas.png').read()
    img = Image.open(BytesIO(im)).convert("RGBA").load()
		
    new_origin = urllib.urlopen('https://cloudburstsys.github.io/place.conep.one/origin.txt').read().decode("utf-8").split(',')
    origin = (int(new_origin[0]), int(new_origin[1]))
    size = (int(new_origin[2]), int(new_origin[3]))

    ver = urllib.urlopen('https://cloudburstsys.github.io/place.conep.one/version.txt').read().decode("utf-8").replace("\n", "")
    if(ver != version):
      print("VERSION OUT OF DATE!")
      print("PLEASE RUN 'git pull https://github.com/CloudburstSys/PonyPixel.git' TO UPDATE")
      
      return (None, (None, None), (None, None))

    return (img, origin, size)

  (img, origin, size) = getData()
  
  if(img == None):
    return

  (ox, oy) = origin
  (sx, sy) = size

  totalPixels = sx*sy
  correctPixels = 0
  wrongPixels = 0

  wrongPixelsArray = []

  for i in range(sx*sy):
    x = (i % sx) + ox
    y = math.floor(i / sx) + oy
	
    if(color_map[rgb_to_hex(closest_color(pix2[x, y], rgb_colors_array))] == color_map[rgb_to_hex(closest_color(img[x-ox, y-oy],rgb_colors_array))]):
		  # Great! They're equal!
      correctPixels += 1
    elif(rgb_to_hex(img[x-ox, y-oy]) == "#00000000"):
      # Blank pixel. we ignore it
      correctPixels += 1
    else:
      #print("Pixel at ({},{}) damaged: Expected: {}, got {}".format(x,y, color_text_map[color_map[rgb_to_hex(closest_color(img[x-ox, y-oy],rgb_colors_array))]], color_text_map[color_map[rgb_to_hex(closest_color(pix2[x, y], rgb_colors_array))]]))
      wrongPixels += 1
      wrongPixelsArray.append((x,y,rgb_to_hex(closest_color(img[x-ox, y-oy],rgb_colors_array))))

  print("{}% correct, {} wrong pixels".format(math.floor((correctPixels/totalPixels)*100),wrongPixels))

  (x,y,expected) = random.choice(wrongPixelsArray)	
  print("Fixing pixel at ({},{})... Replacing with {}".format(x,y,expected))
  timestampOfSafePlace = place.place_tile(x,y,color_map[expected]) + random.randint(5,30)
  print("Done. Can next place at {} seconds from now".format(timestampOfSafePlace - time.time()))

  return timestampOfSafePlace

timestampOfPlaceAttempt = 0

place.login(botConfig.username, botConfig.password)

while True:
  if timestampOfPlaceAttempt > time.time():
    time.sleep(5)
    continue

  try: 
    timestampOfPlaceAttempt = trigger()
  except WebSocketConnectionClosedException:
    print("Lost connection to websocket, Will reattempt shortly.")
  except:
    print("????????")

  time.sleep(5)
