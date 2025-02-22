# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN, Andrew Stevenson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy 

from .. import get_addon_prefs
from .boiler import create_new_nodegroup, link_sockets
from .utils import debug_draw_group


class EXTRANODES_NG_object_info_shader(bpy.types.ShaderNodeCustomGroup):
    """Custom Nodegroup: Gather informations about any camera.
    By default the camera will always use the active camera.
    Expect updates on each depsgraph post and frame_pre update signals"""

    bl_idname = "ShaderNodeExtraNodesObjectInfo"
    bl_label = "Object Info"

    def update_callback(self, context):
        self.update()

    use_self: bpy.props.BoolProperty(
        default=True,
        name="Use Self",
        description="Use the current object as the data source",
        update=update_callback
        )
    
    target_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        update=update_callback,
        )

    def active_obj_callback(self, context):
        if self.active_obj != "Self Object":
            self.active_obj = "Self Object"

        print(self)

    active_obj : bpy.props.StringProperty(
        default="Self Object",
        update=active_obj_callback
    )

    sockets = {
        "Location" : {"attr_name": "location", "location" : (0.0, 99.0), "type": "NodeSocketVector"},
        "Rotation" : {"attr_name": "EN_euler_rotation", "location" : (0.0, -22.0), "type": "NodeSocketVector"},
        "Scale" : {"attr_name": "scale", "location" : (0.0, -143.0), "type": "NodeSocketVector"},
    }

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True
    
    @property
    def tree_name(self):
        if self.use_self:
            return f".{self.bl_idname} - Self"
        elif (obj := self.target_obj) is None:
            return f".{self.bl_idname}"
        else:
            return f".{self.bl_idname} - {obj.name}"

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = self.tree_name
        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            out_sockets = {
                "Location" : "NodeSocketVector",
                "Rotation" : "NodeSocketVector",
                "Scale" : "NodeSocketVector",
            }

            ng = create_new_nodegroup(name, tree_type='ShaderNodeTree',
                out_sockets=out_sockets,
            )
            for target_name, target_data in self.sockets.items():
                node = ng.nodes.new("ShaderNodeAttribute")
                src = node.outputs["Vector"]

                node.name = target_name
                node.attribute_type = "OBJECT"
                node.attribute_name = target_data["attr_name"]
                node.location = target_data["location"]
                target = ng.nodes["Group Output"].inputs[target_name]
                for sock in node.outputs:
                    sock.hide = True
                link_sockets(src, target)
        
        self.node_tree = ng
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when duplicating the node"""
        return None

    def update_node_tree(self):
        tree = bpy.data.node_groups.get(self.tree_name)
        if (tree is None):
            tree = self.node_tree.copy()
            tree.name = self.tree_name

        if (tree.name != self.node_tree.name):
            self.node_tree = tree

        return tree

    def update(self):
        tree = self.update_node_tree()

        if not self.use_self:
            for target_name, target_data in self.sockets.items():
                node = tree.nodes[target_name]
                node.attribute_type = "VIEW_LAYER"

                if (obj := self.target_obj) is not None:
                    node.attribute_name = f'objects["{obj.name}"].{target_data["attr_name"]}'
        else:
            for target_name, target_data in self.sockets.items():
                node = tree.nodes[target_name]
                node.attribute_type = "OBJECT"
                node.attribute_name = target_data["attr_name"]

        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""
        
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.enabled = not self.use_self
        if (self.use_self):
            sub.prop(self, "active_obj", text="", icon="OBJECT_DATA")
        else: 
            sub.prop(self, "target_obj", text="", icon="OBJECT_DATA")
        
        row.prop(self, "use_self", text="", icon="SCENE_DATA")
        
        if get_addon_prefs("debug"):
            debug_draw_group(self, layout)

        return None

    def draw_buttons_ext(self, context, layout):
        """draw in the N panel when the node is selected"""
        
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.active = not self.use_self
        
        if (self.use_self):
            sub.prop(self, "active_obj", text="", icon="OBJECT_DATA")
        else: 
            sub.prop(self, "target_obj", text="", icon="OBJECT_DATA")
        
        row.prop(self, "use_self", text="", icon="SCENE_DATA")
    
        layout.separator(factor=1.2,type='LINE')
            
        col = layout.column(align=True)
        col.label(text="NodeTree:")
        col.template_ID(self, "node_tree")
        
    @classmethod
    def update_all(cls):
        """search for all nodes of this type and update them"""
        for material in bpy.data.materials:
            if (nodes := getattr(material.node_tree, "nodes", None)) is not None:
                for node in nodes:
                    if node.bl_idname==cls.bl_idname:
                        node.update()

        return None 
