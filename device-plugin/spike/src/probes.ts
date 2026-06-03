/**
 * The capability probes. Each probe is self-contained, never throws, and returns
 * a ProbeResult. Intermediate findings are streamed via logLine so the on-device
 * log captures everything even if a probe hangs or the app is killed.
 *
 * These probes exercise the REAL sn-plugin-lib SDK (discovered by reading its
 * bundled .d.ts files), not generic stand-ins. The headline questions:
 *
 *   - Does PluginFileAPI.generateNotePng actually rasterize a page on-device?
 *     (If yes, we never port the supernotelib decoder — the biggest risk is gone.)
 *   - Can we fetch() out to an LLM? (existential)
 *   - Is pen_up the only trigger, and is polling viable as a fallback?
 *   - Can we store the API key in non-synced secure storage?
 *
 * Decision gate (see PORTING.md): P2/P3/P4/P7 must pass to proceed to Phase 1.
 * P6 gates the onboarding web server. P5 decides the auto-trigger strategy.
 * P8 is informational/non-blocking.
 */
import RNFS from 'react-native-fs';
import * as Keychain from 'react-native-keychain';
import TcpSocket from 'react-native-tcp-socket';
import { NetworkInfo } from 'react-native-network-info';
import {
  PluginManager,
  PluginFileAPI,
  PluginNoteAPI,
} from 'sn-plugin-lib';

import { ProbeResult, ProbeStatus, logLine } from './log';

/** Candidate roots where Supernote stores notes — probed in order. */
const NOTE_ROOTS = [
  '/storage/emulated/0/Note',
  '/storage/emulated/0/Supernote/Note',
  '/storage/emulated/0/Document',
  '/storage/emulated/0',
];

/** Supernote .note file signatures (see supernotelib/parser.py). */
const NOTE_SIGNATURES = ['noteSN_FILE_VER_', 'SN_FILE_ASA_', 'note'];

/** SDK calls return an APIResponse-shaped object; normalize it for logging. */
function fmtResponse(r: unknown): string {
  if (r && typeof r === 'object') {
    const o = r as { success?: boolean; result?: unknown; error?: unknown };
    if ('success' in o || 'result' in o) {
      return `success=${o.success} result=${JSON.stringify(o.result)}${
        o.error ? ` error=${JSON.stringify(o.error)}` : ''
      }`;
    }
  }
  return JSON.stringify(r);
}

function isOk(r: unknown): boolean {
  return Boolean(r && typeof r === 'object' && (r as { success?: boolean }).success);
}

async function timed(
  id: string,
  title: string,
  fn: () => Promise<{ status: ProbeStatus; detail: string }>,
): Promise<ProbeResult> {
  const start = Date.now();
  try {
    const { status, detail } = await fn();
    return { id, title, status, detail, durationMs: Date.now() - start };
  } catch (err) {
    const detail = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    return { id, title, status: 'fail', detail, durationMs: Date.now() - start };
  }
}

/** Decode a base64 string to a Latin-1/ASCII string (enough to read a signature). */
function base64ToAscii(b64: string): string {
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let out = '';
  const clean = b64.replace(/[^A-Za-z0-9+/]/g, '');
  for (let i = 0; i < clean.length; i += 4) {
    const e1 = chars.indexOf(clean[i]);
    const e2 = chars.indexOf(clean[i + 1]);
    const e3 = chars.indexOf(clean[i + 2]);
    const e4 = chars.indexOf(clean[i + 3]);
    const c1 = (e1 << 2) | (e2 >> 4);
    const c2 = ((e2 & 15) << 4) | (e3 >> 2);
    const c3 = ((e3 & 3) << 6) | e4;
    out += String.fromCharCode(c1);
    if (e3 !== -1) out += String.fromCharCode(c2);
    if (e4 !== -1) out += String.fromCharCode(c3);
  }
  return out;
}

