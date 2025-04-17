import bpy
import os
import numpy as np

from PIL import Image
import cv2
from bpy.utils import previews
from skimage import color

from .palette import *
from .util import *
from .transfer import *
from . import globals

def draw_palette_transfer(layout, context):
    layout.label(text="Palette Transfer", icon='COLOR')
    layout.prop(context.scene, "num_colors", text="Number of colors in palette")

    obj = context.active_object

    gotPalette = False
    new_image = None
    if obj and obj.type == 'MESH' and obj.active_material:
        if globals.recolorObjectName != obj.name or 'textureSelected' not in globals.recolor_preview['main']:
            mat = obj.active_material
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE':
                        new_material = mat.copy()
                        obj.data.materials.append(new_material)

                        OImageFilepath = saveOriginalImage(node)
                        new_image = bpy.data.images.load(OImageFilepath)
                        palettes = getPalettes(bpy.path.abspath(new_image.filepath), context.scene.num_colors)

                        # Update global states
                        globals.recolorfilepath[0] = bpy.path.abspath(new_image.filepath)
                        globals.recolorpalette[0] = palettes[1]
                        globals.originalpalette[0] = palettes[0]
                        globals.recolorMaterial = new_material
                        globals.recolorObjectName = obj.name
                        globals.materialImageName = node.image.name
                        
                        if "textureSelected" in globals.recolor_preview['main']:
                            del globals.recolor_preview['main']['textureSelected']
                        globals.recolor_preview['main'].load("textureSelected", globals.recolorfilepath[0], "IMAGE")
                        gotPalette = True
                        break
        elif (len(globals.recolorpalette[0]) != context.scene.num_colors):
            palettes = getPalettes(globals.recolorfilepath[0], context.scene.num_colors)
            globals.recolorpalette[0] = palettes[1]
            globals.originalpalette[0] = palettes[0]
            gotPalette = True

        else:
            gotPalette = True
    else:
        layout.label(text="Select object with image texture")
        globals.recolorfilepath[0] = ""
        globals.recolorpalette[0] = []
        gotPalette = False

    if gotPalette:
        pbefore = globals.recolor_preview['main']['textureSelected']
        layout.template_icon(icon_value=pbefore.icon_id, scale=10.0)

        column = layout.column()
        for i in range(len(globals.recolorpalette[0])):
            temp = column.operator("object.simple_operator", text=f"color {i+1}")
            temp.id = i
            temp.imageType = 0

class ColorOperator(bpy.types.Operator):
    bl_idname = "object.simple_operator"
    bl_label = "Generate Palette"
    
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=255.0,
        default=(1.0, 0, 0, 1.0)
    )

    id: bpy.props.IntProperty(name="Number", default=0)
    imageType: bpy.props.IntProperty(name="Number", default=0)

    def execute(self, context):
        self.report({"INFO"}, ("here1"))
        for i in range(len(self.color)):
            self.color[i] = context.scene.pick_colors.color[i]
        for i in range(len(self.color)):
            globals.recolorpalette[self.imageType][self.id][i] = self.color[i]

        new_palette = []
        for i in range(len(globals.recolorpalette[self.imageType])):
            col = [globals.recolorpalette[self.imageType][i][0], globals.recolorpalette[self.imageType][i][1], globals.recolorpalette[self.imageType][i][2]]
            lab_col = rgbCol2lab(col)
            new_palette.append([*lab_col[0:3], globals.recolorpalette[self.imageType][i][3]])
        self.report({"INFO"}, (f"here2: {globals.recolorfilepath[self.imageType]}"))
        self.report({"INFO"}, (f"here2: {globals.originalpalette[self.imageType][self.id][0]}, {globals.originalpalette[self.imageType][self.id][1]}, {globals.originalpalette[self.imageType][self.id][2]}, {globals.originalpalette[self.imageType][self.id][3]}"))
        self.report({"INFO"}, (f"here2: {new_palette[self.id][0]}, {new_palette[self.id][1]}, {new_palette[self.id][2]}, {new_palette[self.id][3]}"))

        new_image = setPalette(globals.recolorfilepath[self.imageType], old_palette=globals.originalpalette[self.imageType], new_palette=new_palette)

        filename = "default.png"
        filepath = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/"
        self.report({"INFO"}, ("here3"))
        if(self.imageType != 0):
            filename = "texture.png"
            globals.recoloredimagefilepath = filepath + filename
        filepath = saveImage(new_image, filepath, filename, context)
        self.report({"INFO"}, ("here4"))
        if(self.imageType == 0):
            setImage(context, filepath)
        else:
            showImage(filepath)
        self.report({"INFO"}, ("here5"))
        return {'FINISHED'}
    
    def invoke(self, context, event):
        
        if(self.imageType == 0):
            checkImage(context, self)
        
        self.color = globals.recolorpalette[self.imageType][self.id]
        context.scene.pick_colors.color = globals.recolorpalette[self.imageType][self.id]

        return context.window_manager.invoke_props_dialog(self) 
    
    def draw(self, context):
        layout = self.layout
        layout.template_color_picker(context.scene.pick_colors, "color", value_slider=True)



def updateTextPalette(context, filepath):
    globals.recolorfilepath[1] = filepath
    
    if "textureTransfer" in globals.recolor_preview['main']:
        del globals.recolor_preview["main"]['textureTransfer']
    globals.recolor_preview['main'].load("textureTransfer", globals.recolorfilepath[1], "IMAGE")
    globals.recoloredimagefilepath = ""

    palettes = getPalettes(globals.recolorfilepath[1], context.scene.num_colors_text)
    globals.recolorpalette[1] = palettes[1]
    globals.originalpalette[1] = palettes[0]
    

