import bpy
import subprocess
import os
import uuid
from bpy.utils import previews
from . import globals

# Preview cache
recolor_preview = {}

# ----------------------------
# UI Settings
# ----------------------------

class Texture2Settings(bpy.types.PropertyGroup):
    active_option: bpy.props.EnumProperty(
        name="Select Effect",
        items=[
            ('OPTION_1', "Pixelate Image", ""),
            ('OPTION_2', "Neural Painter Style", ""),
            ('OPTION_3', "Voronoi Watercolor Style", ""),
            ('OPTION_4', "Brushstyle Painterly Effect", ""),
            ('OPTION_5', "SLIC Normal Stylizer", ""),  # 🔹 New option
            ('OPTION_RESET', "Restore Original Texture", "")
        ],
        default='OPTION_1'
    )
    
    

    # Pixelate
    pixelate_downsample: bpy.props.IntProperty(name="Downsample Ratio", default=4, min=1, max=32)
    pixelate_palette: bpy.props.IntProperty(name="Palette Size", default=7, min=2, max=64)


    slic_num_segments: bpy.props.IntProperty(name="Number of Segments", default=300, min=10, max=1000)
    slic_compactness: bpy.props.IntProperty(name="Compactness", default=50, min=1, max=100)

    # Neural Painter
    vertical_brush_path: bpy.props.StringProperty(
        name="Vertical Brush Map",
        description="Path to vertical brush texture",
        subtype='FILE_PATH'
    )
    horizontal_brush_path: bpy.props.StringProperty(
        name="Horizontal Brush Map",
        description="Path to horizontal brush texture",
        subtype='FILE_PATH'
    )

    # Voronoi
    num_voronoi_patterns: bpy.props.IntProperty(name="Number of Voronoi Patterns", default=3, min=1, max=20)
    oil_paint_size: bpy.props.IntProperty(name="Oil Paint Size", default=12, min=1, max=50)
    oil_paint_dyn_ratio: bpy.props.IntProperty(name="Oil Paint Dynamic Ratio", default=10, min=1, max=50)
    use_bilateral_filter: bpy.props.BoolProperty(name="Use Bilateral Filter", default=True)

    # Brushstyle checkboxes
    brushstyle_expressionist: bpy.props.BoolProperty(name="Expressionist")
    brushstyle_impressionist: bpy.props.BoolProperty(name="Impressionist")
    brushstyle_colorist: bpy.props.BoolProperty(name="Colorist Wash")
    brushstyle_pointillist: bpy.props.BoolProperty(name="Pointillist")


# ----------------------------
# Operator
# ----------------------------

class TEXTURE2_OT_ApplyEffect(bpy.types.Operator):
    bl_idname = "texture2.apply_effect"
    bl_label = "Apply Albedo Effect"

    def execute(self, context):
        obj = context.object
        settings = context.scene.texture2_settings

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        mat = obj.active_material
        if not mat or not mat.use_nodes:
            self.report({'ERROR'}, "Material must use nodes.")
            return {'CANCELLED'}

        from_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                base_color = node.inputs.get("Base Color")
                if base_color and base_color.is_linked:
                    from_node = base_color.links[0].from_node
                    break

        if not from_node or from_node.type != 'TEX_IMAGE' or not from_node.image:
            self.report({'ERROR'}, "Base Color must be linked to an image.")
            return {'CANCELLED'}

        if(from_node.image.filepath == ""):
            input_path = os.path.dirname(bpy.data.filepath) + "/new_palette" + "/abstruction.png"
            from_node.image.save(filepath = input_path)
        else:
            input_path = bpy.path.abspath(from_node.image.filepath)

        # Store original texture path
        if "original_albedo_path" not in obj:
            obj["original_albedo_path"] = input_path

        if settings.active_option == 'OPTION_RESET':
            if "original_albedo_path" in obj:
                original_path = obj["original_albedo_path"]
                if os.path.exists(original_path):
                    original_img = bpy.data.images.load(original_path)
                    from_node.image = original_img
                    recolor_preview['main'].clear()
                    recolor_preview['main'].load("textureSelected", original_path, "IMAGE")
                    self.report({'INFO'}, "Original texture restored.")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, "Original texture file not found.")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "No original texture path recorded.")
                return {'CANCELLED'}

        # Effect setup
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Save your .blend file first.")
            return {'CANCELLED'}

        save_dir = os.path.join(os.path.dirname(blend_path), "effect_outputs")
        os.makedirs(save_dir, exist_ok=True)
        output_path = os.path.join(save_dir, f"effect_{uuid.uuid4().hex}.png")

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
                effect_args = ["--expressionist"]  # fallback


        elif settings.active_option == 'OPTION_5':
            effect_id = "slicstylize"
            effect_args = [
                str(settings.slic_num_segments),
                str(settings.slic_compactness)
            ]
        python_file = os.path.join(os.path.dirname(__file__), "run_effect_subprocess.py")
        args = [globals.PYTHON, python_file, effect_id, input_path, output_path] + effect_args

        try:
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0 or result.stdout.strip() == "":
                self.report({'ERROR'}, "Effect subprocess failed.")
                print("hi" + result.stdout.strip() + "ih")
                self.report({'ERROR'}, result.stderr)
                return {'CANCELLED'}

            new_img = bpy.data.images.load(output_path)
            from_node.image = new_img
            recolor_preview['main'].clear()
            recolor_preview['main'].load("textureSelected", output_path, "IMAGE")
            self.report({'INFO'}, f"Effect applied: {effect_id}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to run subprocess: {e}")
            return {'CANCELLED'}


# ----------------------------
# UI Layout
# ----------------------------

def draw_geometric_abstraction_layout(layout, context):
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

    layout.operator("texture2.apply_effect", text="Apply Effect")

    if "main" in recolor_preview and "textureSelected" in recolor_preview['main']:
        layout.template_icon(icon_value=recolor_preview['main']['textureSelected'].icon_id, scale=6)
    else:
        layout.label(text="No image preview available.")


# ----------------------------
# Register / Unregister
# ----------------------------

classes = (
    Texture2Settings,
    TEXTURE2_OT_ApplyEffect,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.texture2_settings = bpy.props.PointerProperty(type=Texture2Settings)
    recolor_preview['main'] = previews.new()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.texture2_settings
    for pcoll in recolor_preview.values():
        previews.remove(pcoll)
    recolor_preview.clear()
