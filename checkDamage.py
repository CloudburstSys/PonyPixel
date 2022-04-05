import numpy as np
import urllib

from traceback import print_exc
from tqdm import tqdm
from io import BytesIO
from bs4 import BeautifulSoup
from PIL import ImageColor
from PIL import Image

# Behold, the dirtiest code I ever wrote
# This hacky hack serves as a bridge for urllib in Python 2 and Python 3
try:
    urllib.urlopen
except AttributeError as err:
    urllib.urlopen = urllib.request.urlopen

def image_to_npy(img):
    return np.asarray(img).transpose((1, 0, 2))

def fetchFinalCanvas():
    im = image_to_npy(Image.open("./final_canvas.png").convert("RGBA"))
    assert im.dtype == 'uint8', f'got dtype {im.dtype}, expected uint8'
    assert im.shape[2] == 4, f'got {im.shape[2]} color channels, expected 4 (RGBA)'
    return im

def fetchBotTemplate():
    im = None
    try:
        im = urllib.urlopen(f'https://media.githubusercontent.com/media/r-ainbowroad/minimap/d/main/mlp/bot.png').read()# load raw file
    except:
        im = "./bot.png"
    im = image_to_npy(Image.open(BytesIO(im)).convert("RGBA"))# raw -> intMatrix([W, H, (RGBA)])
    assert im.dtype == 'uint8', f'got dtype {im.dtype}, expected uint8'
    assert im.shape[2] == 4, f'got {im.shape[2]} color channels, expected 4 (RGBA)'
    return im

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

getDiff(fetchFinalCanvas(), fetchBotTemplate())