bl_info = {
    "name": "Texture Editor",
    "description": "A modular texture editing toolkit for albedo and normal maps",
    "blender": (3, 0, 0),
    "version": (1, 0, 1),
    "location": "View3D > Sidebar > Recolour",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "3D View"
}

import bpy
import subprocess
import os
from bpy.utils import previews

# Local modules
from . import globals
from . import recolor
from . import texture
from . import abstruction
from . import normal


# ----------------------------------------------------------------------
# Main Panel
# ----------------------------------------------------------------------

class PedroVersePanel(bpy.types.Panel):
    bl_label = 'PedroVerse'
    bl_idname = 'SNA_PT_PedroVerse_52FC0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'PedroVerse'
    bl_order = 0
    bl_ui_units_x = 0

    def draw(self, context):
        layout = self.layout

        # Style Transfer
        layout1 = layout.box()
        layout1.label(text="Style Transfer")
        texture.draw_style_transfer_layout(layout1, context)

        # Palette Transfer
        layout2 = layout.box()
        layout2.label(text="Palette Transfer")
        recolor.draw_palette_transfer(layout2, context)

        # Geometric Abstraction
        layout3 = layout.box()
        layout3.label(text="Geometric Abstraction")
        try:
            abstruction.draw_geometric_abstraction_layout(layout3, context)
        except Exception:
            layout3.label(text="Error loading abstraction layout")
            import traceback
            traceback.print_exc()

        # Normal Map Effects
        layout4 = layout.box()
        layout4.label(text="Normals")
        try:
            normal.draw_normal_effect_layout(layout4, context)
        except Exception:
            layout4.label(text="Error loading normal effect layout")
            import traceback
            traceback.print_exc()


# ----------------------------------------------------------------------
# Register / Unregister
# ----------------------------------------------------------------------

def register():
    # Run newer.py using the venv
    recolor.register()
    texture.register()
    abstruction.register()
    normal.register()

    bpy.utils.register_class(PedroVersePanel)
    globals.recolor_preview['main'] = previews.new()


def unregister():
    recolor.unregister()
    texture.unregister()
    abstruction.unregister()
    normal.unregister()

    bpy.utils.unregister_class(PedroVersePanel)
    for pcoll in globals.recolor_preview.values():
        previews.remove(pcoll)
    globals.recolor_preview.clear()


if __name__ == "__main__":
    register()
