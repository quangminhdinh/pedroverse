import bpy
import os
import numpy as np

from bpy.utils import previews
import subprocess
import json

from . import globals

subprocess_file = "/recolor/recolor_subprocess.py"
script_path = os.path.dirname(__file__)
save_path = "" 

def draw_palette_transfer(layout, context):
    #have to do it here as it requires it to be in the draw function
    if bpy.data.filepath == "":
        layout.label(text="Please save file first")
        return
    
    global save_path
    if(save_path == ""):
        save_path = os.path.dirname(bpy.data.filepath) + "/new_palette"


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
                        is_base_color = False
                        for output in node.outputs:
                            for link in output.links:
                                if link.to_node.type == 'BSDF_PRINCIPLED' and link.to_socket.name == 'Base Color':
                                    is_base_color = True
                                    break
                            if is_base_color:
                                break

                        if not is_base_color:
                            continue  # ❌ Skip anything not wired to Base Color

                        # ✅ Only proceed for base color nodes
                        new_material = mat.copy()
                        obj.data.materials.append(new_material)

                        savePalettes(context, node.image, 0)
                        globals.recolorMaterial = new_material
                        globals.recolorObjectName = obj.name
                        globals.materialImageName = node.image.name

                        if "textureSelected" in globals.recolor_preview['main']:
                            del globals.recolor_preview['main']['textureSelected']
                        globals.recolor_preview['main'].load("textureSelected", globals.recolorfilepath[0], "IMAGE")
                        gotPalette = True
                        break

        elif len(globals.recolorpalette[0]) != context.scene.num_colors:
            new_image = bpy.data.images.load(globals.recolorfilepath[0])
            savePalettes(context, new_image, 0)
            gotPalette = True

        else:
            gotPalette = True
    else:
        layout.label(text="Select object with image texture")
        globals.recolorfilepath[0] = ""
        globals.recolorpalette[0] = []
        globals.recolorObjectName = None
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
        for i in range(len(self.color)):
            self.color[i] = context.scene.pick_colors.color[i]
        for i in range(len(self.color)):
            globals.recolorpalette[self.imageType][self.id][i] = self.color[i]

        args = [
            globals.PYTHON, script_path + subprocess_file, "recolor",
            str(self.imageType),
            globals.recolorfilepath[self.imageType],
            save_path + "/",
            json.dumps(globals.recolorpalette[self.imageType]),
            json.dumps(globals.originalpalette[self.imageType])
        ]
        
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        filepath = result.stdout.strip()

        if(self.imageType == 0):
            if "textureSelected" in globals.recolor_preview['main']:
                del globals.recolor_preview["main"]['textureSelected']
            globals.recolor_preview['main'].load("textureSelected", filepath, "IMAGE")
            setImage(context, filepath)

        else:
            globals.recoloredimagefilepath = filepath
            if "textureTransfer" in globals.recolor_preview['main']:
                del globals.recolor_preview["main"]['textureTransfer']
            globals.recolor_preview['main'].load("textureTransfer", filepath, "IMAGE")
            
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

    savePalettes(context, new_image, 1)
    

class TextureImageSelect(bpy.types.Operator):
    bl_idname = "texture.load_image_s"
    bl_label = "Select Image"

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Choose a file",
        subtype='FILE_PATH'
    )

    def execute(self, context):
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
                is_base_color = False
                for output in node.outputs:
                    for link in output.links:
                        if link.to_node.type == 'BSDF_PRINCIPLED' and link.to_socket.name == 'Base Color':
                            is_base_color = True
                            break
                    if is_base_color:
                        break

                if not is_base_color:
                    continue  # ❌ Skip nodes not connected to Base Color

                # ✅ Proceed only with base color image node
                if ((globals.recolorMaterial and isinstance(globals.recolorMaterial, str)) or 
                    globals.recolorMaterial.name != context.active_object.active_material.name or 
                    globals.materialImageName != node.image.name):

                    savePalettes(context, node.image, 0)

                    globals.recolorMaterial = context.active_object.active_material
                    globals.materialImageName = node.image.name

                    if "textureSelected" in globals.recolor_preview['main']:
                        del globals.recolor_preview['main']["textureSelected"]
                    globals.recolor_preview['main'].load("textureSelected", globals.recolorfilepath[0], "IMAGE")

    
def savePalettes(context, new_image, number):
    os.makedirs(save_path, exist_ok=True)

    numpy_image = np.array(new_image.pixels)
    width, height = new_image.size
    pixels = numpy_image.reshape((height, width, 4))
    pixels = pixels[:, :, :3] * 255
    pixels = np.flipud(pixels)

    np.save(save_path + "/temp.npy", pixels)

    num_colors = str(context.scene.num_colors)
    if(number == 1):
        num_colors=str(context.scene.num_colors_text)


    args = [
        globals.PYTHON, script_path + subprocess_file, "getPalettes",
        save_path + "/temp.npy",
        save_path + "/original.png" ,
        num_colors
    ]
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    palettes = json.loads(result.stdout)

    globals.recolorpalette[number] = palettes[1]
    globals.originalpalette[number] = palettes[0]

    globals.recolorfilepath[number] = save_path + "/original.png"



def setImage(context, save_path):
    material = globals.recolorMaterial

    # If it's a different object or material is not initialized, duplicate and assign
    if globals.recolorObjectName != context.active_object.name or material is None:
        material = context.active_object.active_material.copy()
        context.active_object.data.materials.append(material)

    context.active_object.active_material = material

    # Load new image from given path
    new_image = bpy.data.images.load(save_path)

    # Only update nodes connected to the Base Color socket
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            is_base_color = False
            for output in node.outputs:
                for link in output.links:
                    if link.to_node.type == 'BSDF_PRINCIPLED' and link.to_socket.name == 'Base Color':
                        is_base_color = True
                        break
                if is_base_color:
                    break

            if is_base_color:
                node.image = new_image
                globals.materialImageName = new_image.name

            


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