// ---------------------------------------------------------------------------
// P1 — SDK bridge: init + device/plugin info. Also surfaces the (synced) plugin
//      dir so we know which path must NOT hold secrets.
// ---------------------------------------------------------------------------
export async function probeSdkBridge(): Promise<ProbeResult> {
  return timed('P1', 'sn-plugin-lib bridge', async () => {
    await PluginManager.init();
    const [deviceType, name, dir] = await Promise.all([
      PluginManager.getDeviceType().catch((e) => `err:${e}`),
      PluginManager.getPluginName().catch((e) => `err:${e}`),
      PluginManager.getPluginDirPath().catch((e) => `err:${e}`),
    ]);
    await logLine(`P1 deviceType=${deviceType} name=${name}`);
    await logLine(`P1 pluginDir=${dir}  <-- secrets MUST NOT live here (it syncs)`);
    return {
      status: 'pass',
      detail: `init OK; deviceType=${deviceType}, pluginDir=${dir}`,
    };
  });
}

// ---------------------------------------------------------------------------
// P2 — Outbound HTTPS fetch. EXISTENTIAL: no egress => no on-device LLM.
// ---------------------------------------------------------------------------
export async function probeFetch(apiKey?: string): Promise<ProbeResult> {
  return timed('P2', 'outbound HTTPS fetch', async () => {
    const url = apiKey
      ? 'https://api.openai.com/v1/models'
      : 'https://httpbin.org/get';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
        signal: controller.signal,
      });
      const body = (await resp.text()).slice(0, 200);
      await logLine(`P2 ${url} -> HTTP ${resp.status}; body[0:200]=${body}`);
      // Any HTTP response (even 401/403) proves the network path works.
      return { status: 'pass', detail: `HTTP ${resp.status} from ${url} — egress works` };
    } finally {
      clearTimeout(timeout);
    }
  });
}

// ---------------------------------------------------------------------------
// P3 — Native page rasterization (THE key enabler). If generateNotePng works,
//      we never port the supernotelib decoder.
// ---------------------------------------------------------------------------
async function findFirstNote(): Promise<{ root: string; path: string } | null> {
  for (const root of NOTE_ROOTS) {
    try {
      if (!(await RNFS.exists(root))) {
        await logLine(`P3 root ${root}: does not exist`);
        continue;
      }
      const entries = await RNFS.readDir(root);
      await logLine(`P3 root ${root}: ${entries.length} entries`);
      const note = entries.find((e) => e.isFile() && e.name.endsWith('.note'));
      if (note) return { root, path: note.path };
      for (const dir of entries.filter((e) => e.isDirectory()).slice(0, 20)) {
        try {
          const sub = await RNFS.readDir(dir.path);
          const subNote = sub.find((e) => e.isFile() && e.name.endsWith('.note'));
          if (subNote) return { root, path: subNote.path };
        } catch {
          /* unreadable subdir */
        }
      }
    } catch (err) {
      await logLine(`P3 root ${root}: error ${String(err)}`);
    }
  }
  return null;
}

export async function probeRasterize(): Promise<ProbeResult> {
  return timed('P3', 'native .note -> PNG', async () => {
    const found = await findFirstNote();
    if (!found) {
      return { status: 'fail', detail: `no .note files under: ${NOTE_ROOTS.join(', ')}` };
    }

    // Secondary evidence: confirm the raw file is a real .note.
    const head = base64ToAscii(await RNFS.read(found.path, 64, 0, 'base64'));
    const sig = NOTE_SIGNATURES.find((s) => head.startsWith(s));
    await logLine(`P3 ${found.path} head="${head.slice(0, 24)}" sig=${sig ?? 'none'}`);

    // Primary test: ask the device to rasterize page 0 to PNG.
    const pageCountResp = await PluginFileAPI.getNoteTotalPageNum(found.path);
    await logLine(`P3 getNoteTotalPageNum -> ${fmtResponse(pageCountResp)}`);

    const pngPath = `${RNFS.DocumentDirectoryPath}/spike-page0.png`;
    const start = Date.now();
    const genResp = await PluginFileAPI.generateNotePng({
      notePath: found.path,
      page: 0,
      times: 1,
      pngPath,
      type: 1, // white background
    });
    const ms = Date.now() - start;
    await logLine(`P3 generateNotePng -> ${fmtResponse(genResp)} in ${ms}ms`);

    const ok = await RNFS.exists(pngPath);
    const size = ok ? (await RNFS.stat(pngPath)).size : 0;
    await logLine(`P3 PNG exists=${ok} size=${size} at ${pngPath}`);

    return {
      status: ok && (isOk(genResp) || size > 0) ? 'pass' : 'fail',
      detail: ok
        ? `native rasterize OK: ${size}B PNG in ${ms}ms — decoder port NOT needed`
        : `generateNotePng produced no file: ${fmtResponse(genResp)}`,
    };
  });
}

