import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel

FOLDER_NAME = "animationHelper"
SHELF_COMMAND = "animationHelper"
SHELF_ANNOTATION = "Animation Helper"

PLATFORM_DIRS = {
    "win32": "Windows",
    "darwin": "Mac",
    "linux": "Linux",
}

PLUGIN_EXTENSIONS = {
    "win32": ".mll",
    "darwin": ".bundle",
    "linux": ".so",
}


def onMayaDroppedPythonFile(*args):
    main()


def log(message):
    print(f"[Animation Helper Installer] {message}")


def get_installer_root():
    return os.path.dirname(os.path.abspath(__file__))


def get_general_maya_scripts_dir():
    user_app_dir = cmds.internalVar(userAppDir=True)
    maya_user_dir = os.path.dirname(user_app_dir)
    scripts_dir = os.path.join(maya_user_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    return scripts_dir


def get_platform_folder():
    platform_key = sys.platform
    folder = PLATFORM_DIRS.get(platform_key)
    if not folder:
        cmds.confirmDialog(
            t=SHELF_ANNOTATION,
            m=f"Unsupported platform: {platform_key}",
            button=["Ok"],
        )
        return None
    return folder


def read_version_file(path):
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as handle:
        version = handle.read().strip()

    return version or None


def parse_version(version_string):
    return tuple(int(part) for part in version_string.strip().split("."))


def is_newer_version(new_version, old_version):
    return parse_version(new_version) > parse_version(old_version)


def versions_equal(first_version, second_version):
    return parse_version(first_version) == parse_version(second_version)


def normalize_path(path):
    if not path:
        return ""

    return os.path.normcase(os.path.normpath(os.path.abspath(path.replace("/", os.sep))))


def get_expected_icon_path(dst):
    icon_path = os.path.join(dst, "icons", "animationHelperIcon.png")
    if os.path.isfile(icon_path):
        return icon_path

    return os.path.join(dst, "animationHelperIcon.png")


def get_visible_shelf_tab():
    shelf_top = mel.eval("$tmpVar=$gShelfTopLevel")
    tabs = cmds.tabLayout(shelf_top, query=True, childArray=True) or []

    for tab in tabs:
        if cmds.shelfLayout(tab, query=True, visible=True):
            return tab

    return None


def is_plugin_shelf_button(button):
    if not cmds.objExists(button):
        return False

    if cmds.control(button, query=True, type=True) != "shelfButton":
        return False

    command = (cmds.shelfButton(button, query=True, command=True) or "").strip()
    annotation = cmds.shelfButton(button, query=True, annotation=True) or ""

    return command == SHELF_COMMAND or FOLDER_NAME in command or annotation == SHELF_ANNOTATION


def find_plugin_shelf_button(shelf_tab):
    for child in cmds.shelfLayout(shelf_tab, query=True, childArray=True) or []:
        if is_plugin_shelf_button(child):
            return child

    return None


def shelf_button_needs_fix(button, expected_icon_path):
    command = (cmds.shelfButton(button, query=True, command=True) or "").strip()
    source_type = cmds.shelfButton(button, query=True, sourceType=True)
    image = cmds.shelfButton(button, query=True, image=True) or ""
    image1 = cmds.shelfButton(button, query=True, image1=True) or image
    expected = normalize_path(expected_icon_path)

    if command != SHELF_COMMAND:
        return True

    if source_type != "mel":
        return True

    if normalize_path(image) != expected and normalize_path(image1) != expected:
        return True

    return False


def create_shelf_button(shelf_tab, icon_path):
    cmds.shelfButton(
        parent=shelf_tab,
        image=icon_path,
        image1=icon_path,
        style="iconOnly",
        ann=SHELF_ANNOTATION,
        useAlpha=True,
        command=SHELF_COMMAND,
        sourceType="mel",
    )


def fix_shelf_button(button, icon_path):
    cmds.shelfButton(
        button,
        edit=True,
        image=icon_path,
        image1=icon_path,
        style="iconOnly",
        ann=SHELF_ANNOTATION,
        useAlpha=True,
        command=SHELF_COMMAND,
        sourceType="mel",
    )


def ensure_shelf_button(dst):
    log("Checking shelf button on the active shelf tab...")

    icon_path = get_expected_icon_path(dst)
    if not os.path.isfile(icon_path):
        log(f"Expected icon not found: {icon_path}")
        return

    log(f"Expected icon path: {icon_path}")

    shelf_tab = get_visible_shelf_tab()
    if not shelf_tab:
        log("No visible shelf tab found.")
        return

    log(f"Active shelf tab: {shelf_tab}")

    existing_button = find_plugin_shelf_button(shelf_tab)
    if existing_button:
        log(f"Found existing shelf button: {existing_button}")

        command = (cmds.shelfButton(existing_button, query=True, command=True) or "").strip()
        source_type = cmds.shelfButton(existing_button, query=True, sourceType=True)
        image = cmds.shelfButton(existing_button, query=True, image=True) or ""
        log(f"Current command: {command!r}")
        log(f"Current sourceType: {source_type!r}")
        log(f"Current icon: {image}")

        if shelf_button_needs_fix(existing_button, icon_path):
            log("Shelf button needs fix. Updating icon and command...")
            fix_shelf_button(existing_button, icon_path)
            log("Shelf button updated.")
        else:
            log("Shelf button is already correct. No changes needed.")
        return

    log("No shelf button found on the active shelf tab. Creating a new one...")
    create_shelf_button(shelf_tab, icon_path)
    log("Shelf button created.")


def handle_fresh_install_case(src, dst, installer_root, installer_version):
    log("Fresh install: animationHelper not found in scripts folder.")

    if not os.path.isdir(src):
        log(f"Source folder not found: {src}")
        cmds.confirmDialog(
            t=SHELF_ANNOTATION,
            m=(
                f"Folder not found:\n{src}\n\n"
                f"Expected platform folder with {FOLDER_NAME} next to installer."
            ),
            button=["Ok"],
        )
        return

    try:
        log(f"Copying from: {src}")
        log(f"Copying to: {dst}")
        shutil.copytree(src, dst)
        log("Copy finished.")

        merge_icons_folder(installer_root, dst)
        log("Icons folder merged.")

        installed_version_path = os.path.join(dst, "version.txt")
        write_version_file(installed_version_path, installer_version)
        log(f"Version file written: {installed_version_path} ({installer_version})")

        plugin_ok, plugin_msg = load_plugin_if_needed(dst)
        log(plugin_msg)

        ensure_shelf_button(dst)

        if plugin_ok:
            log("Opening Animation Helper...")
            cmds.animationHelper()
    except Exception as exc:
        log(f"Fresh install failed: {exc}")
        cmds.confirmDialog(
            t=SHELF_ANNOTATION,
            m=f"Install failed:\n{exc}",
            button=["Ok"],
        )
        return

    log("Fresh install finished.")


def handle_same_version_case(dst):
    log("Case 1: Same version already installed.")
    log("Skipping copy/install. Running shelf checks only...")
    ensure_shelf_button(dst)
    log("Case 1 finished.")


def is_plugin_loaded():
    plugins = cmds.pluginInfo(query=True, listPlugins=True) or []
    if FOLDER_NAME not in plugins:
        return False
    return cmds.pluginInfo(FOLDER_NAME, query=True, loaded=True)


def unload_plugin_if_loaded():
    if is_plugin_loaded():
        cmds.pluginInfo(FOLDER_NAME, edit=True, autoload=False)
        cmds.unloadPlugin(FOLDER_NAME, force=True)


def copy_plugins_replace(src_parent, dst_parent):
    src = os.path.join(src_parent, "plugins")
    if not os.path.isdir(src):
        return

    dst = os.path.join(dst_parent, "plugins")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_version_file(path, version):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"{version}\n")


