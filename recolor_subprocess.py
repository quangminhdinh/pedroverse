import os
import sys
import numpy as np
import json

from PIL import Image
import cv2
from skimage import color

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  

from palette import *
from util import *
from transfer import *



def getPalettes(numpy_image, save_filepath, num):
    numpy_image = numpy_image.astype(np.uint8)
    image_rgb = Image.fromarray(numpy_image)
    image_rgb.save(save_filepath)
    image_lab = rgb2lab(image_rgb)
    palette = build_palette(image_lab, num)

    recolorPalette = [RegularRGB(LABtoRGB(RegularLAB(c))) for c in palette]

    for i in range(len(palette)):
        palette[i] = [*palette[i], 1.0]
        recolorPalette[i] = [*recolorPalette[i], 1.0]
        for j in range(3):
            recolorPalette[i][j] = recolorPalette[i][j]/255.0
    
    output = [palette, recolorPalette]
    
    print(json.dumps(output))

def setPalette(image_filepath, old_palette, new_palette):
    image_rgb = Image.open(image_filepath)
    image_lab = rgb2lab(image_rgb)
    
    new_image = image_transfer(image_lab, old_palette, new_palette, sample_level=10, luminance_flag=False)
    return new_image

def rgbCol2lab(old_color):
    lab_col = color.rgb2lab(old_color)
    lab_col = [int(lab_col[0]*255.0/100.0), int(lab_col[1]+128), int(lab_col[2]+128)]
    return lab_col


def saveImage(new_image, image_path):
    temp = cv2.cvtColor(numpy.array(lab2rgb(new_image)), cv2.COLOR_RGB2BGR)
    cv2.imwrite(image_path,temp)

def recolor(imageType, recolorfilepath, dirpath, recolorpalette, originalpalette):
    new_palette = []
    for i in range(len(recolorpalette)):
        col = [recolorpalette[i][0], recolorpalette[i][1], recolorpalette[i][2]]
        lab_col = rgbCol2lab(col)
        new_palette.append([*lab_col[0:3], recolorpalette[i][3]])

    new_image = setPalette(recolorfilepath, old_palette=originalpalette, new_palette=new_palette)

    filename = "default.png"
    filepath = dirpath #os.path.dirname(bpy.data.filepath) + "/new_palette" + "/"

    if(imageType != 0):
        filename = "texture.png"
    
    image_path = dirpath + filename
    saveImage(new_image, image_path)

    print(image_path)

if __name__=="__main__":
    function = sys.argv[1]

    if(function == "getPalettes"):
        numpy_image = np.load(sys.argv[2])
        save_filepath = sys.argv[3]
        num = int(sys.argv[4])

        getPalettes(numpy_image, save_filepath, num)

    elif(function == "recolor"):
        imageType = int(sys.argv[2])
        recolorfilepath = sys.argv[3]
        dirpath = sys.argv[4]
        recolorpalette = json.loads(sys.argv[5])
        originalpalette = json.loads(sys.argv[6])

        recolor(imageType, recolorfilepath, dirpath, recolorpalette, originalpalette)

    