// ---------------------------------------------------------------------------
// P4 — Write to the vault/output path (round-trip).
// ---------------------------------------------------------------------------
export async function probeWrite(vaultPath?: string): Promise<ProbeResult> {
  return timed('P4', 'write to vault path', async () => {
    const targets = [
      `${NOTE_ROOTS[0]}/SuperMD-test`,
      vaultPath ? `${vaultPath}/SuperMD-test` : null,
    ].filter((t): t is string => Boolean(t));

    const results: string[] = [];
    let anyPass = false;
    for (const dir of targets) {
      const file = `${dir}/spike-test.md`;
      try {
        await RNFS.mkdir(dir);
        await RNFS.writeFile(file, '# spike\n', 'utf8');
        const back = await RNFS.readFile(file, 'utf8');
        await RNFS.unlink(file);
        const ok = back === '# spike\n';
        anyPass = anyPass || ok;
        results.push(`${dir}: ${ok ? 'OK' : 'mismatch'}`);
      } catch (err) {
        results.push(`${dir}: ${String(err)}`);
      }
    }
    await logLine(`P4 ${results.join(' | ')}`);
    return { status: anyPass ? 'pass' : 'fail', detail: results.join(' | ') };
  });
}

// ---------------------------------------------------------------------------
// P5 — Trigger strategy. The SDK exposes only `event_pen_up` (no save hook);
//      test it, plus a polling baseline as the fallback auto-trigger.
// ---------------------------------------------------------------------------
let penUpSub: { remove: () => void } | null = null;

export function stopPenUpListener(): void {
  if (penUpSub) {
    try {
      penUpSub.remove();
    } catch {
      /* already removed */
    }
    penUpSub = null;
  }
}

export async function probeTriggers(): Promise<ProbeResult> {
  return timed('P5', 'trigger: pen_up + polling', async () => {
    // 5a: subscribe to the only documented live event.
    let penUpDetail = 'not subscribed';
    try {
      stopPenUpListener();
      let count = 0;
      const sub = PluginManager.registerEventListener('event_pen_up', 1, {
        onMsg: () => {
          count += 1;
          void logLine(`P5a event_pen_up fired (#${count})`);
        },
      });
      penUpSub = sub as unknown as { remove: () => void };
      penUpDetail =
        'subscribed to event_pen_up — write in an open note to see it fire (then "Stop pen-up")';
    } catch (err) {
      penUpDetail = `event_pen_up subscribe failed: ${String(err)}`;
    }
    await logLine(`P5a ${penUpDetail}`);

    // 5b: polling baseline — measure the cost of one mtime scan of the Note tree.
    let scanDetail = 'no note root readable';
    for (const root of NOTE_ROOTS) {
      try {
        if (!(await RNFS.exists(root))) continue;
        const start = Date.now();
        const entries = await RNFS.readDir(root);
        scanDetail = `scanned ${root}: ${entries.length} entries in ${Date.now() - start}ms`;
        break;
      } catch {
        /* try next root */
      }
    }
    await logLine(`P5b ${scanDetail}`);
    await logLine(
      'P5b NOTE: no save hook exists. Options = pen_up-debounce while a note is open, ' +
        'or foreground mtime polling. Both only run while the plugin is active.',
    );

    return {
      status: 'unknown',
      detail: `${penUpDetail}; ${scanDetail}`,
    };
  });
}

// ---------------------------------------------------------------------------
// P6 — Ephemeral local HTTP server (for onboarding). Leaves the server running
//      so you can hit it from a phone; call stopServer() from the UI to close.
// ---------------------------------------------------------------------------
let serverHandle: { close: () => void } | null = null;

export function stopServer(): void {
  if (serverHandle) {
    try {
      serverHandle.close();
    } catch {
      /* already closed */
    }
    serverHandle = null;
  }
}