def merge_icons_folder(installer_root, dst):
    icons_src = os.path.join(installer_root, "icons")
    icons_dst = os.path.join(dst, "icons")

    if not os.path.isdir(icons_src):
        return

    if os.path.isdir(icons_dst):
        shutil.rmtree(icons_dst)

    shutil.copytree(icons_src, icons_dst)


def install_or_update(src, dst, installer_root):
    unload_plugin_if_loaded()

    if os.path.isdir(dst):
        copy_plugins_replace(src, dst)
        merge_icons_folder(installer_root, dst)
    else:
        shutil.copytree(src, dst)
        merge_icons_folder(installer_root, dst)


def get_plugin_path(dst):
    maya_version = cmds.about(version=True)
    plugin_dir = os.path.join(dst, "plugins", maya_version)
    if not os.path.isdir(plugin_dir):
        return None

    ext = PLUGIN_EXTENSIONS.get(sys.platform)
    if not ext:
        return None

    plugin_path = os.path.join(plugin_dir, FOLDER_NAME + ext)
    if os.path.isfile(plugin_path):
        return plugin_path

    for name in os.listdir(plugin_dir):
        if name.startswith(FOLDER_NAME) and name.endswith(ext):
            return os.path.join(plugin_dir, name)

    return None


def load_plugin_if_needed(dst):
    plugin_path = get_plugin_path(dst)
    if not plugin_path:
        maya_version = cmds.about(version=True)
        return False, f"No plugin found for Maya {maya_version}."

    if is_plugin_loaded():
        cmds.pluginInfo(FOLDER_NAME, edit=True, autoload=True)
        return True, "Plugin already loaded."

    cmds.loadPlugin(plugin_path)
    cmds.pluginInfo(FOLDER_NAME, edit=True, autoload=True)
    return True, f"Plugin loaded from:\n{plugin_path}"


def main():
    log("Starting installer...")

    installer_root = get_installer_root()
    log(f"Installer root: {installer_root}")

    platform_folder = get_platform_folder()
    if not platform_folder:
        log("Unsupported platform. Stopping.")
        return

    log(f"Platform folder: {platform_folder}")

    scripts_dir = get_general_maya_scripts_dir()
    dst = os.path.join(scripts_dir, FOLDER_NAME)
    log(f"Installed destination: {dst}")

    installer_version_path = os.path.join(installer_root, "version.txt")
    installer_version = read_version_file(installer_version_path)
    if not installer_version:
        log(f"Installer version file not found: {installer_version_path}")
        cmds.confirmDialog(
            t=SHELF_ANNOTATION,
            m="Installer version file not found.",
            button=["Ok"],
        )
        return

    log(f"Installer version: {installer_version}")

    src = os.path.join(installer_root, platform_folder, FOLDER_NAME)
    log(f"Source folder: {src}")

    if not os.path.isdir(dst):
        handle_fresh_install_case(src, dst, installer_root, installer_version)
        log("Installer finished.")
        return

    log("Installed animationHelper folder found.")

    installed_version_path = os.path.join(dst, "version.txt")
    installed_version = read_version_file(installed_version_path)
    if not installed_version:
        log(f"Installed version file not found: {installed_version_path}")
        log("Stopping for now.")
        return

    log(f"Installed version: {installed_version}")

    if is_newer_version(installer_version, installed_version):
        log(
            "New update is available, but update flow is not implemented yet. Stopping."
        )
        return

    log("No new update available.")

    if not versions_equal(installer_version, installed_version):
        log(
            "Installer version does not match installed version. "
            "This case is not handled yet. Stopping."
        )
        return

    log("Installed version matches installer version.")
    handle_same_version_case(dst)
    log("Installer finished.")

