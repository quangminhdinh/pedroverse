import bpy
import os
import sys
import numpy as np
import uuid
from . import globals
import subprocess


os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'

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
        dir_path = os.path.dirname(__file__) + "/texture_transfer"
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
            if node.type == "TEX_IMAGE":
                for output in node.outputs:
                    for link in output.links:
                        if link.to_node.type == "BSDF_PRINCIPLED" and link.to_socket.name == "Base Color":
                            img_lists.append(node)
            
        
        for node in img_lists:
            self.report({'INFO'}, f"Candidate Texture Node: {node.name} (Image: {node.image.name if node.image else 'None'})")
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
                globals.PYTHON, dir_path+python_file,
                bpy.path.abspath(tex_image.image.filepath),
                str(bpy.context.scene.blending_ratio),
                str(content_image_size),
                dir_path + "/style_predict.tflite",
                dir_path + "/style_transform.tflite",
                self.filepath,
                output_path
            ]

            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("\n\n" + result.stderr)
            if result.stdout == "":
                self.report({'ERROR'}, "Style Transfer Failed")
                return {'CANCELLED'}
            
            ou_img = bpy.data.images.load(output_path, check_existing=True)
            for tex_node in img_lists:
                for output in tex_node.outputs:
                    for link in output.links:
                        if link.to_node.type == "BSDF_PRINCIPLED" and link.to_socket.name == "Base Color":
                            # Report the image node being updated
                            node_name = tex_node.name
                            old_img_name = tex_node.image.name if tex_node.image else "None"
                            self.report({'INFO'}, f"Updating node '{node_name}' (was: {old_img_name}) -> new image: {ou_img.name}")
                            
                            tex_node.image = ou_img

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
   