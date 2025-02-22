def debug_draw_group(self, layout):
    row = layout.row()
    row.enabled = False
    row.template_ID(self, "node_tree")