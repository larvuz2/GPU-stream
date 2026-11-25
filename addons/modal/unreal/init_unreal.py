# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Puts Send to Blender in the Unreal Editor's Tools menu, as the editor starts.

The editor runs a file of this name from every folder on its Python path when
it starts (Epic's "Scripting the Unreal Editor Using Python"), so the session
puts this folder on that path and the entry is there in every project. The
entry runs `send_to_blender.menu_action`.
"""

import unreal

menus = unreal.ToolMenus.get()
tools = menus.extend_menu("LevelEditor.MainMenu.Tools")
tools.add_section("Moody", "Moody")
entry = unreal.ToolMenuEntry(name="MoodySendToBlender", type=unreal.MultiBlockType.MENU_ENTRY)
entry.set_label("Send to Blender")
entry.set_tool_tip("Export the selected actors, or the static meshes selected in the Content Browser, and import them into Blender.")
entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "", "import send_to_blender; send_to_blender.menu_action()")
tools.add_menu_entry("Moody", entry)
menus.refresh_all_widgets()
