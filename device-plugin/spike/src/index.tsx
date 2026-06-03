/**
 * SuperMD Spike — a single screen that runs the capability probes and shows the
 * results. Designed for e-ink: high-contrast, no animation, large touch targets.
 *
 * Optional inputs (API key, vault path) are entered here for now. The real
 * plugin will collect these via the ephemeral onboarding web server (Phase 3).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { LOG_PATH, ProbeResult, resetLog, logResult, subscribe } from './log';
import {
  probeSdkBridge,
  probeFetch,
  probeRasterize,
  probeWrite,
  probeTriggers,
  probeHttpServer,
  probeKeychain,
  probeMetadataAndInsert,
  stopServer,
  stopPenUpListener,
  runAll,
} from './probes';

interface NamedProbe {
  id: string;
  title: string;
  run: (opts: { apiKey?: string; vaultPath?: string }) => Promise<ProbeResult>;
}

const PROBES: NamedProbe[] = [
  { id: 'P1', title: 'sn-plugin-lib bridge', run: () => probeSdkBridge() },
  { id: 'P2', title: 'outbound fetch', run: (o) => probeFetch(o.apiKey) },
  { id: 'P3', title: 'native .note→PNG', run: () => probeRasterize() },
  { id: 'P4', title: 'write to vault', run: (o) => probeWrite(o.vaultPath) },
  { id: 'P5', title: 'pen_up + polling', run: () => probeTriggers() },
  { id: 'P6', title: 'http server', run: () => probeHttpServer() },
  { id: 'P7', title: 'secure key storage', run: () => probeKeychain() },
  { id: 'P8', title: 'metadata + insert', run: () => probeMetadataAndInsert() },
];

function badge(status: ProbeResult['status']): string {
  return status === 'pass' ? '✓' : status === 'fail' ? '✗' : '?';
}

export default function App(): React.JSX.Element {
  const [lines, setLines] = useState<string[]>([]);
  const [results, setResults] = useState<Record<string, ProbeResult>>({});
  const [apiKey, setApiKey] = useState('');
  const [vaultPath, setVaultPath] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => subscribe(setLines), []);

  const record = useCallback(async (r: ProbeResult) => {
    await logResult(r);
    setResults((prev) => ({ ...prev, [r.id]: r }));
  }, []);

  const onRunOne = useCallback(
    async (probe: NamedProbe) => {
      setBusy(true);
      try {
        await record(await probe.run({ apiKey: apiKey || undefined, vaultPath: vaultPath || undefined }));
      } finally {
        setBusy(false);
      }
    },
    [apiKey, vaultPath, record],
  );

  const onRunAll = useCallback(async () => {
    setBusy(true);
    try {
      await resetLog();
      const all = await runAll({ apiKey: apiKey || undefined, vaultPath: vaultPath || undefined });
      for (const r of all) await record(r);
    } finally {
      setBusy(false);
    }
  }, [apiKey, vaultPath, record]);

  return (
    <SafeAreaView style={styles.root}>
      <Text style={styles.h1}>SuperMD Capability Spike</Text>
      <Text style={styles.sub}>Log file: {LOG_PATH}</Text>

      <View style={styles.inputs}>
        <TextInput
          style={styles.input}
          placeholder="LLM API key (optional, for P2)"
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          value={apiKey}
          onChangeText={setApiKey}
        />
        <TextInput
          style={styles.input}
          placeholder="Vault/output path (optional, for P4)"
          autoCapitalize="none"
          autoCorrect={false}
          value={vaultPath}
          onChangeText={setVaultPath}
        />
      </View>

      <View style={styles.row}>
        <TouchableOpacity
          style={[styles.btn, styles.primary]}
          disabled={busy}
          onPress={onRunAll}
        >
          <Text style={[styles.btnText, styles.btnTextPrimary]}>
            {busy ? 'Running…' : 'Run all probes'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.btn} onPress={stopServer}>
          <Text style={styles.btnText}>Stop server</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.btn} onPress={stopPenUpListener}>
          <Text style={styles.btnText}>Stop pen-up</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.probes}>
        {PROBES.map((p) => {
          const r = results[p.id];
          return (
            <TouchableOpacity
              key={p.id}
              style={styles.probe}
              disabled={busy}
              onPress={() => onRunOne(p)}
            >
              <Text style={styles.probeBadge}>{r ? badge(r.status) : '·'}</Text>
              <Text style={styles.probeTitle}>
                {p.id} {p.title}
              </Text>
              <Text style={styles.probeDetail} numberOfLines={2}>
                {r ? r.detail : 'tap to run'}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={styles.h2}>Log</Text>
      <ScrollView style={styles.log}>
        {lines.map((l, i) => (
          <Text key={i} style={styles.logLine}>
            {l}
          </Text>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#ffffff', padding: 12 },
  h1: { fontSize: 20, fontWeight: 'bold', color: '#000' },
  h2: { fontSize: 16, fontWeight: 'bold', color: '#000', marginTop: 8 },
  sub: { fontSize: 11, color: '#444', marginBottom: 8 },
  inputs: { marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: '#000',
    paddingHorizontal: 8,
    paddingVertical: 6,
    marginBottom: 6,
    color: '#000',
  },
  row: { flexDirection: 'row', marginBottom: 8 },
  btn: {
    borderWidth: 1,
    borderColor: '#000',
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginRight: 8,
  },
  primary: { backgroundColor: '#000' },
  btnText: { color: '#000', fontWeight: 'bold' },
  btnTextPrimary: { color: '#fff' },
  probes: { marginBottom: 8 },
  probe: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#ccc',
    paddingVertical: 8,
  },
  probeBadge: { width: 24, fontSize: 18, fontWeight: 'bold', color: '#000' },
  probeTitle: { width: 150, fontSize: 13, color: '#000' },
  probeDetail: { flex: 1, fontSize: 11, color: '#333' },
  log: { flex: 1, borderWidth: 1, borderColor: '#000', padding: 6 },
  logLine: { fontSize: 10, color: '#000', fontFamily: 'monospace' },
});
