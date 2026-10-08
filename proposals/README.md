Core has no `hyprpm.toml`. The adjacent file proposes its build entry; it is
**not ready to ship**. Core embeds a build-directory daemon path, while hyprpm
copies only the plugin output. Add a core-owned relocatable/installable helper
path before adopting this manifest, then test hyprpm staging and updates against
0.56.2. The meta flake and script patch that path in their private build sources
and install both outputs together. No component checkout is modified.
