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
from bpy.utils import previews

from .recolor import *
from .texture import *

from . import globals

class RecolourPanel(bpy.types.Panel):
    bl_label = 'Recolour'
    bl_idname = 'SNA_PT_Recolour_52FC0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = ''
    bl_category = 'Recolour'
    bl_order = 0
    bl_ui_units_x=0


    def draw(self, context):
        glob_layout = self.layout
        global temp, tries
        layout1 = glob_layout.box()
        draw_style_transfer_layout(layout1, context)

        layout2 = glob_layout.box()
        draw_palette_transfer(layout2, context)
   


def register():
    recolor.register()

    texture.register()

    bpy.utils.register_class(RecolourPanel)
    

    globals.recolor_preview['main'] = bpy.utils.previews.new()



def unregister():
    recolor.unregister()
    texture.unregister()

    bpy.utils.unregister_class(RecolourPanel)


    for pcoll in globals.recolor_preview.values():
        bpy.utils.previews.remove(pcoll)
    globals.recolor_preview.clear()


if __name__ == "__main__":
    register()
