import {mkdtemp, mkdir, writeFile, cp, readdir, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

const SOURCE_URL = 'https://codeload.github.com/PedroFlores199/AutoPeritaje/tar.gz/c8f019a7a55ae271ab4c7ce5e466149e61ca06b4';
const SOURCE_SHA256 = '9c183cae74cb5a68c2cbad18495f7ea1125208b543c3727a6813d3b6b9e242f7';
const response = await fetch(SOURCE_URL);
if (!response.ok) throw new Error('Source download failed: HTTP ' + response.status);
const bytes = new Uint8Array(await response.arrayBuffer());
if (createHash('sha256').update(bytes).digest('hex') !== SOURCE_SHA256) throw new Error('Source checksum mismatch');
const folder = await mkdtemp(path.join(tmpdir(), 'autoperitaje-'));
const archive = path.join(folder, 'source.tar.gz');
const source = path.join(folder, 'source');
await mkdir(source);
await writeFile(archive, bytes);
execFileSync('tar', ['-xzf', archive, '-C', source, '--strip-components=1']);
await cp(path.join(source, 'web-demo'), 'dist', {recursive:true});
execFileSync(process.execPath, [path.resolve('dist/prepare.mjs')], {stdio:'inherit'});
const output = path.resolve('static');
await mkdir(output, {recursive:true});
for (const entry of await readdir('dist', {withFileTypes:true})) {
  if (entry.isFile() && !['README.md', 'prepare.mjs'].includes(entry.name)) await cp(path.join('dist', entry.name), path.join(output, entry.name));
}
for (const directory of ['models', 'vendor']) {
  for (const entry of await readdir(path.join('dist', directory))) {
    const filename = entry === 'manifest.json' ? 'vendor-manifest.json' : entry;
    await cp(path.join('dist', directory, entry), path.join(output, filename));
  }
}
const index = path.join(output, 'index.html');
await writeFile(index, (await readFile(index, 'utf8')).replaceAll('./vendor/', './'));
const inference = path.join(output, 'inference.mjs');
await writeFile(inference, (await readFile(inference, 'utf8')).replaceAll('./vendor/', './').replaceAll('./models/', './'));
await cp('README.md', path.join(output, 'README.md'));
console.log('Static files prepared locally with verified source and models. Upload static/ contents; no paid build is required.');
