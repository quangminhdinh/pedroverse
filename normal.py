import bpy
import os
import uuid
import subprocess
from . import globals

class TEXTURE_OT_apply_normal_effect(bpy.types.Operator):
    """Apply effect to normal map and fix color space automatically"""
    bl_idname = "texture.apply_normal_effect"
    bl_label = "Apply Normal Effect"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        mat = obj.active_material if obj else None
        settings = context.scene.texture2_settings

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object.")
            return {'CANCELLED'}

        if not mat or not mat.use_nodes:
            self.report({'ERROR'}, "Active object must have a material with nodes enabled.")
            return {'CANCELLED'}

        nodes = mat.node_tree.nodes
        normal_node = None

        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                for output in node.outputs:
                    for link in output.links:
                        if link.to_node.type == 'NORMAL_MAP' or link.to_socket.name == 'Normal':
                            normal_node = node
                            break
                if normal_node:
                    break

        if not normal_node:
            self.report({'WARNING'}, "No normal map texture found.")
            return {'CANCELLED'}

        if(normal_node.image.filepath == ""):
            input_path = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/normal.png"
            normal_node.image.save(filepath = input_path)
        else:
            input_path = bpy.path.abspath(normal_node.image.filepath)

        # Store original normal path
        if "original_normal_path" not in obj:
            obj["original_normal_path"] = input_path

        # Reset to default logic
        if settings.active_option == 'OPTION_RESET':
            if "original_normal_path" in obj:
                original_path = obj["original_normal_path"]
                if os.path.exists(original_path):
                    restored_img = bpy.data.images.load(original_path)
                    restored_img.colorspace_settings.name = 'Non-Color'
                    normal_node.image = restored_img
                    globals.recolor_preview['main'].clear()
                    globals.recolor_preview['main'].load("normalPreview", original_path, 'IMAGE')
                    self.report({'INFO'}, "Original normal map restored.")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, "Original normal texture file not found.")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "No original normal map path recorded.")
                return {'CANCELLED'}

        # Normal effect setup
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Please save your .blend file first.")
            return {'CANCELLED'}

        save_dir = os.path.join(os.path.dirname(blend_path), "normal_effect_outputs")
        os.makedirs(save_dir, exist_ok=True)
        output_path = os.path.join(save_dir, f"normal_{uuid.uuid4().hex}.png")

        effect_id = ""
        effect_args = []

        if settings.active_option == 'OPTION_1':
            effect_id = "pixelate"
            effect_args = [str(settings.pixelate_downsample), str(settings.pixelate_palette)]

        elif settings.active_option == 'OPTION_2':
            effect_id = "brush"
            effect_args = [
                bpy.path.abspath(settings.vertical_brush_path),
                bpy.path.abspath(settings.horizontal_brush_path)
            ]

        elif settings.active_option == 'OPTION_3':
            effect_id = "voronoi"
            effect_args = [
                str(settings.num_voronoi_patterns),
                str(settings.oil_paint_size),
                str(settings.oil_paint_dyn_ratio),
                str(int(settings.use_bilateral_filter))
            ]

        elif settings.active_option == 'OPTION_4':
            effect_id = "brushstyle"
            if settings.brushstyle_expressionist:
                effect_args = ["--expressionist"]
            elif settings.brushstyle_impressionist:
                effect_args = ["--impressionist"]
            elif settings.brushstyle_colorist:
                effect_args = ["--colorist_wash"]
            elif settings.brushstyle_pointillist:
                effect_args = ["--pointillist"]
            else:
                effect_args = ["--expressionist"]

        elif settings.active_option == 'OPTION_5':
            effect_id = "slicstylize"
            effect_args = [
                str(settings.slic_num_segments),
                str(settings.slic_compactness)
            ]

        if not effect_id:
            self.report({'WARNING'}, "Selected effect not implemented for normals.")
            return {'CANCELLED'}

        python_file = os.path.join(os.path.dirname(__file__), "run_effect_subprocess.py")
        args = [globals.PYTHON, python_file, effect_id, input_path, output_path] + effect_args + ["--normal"]

        try:
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                self.report({'ERROR'}, f"Effect subprocess failed:\n{result.stderr}")
                return {'CANCELLED'}

            new_img = bpy.data.images.load(output_path)
            new_img.colorspace_settings.name = 'Non-Color'
            normal_node.image = new_img

            # Update preview for normal maps
            globals.recolor_preview['main'].clear()
            globals.recolor_preview['main'].load("normalPreview", output_path, 'IMAGE')

            self.report({'INFO'}, f"Effect applied to normal map: {effect_id}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Subprocess failed: {e}")
            return {'CANCELLED'}


# ------------------------------------------------
# UI Layout Drawing Function
# ------------------------------------------------

def draw_normal_effect_layout(layout, context):
    settings = context.scene.texture2_settings
    layout.prop(settings, "active_option", text="Effect")

    if settings.active_option == 'OPTION_1':
        layout.prop(settings, "pixelate_downsample")
        layout.prop(settings, "pixelate_palette")

    elif settings.active_option == 'OPTION_2':
        layout.prop(settings, "vertical_brush_path")
        layout.prop(settings, "horizontal_brush_path")

    elif settings.active_option == 'OPTION_3':
        layout.prop(settings, "num_voronoi_patterns")
        layout.prop(settings, "oil_paint_size")
        layout.prop(settings, "oil_paint_dyn_ratio")
        layout.prop(settings, "use_bilateral_filter")

    elif settings.active_option == 'OPTION_4':
        box = layout.box()
        box.label(text="Brushstyle Presets")
        row1 = box.row()
        row1.prop(settings, "brushstyle_expressionist")
        row1.prop(settings, "brushstyle_impressionist")
        row2 = box.row()
        row2.prop(settings, "brushstyle_colorist")
        row2.prop(settings, "brushstyle_pointillist")

    elif settings.active_option == 'OPTION_5':
        layout.prop(settings, "slic_num_segments")
        layout.prop(settings, "slic_compactness")

    layout.operator("texture.apply_normal_effect", text="Apply Normal Effect")

    if "main" in globals.recolor_preview and "normalPreview" in globals.recolor_preview['main']:
        layout.template_icon(icon_value=globals.recolor_preview['main']['normalPreview'].icon_id, scale=6)
    else:
        layout.label(text="No normal preview available.")


# ------------------------------------------------
# Register
# ------------------------------------------------

def register():
    bpy.utils.register_class(TEXTURE_OT_apply_normal_effect)

def unregister():
    bpy.utils.unregister_class(TEXTURE_OT_apply_normal_effect)
