import bpy

def fetch_user_preferences():
    return bpy.context.preferences.addons[__package__].preferences