/**
 * Supernote Cloud client — TS port of the sncloud fork (rnbennett/sncloud) used by
 * docker/stack/supernote-sync/sync.py. Uses Obsidian requestUrl (mobile-safe).
 *
 * Login hash: sha256(md5(password) + randomCode), per the public Supernote Cloud API.
 * The E1760 new-device OTP flow mirrors sync.py: login → E1760 → sendVerificationCode
 * → verifyOtp → token.
 *
 * VERIFY: the exact OTP/CSRF endpoints differ across firmware; confirm the
 * sendVerificationCode/verifyOtp paths against the sncloud fork before relying on
 * the new-device flow. login/ls/download follow the long-standing public API.
 */
import { requestUrl } from 'obsidian';
import { md5Hex } from '../util/md5';
import { sha256Hex } from '../util/hash';

const BASE = 'https://cloud.supernote.com/api';

export interface CloudFile {
  id: string;
  name: string;
  isFolder: boolean;
  size: number;
  updateTime: number;
}

export class CloudError extends Error {
  constructor(message: string, public code?: string) {
    super(message);
  }
}

async function post(path: string, body: unknown, token?: string): Promise<Record<string, unknown>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['x-access-token'] = token;
  const res = await requestUrl({
    url: BASE + path,
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    throw: false,
  });
  if (res.status >= 400) {
    throw new CloudError(`Supernote Cloud HTTP ${res.status}: ${(res.text || '').slice(0, 200)}`);
  }
  return (res.json ?? {}) as Record<string, unknown>;
}

export class SNClient {
  token: string | null;

  constructor(token?: string) {
    this.token = token ?? null;
  }

  async login(email: string, password: string): Promise<string> {
    const rnd = await post('/official/user/query/random', { countryCode: '1', account: email });
    const randomCode = rnd['randomCode'] as string | undefined;
    const timestamp = String(rnd['timestamp'] ?? '');
    if (!randomCode) throw new CloudError('Could not obtain login random code (check the account/email).');

    const hashed = await sha256Hex(md5Hex(password) + randomCode);
    const resp = await post('/official/user/account/login/new', {
      countryCode: '1',
      account: email,
      password: hashed,
      browser: 'Chrome',
      equipment: '1',
      loginMethod: '1',
      timestamp,
      language: 'en',
    });

    const errorCode = String(resp['errorCode'] ?? resp['code'] ?? '');
    if (errorCode === 'E1760' || /E1760/.test(String(resp['error'] ?? ''))) {
      throw new CloudError(`__E1760__:${timestamp}`, 'E1760');
    }
    const token = resp['token'] as string | undefined;
    if (!token) {
      throw new CloudError(String(resp['errorMsg'] ?? resp['msg'] ?? 'Supernote Cloud login failed.'));
    }
    this.token = token;
    return token;
  }

  async sendVerificationCode(email: string, timestamp: string): Promise<string> {
    const resp = await post('/official/user/account/sendCode', {
      countryCode: '1',
      account: email,
      timestamp,
    });
    return String(resp['validCodeKey'] ?? '');
  }

  async verifyOtp(email: string, code: string, validCodeKey: string, timestamp: string): Promise<string> {
    const resp = await post('/official/user/account/verifyCode', {
      countryCode: '1',
      account: email,
      code,
      validCodeKey,
      timestamp,
    });
    const token = resp['token'] as string | undefined;
    if (!token) throw new CloudError(String(resp['errorMsg'] ?? 'OTP verification failed.'));
    this.token = token;
    return token;
  }

  async ls(directoryId = '0'): Promise<CloudFile[]> {
    if (!this.token) throw new CloudError('Not authenticated.', 'NO_TOKEN');
    const resp = await post(
      '/official/user/file/list/query',
      { directoryId, pageNo: 1, pageSize: 1000, order: 'time', sequence: 'desc' },
      this.token,
    );
    const list = (resp['userFileVOList'] as Array<Record<string, unknown>>) ?? [];
    return list.map((f) => ({
      id: String(f['id']),
      name: String(f['fileName']),
      isFolder: f['isFolder'] === 'Y',
      size: Number(f['size'] ?? 0),
      updateTime: Number(f['updateTime'] ?? 0),
    }));
  }

  /** Resolve a '/Note/Sub' path to its directory contents. */
  async lsPath(path: string): Promise<CloudFile[]> {
    const parts = path.split('/').filter(Boolean);
    let dirId = '0';
    for (const part of parts) {
      const items = await this.ls(dirId);
      const match = items.find((i) => i.isFolder && i.name === part);
      if (!match) return [];
      dirId = match.id;
    }
    return this.ls(dirId);
  }

  async download(id: string): Promise<Uint8Array> {
    if (!this.token) throw new CloudError('Not authenticated.', 'NO_TOKEN');
    const meta = await post('/official/user/file/download/url', { id, type: 0 }, this.token);
    const url = meta['url'] as string | undefined;
    if (!url) throw new CloudError('No download URL returned.');
    const res = await requestUrl({ url, method: 'GET', throw: false });
    if (res.status >= 400) throw new CloudError(`Download HTTP ${res.status}`);
    return new Uint8Array(res.arrayBuffer);
  }
}