export async function probeHttpServer(): Promise<ProbeResult> {
  return timed('P6', 'ephemeral HTTP server', async () => {
    stopServer();
    const port = 8088;
    const ip = (await NetworkInfo.getIPV4Address()) ?? '<unknown-ip>';

    const listening = await new Promise<boolean>((resolve) => {
      const settle = setTimeout(() => resolve(false), 5000);
      const server = TcpSocket.createServer((socket) => {
        socket.on('data', () => {
          const html =
            '<!doctype html><meta name=viewport content="width=device-width">' +
            '<h1>SuperMD onboarding server reachable</h1>';
          socket.write(
            'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n' +
              `Content-Length: ${html.length}\r\nConnection: close\r\n\r\n${html}`,
          );
          socket.end();
        });
        socket.on('error', () => undefined);
      });
      server.on('error', (e: Error) => {
        clearTimeout(settle);
        void logLine(`P6 server error: ${e.message}`);
        resolve(false);
      });
      server.listen({ port, host: '0.0.0.0' }, () => {
        clearTimeout(settle);
        serverHandle = server;
        resolve(true);
      });
    });

    const url = `http://${ip}:${port}`;
    await logLine(`P6 listening=${listening} url=${url}`);
    return {
      status: listening ? 'pass' : 'fail',
      detail: listening
        ? `serving at ${url} — open it from your phone, then tap "Stop server"`
        : 'could not bind port 8088',
    };
  });
}

// ---------------------------------------------------------------------------
// P7 — Secure, non-synced storage for the API key (round-trip).
// ---------------------------------------------------------------------------
export async function probeKeychain(): Promise<ProbeResult> {
  return timed('P7', 'secure key storage', async () => {
    const service = 'supermd.spike.apikey';
    const sentinel = `sentinel-${Date.now()}`;
    await Keychain.setGenericPassword('supermd', sentinel, { service });
    const got = await Keychain.getGenericPassword({ service });
    await Keychain.resetGenericPassword({ service });
    const ok = got !== false && got.password === sentinel;
    await logLine(`P7 keychain round-trip ok=${ok}`);
    await logLine(
      'P7 NOTE: confirm this value does NOT appear under the plugin dir from P1 ' +
        'after a device sync (the key must stay device-local).',
    );
    return {
      status: ok ? 'pass' : 'fail',
      detail: ok ? 'keychain set/get/reset OK (non-synced)' : 'keychain round-trip failed',
    };
  });
}

// ---------------------------------------------------------------------------
// P8 — (informational) Native metadata + image insert-back. Confirms we can
//      replace context.py's binary parsing and optionally write results to a note.
// ---------------------------------------------------------------------------
export async function probeMetadataAndInsert(): Promise<ProbeResult> {
  return timed('P8', 'metadata + insert-back', async () => {
    const found = await findFirstNote();
    if (!found) return { status: 'unknown', detail: 'no .note found to inspect' };

    const titles = await PluginFileAPI.getTitles(found.path, [0]).catch((e) => `err:${e}`);
    const keywords = await PluginFileAPI.getKeyWords(found.path, [0]).catch((e) => `err:${e}`);
    await logLine(`P8 getTitles -> ${fmtResponse(titles)}`);
    await logLine(`P8 getKeyWords -> ${fmtResponse(keywords)}`);

    // Confirm PluginNoteAPI.insertImage exists (don't mutate the user's note here).
    const hasInsert = typeof PluginNoteAPI.insertImage === 'function';
    await logLine(`P8 PluginNoteAPI.insertImage available=${hasInsert}`);

    return {
      status: 'unknown',
      detail:
        `native metadata reachable (titles/keywords logged); ` +
        `insertImage=${hasInsert} for optional write-back`,
    };
  });
}

/** Run every probe in order, threading optional onboarding inputs. */
export async function runAll(opts: {
  apiKey?: string;
  vaultPath?: string;
}): Promise<ProbeResult[]> {
  const results: ProbeResult[] = [];
  results.push(await probeSdkBridge());
  results.push(await probeFetch(opts.apiKey));
  results.push(await probeRasterize());
  results.push(await probeWrite(opts.vaultPath));
  results.push(await probeTriggers());
  results.push(await probeHttpServer());
  results.push(await probeKeychain());
  results.push(await probeMetadataAndInsert());
  return results;
}
