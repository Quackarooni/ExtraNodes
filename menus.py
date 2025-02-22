# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy 

from .nodes import gn_node_classes, sh_node_classes


class EXTRANODES_MT_addmenu_general(bpy.types.Menu):

    bl_idname = "EXTRANODES_MT_addmenu_general"
    bl_label  = "Extra Nodes"

    @classmethod
    def poll(cls, context):
        return (context.space_data.tree_type in {'GeometryNodeTree', 'ShaderNodeTree'})

    def draw(self, context):
        tree_type = context.space_data.tree_type
        
        if tree_type == 'GeometryNodeTree':
            classes = gn_node_classes
        elif tree_type == 'ShaderNodeTree':
            classes = sh_node_classes
        else:
            raise ValueError(f"{tree_type} is not a supported node tree type")

        for cls in classes:
            if ('_NG_' in cls.__name__):
                op = self.layout.operator("node.add_node", text=cls.bl_label,)
                op.type = cls.bl_idname
                op.use_transform = True
        
        return None


def extranodes_addmenu_append(self, context,):
    
    self.layout.menu("EXTRANODES_MT_addmenu_general", text="Extra Nodes",)
    
    return None 


def append_menus():

    menu = bpy.types.NODE_MT_add
    menu.append(extranodes_addmenu_append)

    return None 


def remove_menus():

    menu = bpy.types.NODE_MT_add
    for f in menu._dyn_ui_initialize().copy():
        if (f.__name__=='extranodes_addmenu_append'):
            menu.remove(f)
            continue
    
    return None


classes = (
    
    EXTRANODES_MT_addmenu_general,
    
    )