# SPDX-FileCopyrightText: 2025 BD3D DIGITAL DESIGN
#
# SPDX-License-Identifier: GPL-2.0-or-later


from . camerainfo import EXTRANODES_NG_camerainfo
from . isrenderedview import EXTRANODES_NG_isrenderedview
from . sequencervolume import EXTRANODES_NG_sequencervolume
from . mathexpression import EXTRANODES_NG_mathexpression, EXTRANODES_OT_bake_mathexpression
from . pythonapi import EXTRANODES_NG_pythonapi
from . object_info_shader import EXTRANODES_NG_object_info_shader


gn_node_classes = (
    EXTRANODES_NG_camerainfo,
    EXTRANODES_NG_isrenderedview,
    EXTRANODES_NG_sequencervolume,
    EXTRANODES_NG_mathexpression,
    EXTRANODES_OT_bake_mathexpression, 
    EXTRANODES_NG_pythonapi,
)

sh_node_classes = (
    EXTRANODES_NG_object_info_shader,
)


#NOTE order will be order of appearance in addmenu
classes = (
    *gn_node_classes,
    *sh_node_classes,
    )