# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN, Andrew Stevenson
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy 

from ..__init__ import get_addon_prefs
from .boiler import create_new_nodegroup, set_socket_defvalue
from .utils import debug_draw_group


class EXTRANODES_NG_camerainfo(bpy.types.GeometryNodeCustomGroup):
    """Custom Nodegroup: Gather informations about any camera.
    By default the camera will always use the active camera.
    Expect updates on each depsgraph post and frame_pre update signals"""

    bl_idname = "GeometryNodeExtraNodesCameraInfo"
    bl_label = "Camera Info"
    bl_width_default = 150

    use_scene_cam: bpy.props.BoolProperty(
        default=True,
        name="Use Active Camera",
        description="Automatically update the pointer to the active scene camera",
        )

    def camera_obj_poll(self, obj):
        return obj.type == 'CAMERA'

    camera_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=camera_obj_poll,
        )

    @classmethod
    def poll(cls, context):
        """mandatory poll"""
        return True

    def init(self, context):
        """this fct run when appending the node for the first time"""

        name = f".{self.bl_idname}"

        ng = bpy.data.node_groups.get(name)
        if (ng is None):
            ng = create_new_nodegroup(name,
                out_sockets={
                    "Camera Object" : "NodeSocketObject",
                    "Field of View" : "NodeSocketFloat",
                    "Shift X" : "NodeSocketFloat",
                    "Shift Y" : "NodeSocketFloat",
                    "Clip Start" : "NodeSocketFloat",
                    "Clip End" : "NodeSocketFloat",
                    "Resolution X" : "NodeSocketInt",
                    "Resolution Y" : "NodeSocketInt",
                },
            )
         
        ng = ng.copy() #always using a copy of the original ng
        
        self.node_tree = ng
        self.label = self.bl_label

        return None

    def copy(self, node):
        """fct run when duplicating the node"""
        
        self.node_tree = node.node_tree.copy()
        
        return None
    
    def free(self):
        if self.node_tree.users <= 1:
            bpy.data.node_groups.remove(self.node_tree)

    def update(self):
        """generic update function"""

        scene = bpy.context.scene
        cam_obj = scene.camera if (self.use_scene_cam) else self.camera_obj
        set_socket_defvalue(self.node_tree, 0, value=cam_obj)
        
        if (cam_obj and cam_obj.data):
            set_socket_defvalue(self.node_tree, 1, value=cam_obj.data.angle)
            set_socket_defvalue(self.node_tree, 2, value=cam_obj.data.shift_x)
            set_socket_defvalue(self.node_tree, 3, value=cam_obj.data.shift_y)
            set_socket_defvalue(self.node_tree, 4, value=cam_obj.data.clip_start)
            set_socket_defvalue(self.node_tree, 5, value=cam_obj.data.clip_end)
            set_socket_defvalue(self.node_tree, 6, value=scene.render.resolution_x)
            set_socket_defvalue(self.node_tree, 7, value=scene.render.resolution_y)

        return None

    def draw_label(self,):
        """node label"""
        
        return self.bl_label

    def draw_buttons(self, context, layout):
        """node interface drawing"""
        
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.active = not self.use_scene_cam
        
        if (self.use_scene_cam):
              sub.prop(bpy.context.scene, "camera", text="", icon="CAMERA_DATA")
        else: sub.prop(self, "camera_obj", text="", icon="CAMERA_DATA")
        
        row.prop(self, "use_scene_cam", text="", icon="SCENE_DATA")

        if get_addon_prefs("debug"):
            debug_draw_group(self, layout)

        return None

    def draw_buttons_ext(self, context, layout):
        """draw in the N panel when the node is selected"""
        
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.active = not self.use_scene_cam
        
        if (self.use_scene_cam):
              sub.prop(bpy.context.scene, "camera", text="", icon="CAMERA_DATA")
        else: sub.prop(self, "camera_obj", text="", icon="CAMERA_DATA")
        
        layout.prop(self, "use_scene_cam",)
    
        layout.separator(factor=1.2,type='LINE')
            
        col = layout.column(align=True)
        col.label(text="NodeTree:")
        col.template_ID(self, "node_tree")
        
    @classmethod
    def update_all(cls):
        """search for all nodes of this type and update them"""
        
        for n in [n for ng in bpy.data.node_groups for n in ng.nodes if (n.bl_idname==cls.bl_idname)]:
            n.update()
            
        return None 
