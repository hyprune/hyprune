# Owner release decisions

1. Publish the recorded core/shell/sdk/schema/docs/worlds commits, then make the
   repositories public or document private access. No work in this repo is pushed
   automatically. Review the existing component working-tree changes separately.
2. **Done (2026-10-08):** worlds are published as GitHub Releases on
   `hyprune/worlds`, tagged `<world>-v<version>` with the `.tar.zst` archive and a
   `.sha256` file: `lumen-reach-v0.4.0` and `switchyard-v0.1.1`.
   `worlds/releases.json` holds the real URLs, hex SHA-256 and SRI `nixHash`.
   The archives download publicly once `hyprune/worlds` is made public.
3. Build `world-lumen-reach`, `world-switchyard`, `kit-lumen-reach` and `kit-dev`;
   run the optional CI dispatch with `release_worlds = true`. The zero hash is a
   deliberate placeholder; it must never be copied into an actual release.
4. Complete core's supervised DRM/hardware-cursor checklist before recommending
   the first live-session install. Container software rendering is separate
   evidence, not a substitute for it. Decide the first supported Arch package
   snapshot for 0.56.2; Fedora/Debian script packaging remains future work.
5. Decide whether to move the small trusted session launcher into core and add
   token renewal/shell recovery. Current credentials stay in inherited pipes;
   shell reconnect needs a fresh session. UWSM integration requires an explicit
   inherited-FD handoff and must not be enabled by pretending a systemd service
   can recreate launch grants.
6. Wire `docs/zero-to-the-trailer.md` into the site and copy its `images/` files
   with `provenance.json`. Decide whether Switchyard should gain typed workspace
   areas; the dev kit currently reports its legacy limitation.

Convert a verified archive hash to Nix SRI without fetching anything:

```sh
nix hash convert --hash-algo sha256 --to sri YOUR_64_HEX_SHA256
```

The [hyprpm proposal](../proposals/README.md) needs a relocatable helper path in
core before it can become a real component manifest. No component edits are
required for this meta repo's current packaging.
