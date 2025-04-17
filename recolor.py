import bpy
import os
import numpy as np

from bpy.utils import previews
import subprocess
import json

from . import globals

python_file = "/recolor_subprocess.py"
folder_name = "/texture_recolor"
dir_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name

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
                        np.save(os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy", OImageFilepath)
                        save_filepath = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png"

                        
                        args = [
                            "python", dir_path + python_file, "getPalettes",
                            os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy",
                            save_filepath,
                            str(context.scene.num_colors)
                        ]
                        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                        palettes = json.loads(result.stdout)

                        # Update global states
                        globals.recolorfilepath[0] = save_filepath
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
            new_image = bpy.data.images.load(globals.recolorfilepath[0])

            pixels = np.array(new_image.pixels)

            # Optionally reshape or modify the array (e.g., you can reshape it to (height, width, 4))
            height, width = new_image.size
            pixels_reshaped = pixels.reshape((height, width, 4))
            pixels_rgb = pixels_reshaped[:, :, :3]

            # Now we serialize the numpy array to a list (because JSON can't store numpy arrays directly)
            np.save(os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy", pixels_rgb)
            args = [
                "python",dir_path + python_file, "getPalettes",
                os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy",
                os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png",
                str(context.scene.num_colors)
            ]
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            palettes = json.loads(result.stdout)
            globals.recolorpalette[0] = palettes[1]
            globals.originalpalette[0] = palettes[0]
            gotPalette = True

        else:
            gotPalette = True
    else:
        layout.label(text="Select object with image texture")
        globals.recolorfilepath[0] = ""
        globals.recolorpalette[0] = []
        globals.recolorObjectName = obj.name
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

        args = [
            "python", dir_path + python_file, "recolor",
            str(self.imageType),
            globals.recolorfilepath[self.imageType],
            os.path.dirname(bpy.data.filepath) + "/new_palette" + "/",
            json.dumps(globals.recolorpalette[self.imageType]),
            json.dumps(globals.originalpalette[self.imageType])
        ]
        
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        filepath = result.stdout.strip()

        self.report({"INFO"}, (result.stderr))
        if(self.imageType == 0):
            setImage(context, filepath)
        else:
            globals.recoloredimagefilepath = filepath
            if "textureTransfer" in globals.recolor_preview['main']:
                del globals.recolor_preview["main"]['textureTransfer']
            globals.recolor_preview['main'].load("textureTransfer", filepath, "IMAGE")
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
    new_image = bpy.data.images.load(globals.recolorfilepath[1])

    pixels = np.array(new_image.pixels)

    # Optionally reshape or modify the array (e.g., you can reshape it to (height, width, 4))
    height, width = new_image.size
    pixels_reshaped = pixels.reshape((height, width, 4))
    pixels_rgb = pixels_reshaped[:, :, :3] * 255

    # Now we serialize the numpy array to a list (because JSON can't store numpy arrays directly)
    np.save(os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy", pixels_rgb)
    args = [
        "python", dir_path + python_file, "getPalettes",
        os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy",
        os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png",
        str(context.scene.num_colors_text)
    ]
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    palettes = json.loads(result.stdout)
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

    

def checkImage(context, self):
    mat = context.active_object.active_material

    if mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                if ((globals.recolorMaterial and type(globals.recolorMaterial) == str) or globals.recolorMaterial.name != context.active_object.active_material.name or globals.materialImageName != node.image.name):
                        
                    globals.recolorMaterial = context.active_object.active_material
                    new_image_filepath = saveOriginalImage(node)

                    np.save(os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy", new_image_filepath)
                    args = [
                        "python",dir_path + python_file, "getPalettes",
                        os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "temp.npy",
                        os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png",
                        str(context.scene.num_colors)
                    ]
                    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    palettes = json.loads(result.stdout)
                    
                    globals.recolorpalette[0] = palettes[1]
                    globals.originalpalette[0] = palettes[0]
                    
                    globals.recolorfilepath[0] = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png"
                    globals.materialImageName = node.image.name

                    if("textureSelected" in  globals.recolor_preview['main']):
                        del globals.recolor_preview['main']["textureSelected"]
                    globals.recolor_preview['main'].load("textureSelected", globals.recolorfilepath[0], "IMAGE")

    

def saveOriginalImage(node):
    original_image = node.image

    #should probably change how the image is saved giving the user an option to say where to save the image
    os.makedirs(os.path.dirname(bpy.data.filepath) + "/new_palette", exist_ok=True)
    new_filepath = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png" 

    numpy_image = np.array(original_image.pixels)
    width, height = original_image.size
    pixels = numpy_image.reshape((height, width, 4))
    pixels = pixels[:, :, :3] * 255
    pixels = np.flipud(pixels)

    return pixels


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

    bpy.types.Scene.ObjectName = bpy.props.IntProperty(name="Palette Length",
        description="Length of the color palette",
        default=2)

    bpy.types.Scene.pick_colors = bpy.props.PointerProperty(type=MyProperties)
    bpy.types.Scene.num_colors = bpy.props.IntProperty(name="num_colors", default=2, min=2, max=100)

def unregister():
    bpy.utils.unregister_class(MyProperties)
    bpy.utils.unregister_class(ColorOperator)
    bpy.utils.unregister_class(TextureImageSelect)

    del bpy.types.Scene.pick_colors
    del bpy.types.Scene.ObjectName
    del bpy.types.Scene.num_colors