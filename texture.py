import bpy
import os
import sys
import numpy as np
import uuid
from . import globals
import subprocess


folder_name = "/texture_recolor"

os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
dir_path = bpy.utils.script_paths(subdir="addons")[0] + folder_name
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




class TEXTURE_OT_LoadImage(bpy.types.Operator):
    bl_idname = "texture.load_image"
    bl_label = "Load Image"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        global dir_path
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


            python_file = "/texture_subprocess.py"

            output_path = bpy.path.abspath(f"//output_{uuid.uuid4().hex}.png")

            args = [
                "python", dir_path+python_file,
                bpy.path.abspath(tex_image.image.filepath),
                str(0.0),
                str(content_image_size),
                dir_path + "/style_predict.tflite",
                dir_path + "/style_transform.tflite",
                self.filepath,
                output_path
            ]

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.report({"INFO"}, result.stdout)
            if result.stdout == "":
                self.report({'ERROR'}, "Style Transfer Failed")
                self.report({'ERROR'}, result.stderr)
                return {'CANCELLED'}
            
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
   