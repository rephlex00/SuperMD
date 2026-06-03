/**
 * Logging for the spike: every line is mirrored to (1) an in-memory buffer the
 * UI subscribes to, and (2) a durable log file on device storage. The file is
 * the artifact you read back over USB/sync after running on hardware — it is the
 * actual deliverable of the spike.
 */
import RNFS from 'react-native-fs';

/** Where the durable log is written. DocumentDirectoryPath is always writable. */
export const LOG_PATH = `${RNFS.DocumentDirectoryPath}/supermd-spike.log`;

export type ProbeStatus = 'pass' | 'fail' | 'unknown';

export interface ProbeResult {
  id: string;
  title: string;
  status: ProbeStatus;
  detail: string;
  durationMs: number;
}

type Listener = (lines: string[]) => void;

const buffer: string[] = [];
const listeners = new Set<Listener>();

function notify(): void {
  const snapshot = [...buffer];
  for (const l of listeners) {
    l(snapshot);
  }
}

/** Subscribe the UI to log updates. Returns an unsubscribe function. */
export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  listener([...buffer]);
  return () => {
    listeners.delete(listener);
  };
}

/** Append a line to the on-screen buffer and the durable log file. */
export async function logLine(line: string): Promise<void> {
  const stamped = `[${new Date().toISOString()}] ${line}`;
  buffer.push(stamped);
  notify();
  try {
    await RNFS.appendFile(LOG_PATH, stamped + '\n', 'utf8');
  } catch {
    // If the log file isn't writable we still keep the on-screen buffer; the
    // failure itself is informative (it means even DocumentDirectory is locked).
    buffer.push('[warn] could not append to log file at ' + LOG_PATH);
    notify();
  }
}

/** Format and log a finished probe result. */
export async function logResult(result: ProbeResult): Promise<void> {
  const badge =
    result.status === 'pass' ? 'PASS' : result.status === 'fail' ? 'FAIL' : '????';
  await logLine(
    `[${badge}] ${result.id} ${result.title} (${result.durationMs}ms) — ${result.detail}`,
  );
}

/** Truncate the log file at the start of a run so each run is self-contained. */
export async function resetLog(): Promise<void> {
  buffer.length = 0;
  notify();
  try {
    await RNFS.writeFile(LOG_PATH, '', 'utf8');
  } catch {
    // ignore — logLine will report write failures
  }
}
