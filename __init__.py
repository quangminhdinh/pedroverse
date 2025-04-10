bl_info = {
    "name" : "Texture Editor",
    "description" : "",
    "blender" : (3, 0, 0),
    "version" : (1, 0, 1),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}

import bpy
import os
import sys
import numpy as np
import uuid

from PIL import Image
import cv2
from bpy.utils import previews
from skimage import color
import tensorflow as tf

folder_name = "/texture_recolor"

os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
style_predict_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name + "/style_predict.tflite"
style_transform_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name + "/style_transform.tflite"
content_blending_ratio = 0 

content_image_size = 1024 

from .palette import *
from .util import *
from .transfer import *

recolor_preview = {}


def run_style_predict(preprocessed_style_image):
  # Load the model.
  interpreter = tf.lite.Interpreter(model_path=style_predict_path)

  # Set model input.
  interpreter.allocate_tensors()
  input_details = interpreter.get_input_details()
  interpreter.set_tensor(input_details[0]["index"], preprocessed_style_image)

  # Calculate style bottleneck.
  interpreter.invoke()
  style_bottleneck = interpreter.tensor(
      interpreter.get_output_details()[0]["index"]
      )()

  return style_bottleneck

def run_style_transform(style_bottleneck, preprocessed_content_image):
  # Load the model.
  interpreter = tf.lite.Interpreter(model_path=style_transform_path)

  # Set model input.
  input_details = interpreter.get_input_details()
  for index in range(len(input_details)):
    if input_details[index]["name"]=='content_image':
      index = input_details[index]["index"]
      interpreter.resize_tensor_input(index, [1, content_image_size, content_image_size, 3])
  interpreter.allocate_tensors()

  # Set model inputs.
  for index in range(len(input_details)):
    if input_details[index]["name"]=='Conv/BiasAdd':
      interpreter.set_tensor(input_details[index]["index"], style_bottleneck)
    elif input_details[index]["name"]=='content_image':
      interpreter.set_tensor(input_details[index]["index"], preprocessed_content_image)
  interpreter.invoke()

  # Transform content image.
  stylized_image = interpreter.tensor(
      interpreter.get_output_details()[0]["index"]
      )()

  return stylized_image

def tensor_to_image(tensor):
    tensor = tensor*255
    tensor = np.array(tensor, dtype=np.uint8)
    if np.ndim(tensor)>3:
        assert tensor.shape[0] == 1
        tensor = tensor[0]
    return tensor

def load_img(path_to_img):
  img = tf.io.read_file(path_to_img)
  img = tf.io.decode_image(img, channels=3)
  img = tf.image.convert_image_dtype(img, tf.float32)
  img = img[tf.newaxis, :]

  return img

def preprocess_image(image, target_dim):
  # Resize the image so that the shorter dimension becomes 256px.
  shape = tf.cast(tf.shape(image)[1:-1], tf.float32)
  short_dim = min(shape)
  scale = target_dim / short_dim
  new_shape = tf.cast(shape * scale, tf.int32)
  image = tf.image.resize(image, new_shape)

  # Central crop the image.
  image = tf.image.resize_with_crop_or_pad(image, target_dim, target_dim)

  return image


class TEXTURE_OT_LoadImage(bpy.types.Operator):
    bl_idname = "texture.load_image"
    bl_label = "Load Image"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object first")
            return {'CANCELLED'}

        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError:
            self.report({'ERROR'}, "Failed to load image. Check file path.")
            return {'CANCELLED'}

        if not obj.data.materials:
            mat = bpy.data.materials.new(name="NewMaterial")
            obj.data.materials.append(mat)
        else:
            mat = obj.data.materials[0]

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        img_lists = []
        for node in nodes:
            if node.type == "ShaderNodeTexImage" or node.type == "TEX_IMAGE":
                img_lists.append(node)
            
        if len(img_lists) > 0:
            tex_image = img_lists[0]
            if not tex_image.image:
                for im in img_lists:
                    im.image = img
                return {'FINISHED'}
            elif not tex_image.image.filepath:
                temp_tex_image = tex_image.image.copy()
                temp_tex_image.update()
                temp_tex_image.filepath = os.path.dirname(bpy.data.filepath) + "/retexture_temp.png"
                temp_tex_image.name = "retexture_temp"
                temp_tex_image.file_format = "PNG"
                temp_tex_image.save()
                tex_image.image = temp_tex_image


            content_img = load_img(bpy.path.abspath(tex_image.image.filepath))
            style_img = load_img(self.filepath)
                        
            prev = preprocess_image(content_img, 256)
            
            content_img = preprocess_image(content_img, content_image_size)
            style_img = preprocess_image(style_img, 256)
            print(content_img.shape)
            
            style_bottleneck_content = run_style_predict(
                prev
            )
            style_bottleneck = run_style_predict(tf.constant(style_img))
            style_bottleneck_blended = content_blending_ratio * style_bottleneck_content \
                           + (1 - content_blending_ratio) * style_bottleneck
            stylized_img = run_style_transform(style_bottleneck_blended, content_img)
            
            stylized_img = tensor_to_image(stylized_img)
            if stylized_img is None:
                self.report({'ERROR'}, "Style Transfer Failed")
                return {'CANCELLED'}
            output_path = bpy.path.abspath(f"//output_{uuid.uuid4().hex}.png")
            Image.fromarray(stylized_img).save(output_path)
            ou_img = bpy.data.images.load(output_path, check_existing=True)
            for im in img_lists:
                im.image = ou_img
            return {'FINISHED'}
            
        tex_image = nodes.new(type="ShaderNodeTexImage")
        tex_image.location = (-300, 0)
        tex_image.image = img

        for node in nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])
                return {'FINISHED'}

        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        
        material_output = None
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                material_output = node
                break

        if not material_output:
            material_output = nodes.new(type="ShaderNodeOutputMaterial")
            material_output.location = (300, 0)
        
        node_mat_output = nodes['Material Output']

        links.new(bsdf.outputs["BSDF"], material_output.inputs["Surface"])
        links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}



