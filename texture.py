import bpy
import os
import sys
import numpy as np
import uuid
import tensorflow as tf
from PIL import Image
from . import globals


folder_name = "/texture_recolor"

os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
style_predict_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name + "/style_predict.tflite"
style_transform_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name + "/style_transform.tflite"
content_blending_ratio = 0 

content_image_size = 1024 

def draw_style_transfer_layout(layout, context):
    layout.label(text="Style Transfer", icon='SHADING_TEXTURE')
    layout.operator("texture.load_image_s", text="Select Image")
    
    if 'textureTransfer' in globals.recolor_preview['main']:
        layout.prop(context.scene, "blending_ratio", text="Percent of Original Image")

        textb4 = globals.recolor_preview['main']['textureTransfer']
        layout.template_icon(icon_value=textb4.icon_id, scale=10.0)
        layout.prop(context.scene, "num_colors_text", text="Number of colors in palette")

        column = layout.column()

        for i in range(len(globals.recolorpalette[1])):
            temp = column.operator("object.simple_operator", text="color " + str(i + 1))
            temp.color = globals.recolorpalette[1][i]
            temp.imageType = 1
            temp.id = i

        temp = layout.operator("texture.load_image", text="Texture Object")
        temp.filepath = globals.recoloredimagefilepath if globals.recoloredimagefilepath != "" else globals.recolorfilepath[1]

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
            style_bottleneck_blended = (context.scene.blending_ratio/100.0) * style_bottleneck_content \
                           + (1 - (context.scene.blending_ratio/100.0)) * style_bottleneck
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


def register():
    bpy.utils.register_class(TEXTURE_OT_LoadImage)
    bpy.types.Scene.blending_ratio = bpy.props.FloatProperty(name="Content Blending Ration", default=0, min=0, max=100)

def unregister():
    bpy.utils.unregister_class(TEXTURE_OT_LoadImage)
    del bpy.types.Scene.blending_ratio
   