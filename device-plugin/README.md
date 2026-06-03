# device-plugin — SuperMD on the Supernote

On-device port of SuperMD as a Supernote plugin (`sn-plugin-lib`, React Native / TypeScript).
See [`../PORTING.md`](../PORTING.md) for the full architecture and roadmap.

## `spike/` — capability validation (Phase 0)

A throwaway plugin that empirically answers what the SDK actually allows on real hardware,
**before** building the full port. It runs 8 probes and writes the results to a log file.

### Probes

| ID | Validates | Gate |
| --- | --- | --- |
| P1 | `PluginManager.init()`, device type, plugin dir (the synced path to avoid for secrets) | — |
| P2 | Outbound HTTPS `fetch` to an LLM endpoint | **must pass** (existential) |
| P3 | `PluginFileAPI.generateNotePng` rasterizes a `.note` page natively | **must pass** (removes the decoder-port risk) |
| P4 | Writing `.md` to the Note tree / vault path | **must pass** |
| P5 | `event_pen_up` subscription + polling-scan cost | future/non-gating (initial scope is fully manual) |
| P6 | Ephemeral `react-native-tcp-socket` HTTP server (onboarding) | gates Phase 3 |
| P7 | `react-native-keychain` round-trip, device-local & non-synced | **must pass** |
| P8 | Native `getTitles`/`getKeyWords` + `insertImage` availability | informational |

### Build & run

```bash
cd device-plugin/spike
npm install
npm run typecheck          # tsc --noEmit, must be clean
npm run build              # react-native-builder-bob -> packageable output
# Package to .snplg per the Supernote plugin toolchain, sideload, open the plugin,
# tap "Run all probes".
```

### Reading results

Every probe line is mirrored to the on-screen log **and** to
`${DocumentDirectoryPath}/supermd-spike.log` on the device. Pull that file back (USB / sync)
and transcribe the outcomes into the "Spike results" table in [`../PORTING.md`](../PORTING.md).
That table is the gate for starting Phase 1.

> The `spike/` tree is intentionally disposable — once its findings are recorded in
> `PORTING.md`, it can be removed or replaced by the real plugin.