class MyProperties(bpy.types.PropertyGroup):
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,  # RGBA
        min=0.0, max=1.0,
        default=(1, 1, 1, 1.0)
    )


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

    palette = None
    image_filepath = ""

    def execute(self, context):
        for i in range(4):
            self.color[i] = context.scene.my_tools.color[i]
        for i in range(4):
            context.window_manager["recolorpalette"][self.id][i] = self.color[i]

        new_palette = []
        for i in range(context.scene.num_colors):
            col = [context.window_manager["recolorpalette"][i][0], context.window_manager["recolorpalette"][i][1], context.window_manager["recolorpalette"][i][2]]
            lab_col = rgbCol2lab(col)
            new_palette.append([*lab_col[0:3], context.window_manager["recolorpalette"][i][3]])
            self.report({'INFO'}, f"colors: {new_palette[i][0]} , {new_palette[i][1]} + ,  + {new_palette[i][2]} + ,  +{new_palette[i][3]}")
        new_image = setPalette(self.image_filepath, old_palette=ColorOperator.palette, new_palette=new_palette)
        saveNSetImage(new_image, "new_palette.png", context)
        return {'FINISHED'}
    
    def invoke(self, context, event):

        temp = context.window_manager["originalpalette"][self.id]
        self.report({'INFO'}, f"type: {temp[0]} , {temp[1]} + ,  + {temp[2]} + ,  +{temp[3]}")
        self.color = context.window_manager["recolorpalette"][self.id]


        context.scene.my_tools.color = context.window_manager["recolorpalette"][self.id]
        self.report({'INFO'}, f"type: {self.color[0]} , {self.color[1]} + ,  + {self.color[2]} + ,  +{self.color[3]}")
        return context.window_manager.invoke_props_dialog(self) 
    
    def draw(self, context):
        layout = self.layout
        layout.template_color_picker(context.scene.my_tools, "color", value_slider=True)





class RecolourPanel(bpy.types.Panel):
    bl_label = 'Recolour'
    bl_idname = 'SNA_PT_Recolour_52FC0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Recolour'
    bl_order = 0
    bl_ui_units_x=0

    global recolor_preview

    last_b_iamge = ""

    def draw(self, context):
        glob_layout = self.layout
        
        layout1 = glob_layout.box()
        layout1.label(text="Style Transfer", icon='SHADING_TEXTURE')
        layout1.operator("texture.load_image", text="Select Image")
        

        layout = glob_layout.box()
        layout.label(text="Palette Transfer", icon='COLOR')
        layout.prop(context.scene, "num_colors", text="Number of colors in palette")
        
        obj = context.active_object
        wm = context.window_manager
        checkWMVars()

        gotPalette = False
        new_image = None
        
        if obj and obj.type == 'MESH' and obj.active_material:
            if(wm["recolorObjectName"] != obj.name or len(wm["recolorpalette"]) != context.scene.num_colors):
                mat = obj.active_material
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE':
                            new_image = saveNLoadImage(node)
                            
                            new_material = mat.copy()
                            obj.data.materials.append(new_material)

                            layout.label(text = new_image.filepath)
                            
                            tempPalette, recolorPalette = getPalettes(bpy.path.abspath(new_image.filepath), context.scene.num_colors)

                            #setting variables for later use
                            wm["recolorMaterial"] = new_material 
                            wm["recolorObjectName"] = obj.name
                            wm["recolorfilepath"] = bpy.path.abspath(new_image.filepath)
                            wm["recolorpalette"] = recolorPalette
                            wm['originalpalette'] = tempPalette

                            recolor_preview['main'].load("textureSelected", wm["recolorfilepath"], "IMAGE")
                            gotPalette = True

                            break
                            

                
            else:
                layout.label(text=obj.name + ", " + wm["recolorObjectName"]+ ", " +str(len(recolor_preview['main'])))
                gotPalette = True
        else:
            layout.label(text="Select object with image texture")
            wm["recolorfilepath"] = ""
            wm["recolorpalette"] = []
            gotPalette = False


        if(gotPalette):
            opalette = wm["originalpalette"]
            layout.label(text="Image: " + str(recolor_preview['main']['textureSelected'].icon_id))
            pbefore = recolor_preview['main']['textureSelected']
            layout.template_icon(icon_value=pbefore.icon_id, scale=10.0)
            

            ColorOperator.palette = opalette
            ColorOperator.image_filepath = wm["recolorfilepath"]

            rpalette = wm["recolorpalette"]

            column = layout.column()
            buttons = []
            for i in range(len(rpalette)):
                
                temp = column.operator("object.simple_operator", text="color " + str(i+1))
                temp.color = rpalette[i]
                
                temp.id = i
                buttons.append(temp)
        