class TextureImageSelect(bpy.types.Operator):
    bl_idname = "texture.load_image_s"
    bl_label = "Select Image"

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Choose a file",
        subtype='FILE_PATH'
    )

    def execute(self, context):
        self.report({"INFO"}, (f"selection: {self.filepath}"))
        updateTextPalette(context, self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def num_colors_changed(self, context):
    updateTextPalette(context, globals.recolorfilepath[1])

bpy.types.Scene.num_colors_text = bpy.props.IntProperty(
    name="Number of Colors",
    default=3,
    min=1,
    max=10,
    update=num_colors_changed 
)

     
def saveOriginalImage(node):
    original_image = node.image

    #should probably change how the image is saved giving the user an option to say where to save the image
    os.makedirs(os.path.dirname(bpy.data.filepath) + "/new_palette", exist_ok=True)
    new_filepath = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png" 

    numpy_image = numpy.array(original_image.pixels)
    width, height = original_image.size
    pixels = numpy_image.reshape((height, width, 4))
    pixels = pixels[:, :, :3] * 255

    imageflipped = Image.fromarray(pixels.astype(np.uint8))
    image = imageflipped.transpose(Image.FLIP_TOP_BOTTOM)
    image.save(new_filepath)
    return new_filepath

def getPalettes(image_filepath, num):
    image_rgb = Image.open(image_filepath)
    image_lab = rgb2lab(image_rgb)
    palette = build_palette(image_lab, num)

    recolorPalette = [RegularRGB(LABtoRGB(RegularLAB(c))) for c in palette]

    for i in range(len(palette)):
        palette[i] = [*palette[i], 1.0]
        recolorPalette[i] = [*recolorPalette[i], 1.0]
        for j in range(3):
            recolorPalette[i][j] = recolorPalette[i][j]/255.0
    
    return palette, recolorPalette

def checkImage(context, self):
    mat = context.active_object.active_material

    if mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                if ((globals.recolorMaterial and type(globals.recolorMaterial) == str) or globals.recolorMaterial.name != context.active_object.active_material.name or globals.materialImageName != node.image.name):
                        
                    globals.recolorMaterial = context.active_object.active_material
                    new_image_filepath = saveOriginalImage(node)
                    new_image = new_image=bpy.data.images.load(new_image_filepath)
                    
                    palettes = getPalettes(bpy.path.abspath(new_image.filepath), context.scene.num_colors)
                    globals.recolorpalette[0] = palettes[1]
                    globals.originalpalette[0] = palettes[0]
                    
                    globals.recolorfilepath[0] = bpy.path.abspath(new_image.filepath)
                    globals.materialImageName = node.image.name

                    if("textureSelected" in  globals.recolor_preview['main']):
                        del globals.recolor_preview['main']["textureSelected"]
                    globals.recolor_preview['main'].load("textureSelected", globals.recolorfilepath[0], "IMAGE")

    

def setPalette(image_filepath, old_palette, new_palette):
    image_rgb = Image.open(image_filepath)
    image_lab = rgb2lab(image_rgb)
    
    new_image = image_transfer(image_lab, old_palette, new_palette, sample_level=10, luminance_flag=False)
    return new_image

def rgbCol2lab(old_color):
    lab_col = color.rgb2lab(old_color)
    lab_col = [int(lab_col[0]*255.0/100.0), int(lab_col[1]+128), int(lab_col[2]+128)]
    return lab_col


def saveImage(new_image, image_path, image_name, context):
    temp = cv2.cvtColor(numpy.array(lab2rgb(new_image)), cv2.COLOR_RGB2BGR)
    path1 = image_path + image_name

    cv2.imwrite(path1,temp)
    return path1

def showImage(image_path):
    if "textureTransfer" in globals.recolor_preview['main']:
        del globals.recolor_preview["main"]['textureTransfer']
    globals.recolor_preview['main'].load("textureTransfer", image_path, "IMAGE")

def setImage(context, image_path):
    material = globals.recolorMaterial
    
    if(globals.recolorObjectName != context.active_object.name or material==None):
        material = context.active_object.active_material.copy()
        context.active_object.data.materials.append(material)
    context.active_object.active_material = material

    for node in context.active_object.active_material.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            node.image = bpy.data.images.load(image_path)
            globals.materialImageName = node.image.name
            


class MyProperties(bpy.types.PropertyGroup):
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,  # RGBA
        min=0.0, max=1.0,
        default=(1, 1, 1, 1.0)
    )

def register():
    bpy.utils.register_class(MyProperties)
    bpy.utils.register_class(ColorOperator)
    bpy.utils.register_class(TextureImageSelect)

    bpy.types.Scene.len_palette = bpy.props.IntProperty(name="Palette Length",
        description="Length of the color palette",
        default=2)

    bpy.types.Scene.pick_colors = bpy.props.PointerProperty(type=MyProperties)
    bpy.types.Scene.num_colors = bpy.props.IntProperty(name="num_colors", default=2, min=2, max=100)

def unregister():
    bpy.utils.unregister_class(MyProperties)
    bpy.utils.unregister_class(ColorOperator)
    bpy.utils.unregister_class(TextureImageSelect)

    del bpy.types.Scene.pick_colors
    del bpy.types.Scene.len_palette
    del bpy.types.Scene.num_colors