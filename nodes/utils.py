def debug_draw_group(self, layout):
    row = layout.row()
    row.enabled = False
    row.template_ID(self, "node_tree")


def UI_image_selector(self, layout, prop_name):
    layout.template_ID(self, prop_name, new="image.new", open="image.open")