import com.zondy.mapgis.pluginengine.plugincollection.PluginContainer;

/** Run with the installed SDK and packaged plugin, without starting a licensed GIS session. */
public class PluginRegistrationProbe {
    public static void main(String[] args) {
        if (args.length != 1) throw new IllegalArgumentException("Expected plugin JAR path");
        PluginContainer container = new PluginContainer();
        container.loadPackage(args[0]);
        String prefix = "com.zondy.mapgis.floodguard.plugin.";
        if (!container.getCommands().containsKey(prefix + "FloodInferenceCommand"))
            throw new IllegalStateException("Flood command was not registered by the installed SDK");
        var command = container.getCommands().get(prefix + "FloodInferenceCommand");
        // The host snapshots isEnabled BEFORE invoking onCreate.
        if (!command.isEnabled())
            throw new IllegalStateException("Command would be disabled before host initialization");
        if (!container.getRibbonPages().containsKey(prefix + "FloodRibbonPage"))
            throw new IllegalStateException("Flood ribbon page was not registered");
        if (!container.getRibbonPageGroups().containsKey(prefix + "FloodRibbonGroup"))
            throw new IllegalStateException("Flood ribbon group was not registered");
        System.out.println("PASS: installed SDK registered command/page/group and command enabled before onCreate; GUI not tested.");
    }
}