def saveNLoadImage(node):
    recolor_preview['main'].clear()
    original_image = node.image

    #shoudl probably change how the image is saved giving the user an option to say where to save the image
    os.makedirs(os.path.dirname(bpy.data.filepath) + "/new_palette", exist_ok=True)
    new_filepath = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "original.png" 

    #
    numpy_image = numpy.array(original_image.pixels)
    width, height = original_image.size
    pixels = numpy_image.reshape((height, width, 4))
    pixels = pixels[:, :, :3] * 255

    image = Image.fromarray(pixels.astype(np.uint8))
    image.save(new_filepath)

    new_image=bpy.data.images.load(new_filepath)
    return new_image


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

def setPalette(image_filepath, old_palette, new_palette):
    image_rgb = Image.open(image_filepath)
    image_lab = rgb2lab(image_rgb)
    
    new_image = image_transfer(image_lab, old_palette, new_palette, sample_level=10, luminance_flag=False)
    return new_image

def rgbCol2lab(old_color):
    lab_col = color.rgb2lab(old_color)
    lab_col = [int(lab_col[0]*255.0/100.0), int(lab_col[1]+128), int(lab_col[2]+128)]
    return lab_col


def saveNSetImage(new_image, image_name, context):
    temp = cv2.cvtColor(numpy.array(lab2rgb(new_image)), cv2.COLOR_RGB2BGR)
    path1 = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/" + "default.png"
    temp = cv2.flip(temp, 0)

    cv2.imwrite(path1,temp)
    material = context.window_manager["recolorMaterial"]

    wm = bpy.context.window_manager
    if(wm["recolorObjectName"] != context.active_object.name or material==None):
        material = context.active_object.active_material.copy()
        context.active_object.data.materials.append(material)

    context.active_object.active_material = material


    for node in context.active_object.active_material.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            node.image = bpy.data.images.load(path1)

def checkWMVars():
    wm = bpy.context.window_manager

    if "recolorObjectName" not in wm:
        wm["recolorObjectName"] = ""
    if "recolorfilepath" not in wm:
        wm["recolorfilepath"] = ""
    if "originalpalette" not in wm:
        wm["originalpalette"] = []
    if "recolorpalette" not in wm:
        wm["recolorpalette"] = []
    if "recolorMaterial" not in wm:
        wm["recolorMaterial"] = None



def register():
    global recolor_preview
    
    bpy.utils.register_class(MyProperties)
    bpy.utils.register_class(ColorOperator)
    bpy.utils.register_class(RecolourPanel)
    bpy.utils.register_class(TEXTURE_OT_LoadImage)

    bpy.types.Scene.len_palette = bpy.props.IntProperty(name="Palette Length",
        description="Length of the color palette",
        default=5)

    bpy.types.Scene.my_tools = bpy.props.PointerProperty(type=MyProperties)
    bpy.types.Scene.num_colors = bpy.props.IntProperty(name="num_colors", default=2, min=2, max=100)

    bpy.types.Scene.len_palette = 2

    recolor_preview['main'] = bpy.utils.previews.new()





def unregister():
    global recolor_preview

    del bpy.types.Scene.my_tools
    del bpy.types.Scene.len_palette
    del bpy.types.Scene.num_colors


    bpy.utils.unregister_class(MyProperties)
    bpy.utils.unregister_class(ColorOperator)
    bpy.utils.unregister_class(RecolourPanel)
    bpy.utils.unregister_class(TEXTURE_OT_LoadImage)
    
    for pcoll in recolor_preview.values():
        bpy.utils.previews.remove(pcoll)
    recolor_preview.clear()


    wm = bpy.context.window_manager
    wm["recolorObjectName"] = ""
    wm["recolorfilepath"] = ""
    wm["originalpalette"] = []
    wm["recolorpalette"] = []
    wm["recolorMaterial"] = None

if __name__ == "__main__":
    register()
