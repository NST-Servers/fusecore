from babase._appsubsystem import AppSubsystem
import babase._plugin as base_plugin

base_plugin.PluginSubsystem # TODO: disable 'PluginSubsystem'

class ModLoaderSubsytem(AppSubsystem):
    """Subsystem in charge of reading, categorizing
    and readying custom-made mods.
    """