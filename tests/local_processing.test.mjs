// Unit tests for the on-device processing layer (static/local/).
//
// Run with `node --test public/tests/local_processing.test.mjs`, or via
// scripts/test.sh, which runs it alongside the two pytest suites.
//
// The three source files are plain browser IIFEs with no module system, so they
// are evaluated inside a `vm` context holding just enough of a DOM for them to
// install themselves. That covers everything except the parts that genuinely
// need a renderer — canvas pixels and pdf-lib's PDF writer — which is why the
// assertions below target the dispatch contract and the pure logic ported from
// Python (page-range parsing, output naming, numeral formatting). Those are
// where a divergence from the server would be silent; a mis-drawn watermark is
// not.
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const STATIC = join(dirname(fileURLToPath(import.meta.url)), '..', 'static', 'local');

/** Build a fresh sandbox with the three scripts loaded into it. */
function load() {
    let blobUrls = 0;
    const revoked = [];

    const URLShim = function (...args) { return new URL(...args); };
    URLShim.createObjectURL = () => `blob:mock/${++blobUrls}`;
    URLShim.revokeObjectURL = (u) => { revoked.push(u); };

    const canvasStub = () => ({
        width: 0,
        height: 0,
        toBlob() { throw new Error('canvas rendering is not exercised in these tests'); },
        getContext: () => null,
    });

    const fetchCalls = [];

    const sandbox = {
        console,
        Promise, Blob, FormData, Response, Error, Object, Math, Number, String,
        Array, JSON, Date, RegExp, isFinite, parseInt, WeakMap, FileReader: class { },
        Image: class { },
        URL: URLShim,
        setTimeout,
        document: {
            // Left undefined so ff-local.js takes its documented fallback path
            // for the vendor URL rather than resolving against a script src.
            currentScript: null,
            head: { appendChild() { } },
            createElement(tag) {
                return tag === 'canvas' ? canvasStub() : { set src(_v) { }, onload: null, onerror: null };
            },
        },
        fetch(url, init) {
            fetchCalls.push({ url, init });
            return Promise.resolve(new Response('{"server":true}', {
                status: 200, headers: { 'Content-Type': 'application/json' },
            }));
        },
    };
    sandbox.window = sandbox;
    sandbox.window.apiUrl = (p) => `https://api.test${p}`;

    vm.createContext(sandbox);
    for (const file of ['ff-local.js', 'ops-image.js', 'ops-pdf.js']) {
        vm.runInContext(readFileSync(join(STATIC, file), 'utf8'), sandbox, { filename: file });
    }

    return { sandbox, L: sandbox.window.ffLocal, fetchCalls, revoked };
}

// Arrays built inside the vm have that context's Array.prototype, which
// deepStrictEqual treats as a mismatch however identical the contents. Copying
// into this realm compares the values, which is what these tests are about.
const here = (xs) => Array.from(xs);

// ── Registration ──────────────────────────────────────────────────────────

test('every ported endpoint registers a handler', () => {
    const { L } = load();
    const expected = [
        '/api/image/resize', '/api/image/crop', '/api/image/rotate',
        '/api/image/compress', '/api/image/convert', '/api/image/watermark',
        '/api/image/to-pdf',
        '/api/pdf/merge', '/api/pdf/extract-pages', '/api/pdf/rotate',
        '/api/pdf/organize', '/api/pdf/add-page-numbers', '/api/pdf/watermark',
        '/api/pdf/create-blank', '/api/pdf/create-from-text',
    ];
    for (const path of expected) {
        assert.equal(typeof L.handlers[path], 'function', `${path} has no handler`);
    }
});

test('operations that need the server are deliberately not registered', () => {
    const { L } = load();
    // Moving any of these on-device would either lose fidelity (LibreOffice) or
    // move a metered/AI path off the server; see ops-pdf.js's header.
    for (const path of [
        '/api/pdf/convert-to-word', '/api/pdf/compress', '/api/pdf/repair',
        '/api/pdf/to-excel', '/api/pdf/to-pptx', '/api/word/to-pdf',
        '/api/excel/to-pdf', '/api/ppt/to-pdf', '/api/image/heic-to-jpeg',
        '/api/workflow/execute',
    ]) {
        assert.equal(L.handlers[path], undefined, `${path} should stay on the server`);
    }
});

// ── Output naming (scripts/utils.py::branded_filename) ────────────────────

test('brandedName matches branded_filename()', () => {
    const { L } = load();
    assert.equal(L.brandedName('resume.pdf', 'pdf'), 'resume_forgefiles.org.pdf');
    assert.equal(L.brandedName('photo.HEIC', 'jpg'), 'photo_forgefiles.org.jpg');
    assert.equal(L.brandedName('no-extension', 'pdf'), 'no-extension_forgefiles.org.pdf');
    assert.equal(L.brandedName('a.b.c.png', 'webp'), 'a.b.c_forgefiles.org.webp');
    assert.equal(L.brandedName('x.pdf', '.pdf'), 'x_forgefiles.org.pdf');
});

test('brandedName is idempotent, so chained tools do not stack the suffix', () => {
    const { L } = load();
    // The Python version strips _forgefiles.org before re-adding it, because a
    // result is commonly fed straight back into another tool.
    assert.equal(L.brandedName('resume_forgefiles.org.pdf', 'pdf'), 'resume_forgefiles.org.pdf');
    assert.equal(L.brandedName('resume_FORGEFILES.ORG.pdf', 'pdf'), 'resume_forgefiles.org.pdf');
    const once = L.brandedName('doc.pdf', 'pdf');
    assert.equal(L.brandedName(once, 'pdf'), once);
});

test('hexId produces the short ids the server filenames use', () => {
    const { L } = load();
    assert.match(L.hexId(8), /^[0-9a-f]{8}$/);
    assert.match(L.hexId(6), /^[0-9a-f]{6}$/);
});

// ── Page selection (pdf_utils.py::_parse_page_selection) ──────────────────

test('parsePageSelection handles ranges, order and duplicates', () => {
    const { L } = load();
    const parse = L.pdf.parsePageSelection;
    assert.deepEqual(here(parse('all', 3)), [0, 1, 2]);
    assert.deepEqual(here(parse('1,3-5', 5)), [0, 2, 3, 4]);
    assert.deepEqual(here(parse(' 2 , 1 ', 3)), [1, 0], 'input order is preserved');
    assert.deepEqual(here(parse('1,1,2', 3)), [0, 1], 'repeats collapse');
    assert.deepEqual(here(parse('2-2', 3)), [1]);
    assert.deepEqual(here(parse('ALL', 2)), [0, 1]);
});

test('parsePageSelection rejects bad input with the server error strings', () => {
    const { L } = load();
    const parse = L.pdf.parsePageSelection;
    const rejects = (input, total, message) => assert.throws(
        () => parse(input, total),
        (e) => e.name === 'FFLocalError' && e.message === message,
        `${JSON.stringify(input)} should be rejected`,
    );

    rejects(null, 3, "No pages selected. Please provide page numbers or 'all'.");
    rejects('   ', 3, "No pages selected. Please provide page numbers or 'all'.");
    rejects('5-3', 9, "Invalid page range segment: '5-3'");
    rejects('0-2', 9, "Invalid page range segment: '0-2'");
    rejects('1-', 9, "Invalid page range segment: '1-'");
    rejects('a-b', 9, "Invalid page range numbers: 'a-b'");
    rejects('abc', 9, "Invalid page number: 'abc'");
    rejects('0', 9, "Invalid page number: '0'");
    rejects(',', 9, 'No valid pages selected.');
    rejects('4', 3, 'Selected page number exceeds document page count (3).');
    rejects('1-9', 3, 'Selected page number exceeds document page count (3).');
});

test('parsePageSelection rejects float-looking input rather than truncating', () => {
    const { L } = load();
    // int('1.5') raises in Python too — matching it keeps a typo an error on
    // both paths instead of silently selecting page 1.
    assert.throws(() => L.pdf.parsePageSelection('1.5', 9), (e) => e.name === 'FFLocalError');
});

// ── Page numbering (pdf_utils.py::add_page_numbers) ───────────────────────

test('toRoman matches the server numeral table', () => {
    const { L } = load();
    const cases = [[1, 'I'], [4, 'IV'], [9, 'IX'], [14, 'XIV'], [40, 'XL'],
    [90, 'XC'], [400, 'CD'], [1990, 'MCMXC'], [2024, 'MMXXIV']];
    for (const [n, expected] of cases) assert.equal(L.pdf.toRoman(n), expected, `toRoman(${n})`);
});

test('pageLabel formats decimal, roman and alpha', () => {
    const { L } = load();
    assert.equal(L.pdf.pageLabel('decimal', 7), '7');
    assert.equal(L.pdf.pageLabel('roman', 7), 'VII');
    assert.equal(L.pdf.pageLabel('alpha', 1), 'A');
    assert.equal(L.pdf.pageLabel('alpha', 26), 'Z');
    // Past Z the server gives up and prints the number.
    assert.equal(L.pdf.pageLabel('alpha', 27), '27');
});

// ── Created-PDF naming (pdf_utils.py::create_pdf_from_text) ───────────────

test('safeTitle matches the server filename rule', () => {
    const { L } = load();
    assert.equal(L.pdf.safeTitle('My Report'), 'My_Report');
    assert.equal(L.pdf.safeTitle('in/valid:name*?'), 'invalidname');
    assert.equal(L.pdf.safeTitle('keep-these_1 2'), 'keep-these_1_2');
    assert.equal(L.pdf.safeTitle(''), 'document');
    assert.equal(L.pdf.safeTitle('!!!'), 'document');
    assert.equal(L.pdf.safeTitle('x'.repeat(80)), 'x'.repeat(50));
});

// ── Page geometry ─────────────────────────────────────────────────────────

test('pageSize reproduces reportlab’s dimensions', () => {
    const { L } = load();
    const [aw, ah] = L.pdf.pageSize('A4');
    assert.ok(Math.abs(aw - 595.2755905511812) < 1e-9, `A4 width was ${aw}`);
    assert.ok(Math.abs(ah - 841.8897637795277) < 1e-9, `A4 height was ${ah}`);
    assert.deepEqual(here(L.pdf.pageSize('Letter')), [612.0, 792.0]);
    assert.deepEqual(here(L.pdf.pageSize('letter')), [612.0, 792.0]);
    // Unknown names fall back to A4, as page_sizes.get(..., A4) does.
    assert.deepEqual(here(L.pdf.pageSize('tabloid')), here(L.pdf.pageSize('A4')));
    assert.deepEqual(here(L.pdf.pageSize(undefined)), here(L.pdf.pageSize('A4')));
});

// ── Image format selection (image_utils.py::_FORMAT_EXT) ──────────────────

test('formatOf picks the output format from the input suffix', () => {
    const { L } = load();
    assert.equal(L.image.formatOf('a.jpg'), 'jpg');
    assert.equal(L.image.formatOf('a.JPEG'), 'jpg');
    assert.equal(L.image.formatOf('a.png'), 'png');
    assert.equal(L.image.formatOf('a.webp'), 'webp');
    // Anything Pillow would not round-trip becomes jpg.
    assert.equal(L.image.formatOf('a.bmp'), 'jpg');
    assert.equal(L.image.formatOf('a.tiff'), 'jpg');
    assert.equal(L.image.formatOf('noext'), 'jpg');
});

// ── FormData coercion ─────────────────────────────────────────────────────

test('form helpers coerce and default like FastAPI Form() declarations', () => {
    const { L } = load();
    const fd = new FormData();
    fd.append('quality', '70');
    fd.append('opacity', '0.35');
    fd.append('blank', '');

    assert.equal(L.int(fd, 'quality', 95), 70);
    assert.equal(L.num(fd, 'opacity', 0.4), 0.35);
    assert.equal(L.str(fd, 'missing', 'bottom-right'), 'bottom-right');
    assert.equal(L.int(fd, 'missing', 12), 12);
    assert.equal(L.int(fd, 'blank', 12), 12, 'an empty field takes the default');
    assert.equal(L.int(fd, 'missing', null), null, 'a null default survives');

    // A non-numeric value is the user's error, so it must not silently become
    // NaN and produce a garbage result.
    fd.append('angle', 'sideways');
    assert.throws(() => L.num(fd, 'angle', 90),
        (e) => e.name === 'FFLocalError' && e.message === 'angle must be a number.');
    assert.throws(() => L.int(fd, 'angle', 90),
        (e) => e.name === 'FFLocalError' && e.message === 'angle must be an integer.');
});

test('range() reproduces validate_range()', () => {
    const { L } = load();
    assert.equal(L.range('width', 100, 1), 100);
    assert.equal(L.range('width', null, 1), null, 'null skips validation');
    assert.throws(() => L.range('percentage', 600, 1, 500),
        (e) => e.name === 'FFLocalError' && e.message === 'percentage must be <= 500.');
    assert.throws(() => L.range('width', 0, 1),
        (e) => e.name === 'FFLocalError' && e.message === 'width must be >= 1.');
});

// ── Dispatch contract ─────────────────────────────────────────────────────

test('a successful handler returns a server-shaped JSON response', async () => {
    const { sandbox, L, fetchCalls } = load();
    L.register('/api/test/ok', async () => ({
        blob: new Blob(['hello'], { type: 'application/pdf' }),
        filename: 'out_forgefiles.org.pdf',
        message: 'Pages extracted',
    }));

    const res = await sandbox.window.ffProcess('/api/test/ok', new FormData());
    assert.equal(res.ok, true);
    const body = await res.json();
    assert.equal(body.status, 'success');
    assert.equal(body.message, 'Pages extracted');
    assert.equal(body.filename, 'out_forgefiles.org.pdf');
    assert.equal(body.local, true);
    assert.ok(body.download_token, 'a download_token is always returned');
    assert.equal(fetchCalls.length, 0, 'nothing was uploaded');
});

test('extra fields ride along without displacing the download fields', async () => {
    const { sandbox, L } = load();
    L.register('/api/test/extra', async () => ({
        blob: new Blob(['x']),
        filename: 'a_forgefiles.org.jpg',
        message: 'Image compressed',
        extra: { original_size: 100, compressed_size: 40, reduction_pct: 60 },
    }));

    const body = await (await sandbox.window.ffProcess('/api/test/extra', new FormData())).json();
    assert.equal(body.reduction_pct, 60);
    assert.equal(body.original_size, 100);
    assert.equal(body.filename, 'a_forgefiles.org.jpg');
});

test('a validation error is reported to the user, not retried on the server', async () => {
    const { sandbox, L, fetchCalls } = load();
    L.register('/api/test/bad', async () => { throw new L.Error('Content cannot be empty.'); });

    const res = await sandbox.window.ffProcess('/api/test/bad', new FormData());
    assert.equal(res.status, 400);
    assert.equal((await res.json()).detail, 'Content cannot be empty.');
    // Uploading would only earn the same rejection.
    assert.equal(fetchCalls.length, 0);
});

test('an unsupported input falls back to the server', async () => {
    const { sandbox, L, fetchCalls } = load();
    L.register('/api/test/enc', async () => { throw new L.Unsupported('PDF is encrypted'); });

    const res = await sandbox.window.ffProcess('/api/test/enc', new FormData());
    assert.equal(res.ok, true);
    assert.deepEqual(await res.json(), { server: true });
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, 'https://api.test/api/test/enc');
    assert.equal(fetchCalls[0].init.method, 'POST');
});

test('an unexpected bug falls back to the server instead of failing the tool', async () => {
    const { sandbox, L, fetchCalls } = load();
    L.register('/api/test/boom', async () => { throw new TypeError('undefined is not a function'); });

    const res = await sandbox.window.ffProcess('/api/test/boom', new FormData());
    assert.equal(res.ok, true, 'the user still gets a result');
    assert.equal(fetchCalls.length, 1);
});

test('an unregistered path goes straight to the server', async () => {
    const { sandbox, fetchCalls } = load();
    const res = await sandbox.window.ffProcess('/api/word/to-pdf', new FormData());
    assert.equal(res.ok, true);
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, 'https://api.test/api/word/to-pdf');
});

test('the kill switches route everything back to the server', async () => {
    const { sandbox, L, fetchCalls } = load();
    L.register('/api/test/ok', async () => ({
        blob: new Blob(['x']), filename: 'f.pdf', message: 'done',
    }));

    sandbox.window.FF_LOCAL = false;
    await sandbox.window.ffProcess('/api/test/ok', new FormData());
    assert.equal(fetchCalls.length, 1, 'window.FF_LOCAL = false disables local processing');

    sandbox.window.FF_LOCAL = undefined;
    await sandbox.window.ffProcess('/api/test/ok', new FormData());
    assert.equal(fetchCalls.length, 1, 'and clearing it re-enables them');
});

// ── Result registry ───────────────────────────────────────────────────────

test('local tokens resolve to their blob and are distinguishable from server ones', async () => {
    const { sandbox, L } = load();
    L.register('/api/test/ok', async () => ({
        blob: new Blob(['hello'], { type: 'application/pdf' }),
        filename: 'out_forgefiles.org.pdf',
        message: 'ok',
    }));

    const body = await (await sandbox.window.ffProcess('/api/test/ok', new FormData())).json();
    const token = body.download_token;

    assert.equal(L.isLocalToken(token), true);
    assert.equal(L.isLocalToken('9f8e7d6c'), false, 'a server token is not mistaken for a local one');
    assert.equal(L.resolve('9f8e7d6c'), null, 'server tokens resolve to null so the caller uses /api/download');

    const entry = L.resolve(token);
    assert.equal(entry.filename, 'out_forgefiles.org.pdf');
    assert.equal(await entry.blob.text(), 'hello');
    assert.match(entry.url, /^blob:mock\//);
    assert.equal(L.resolve(token).url, entry.url, 'the object URL is minted once and reused');
});

test('releasing a result revokes its object URL and drops the blob', async () => {
    const { sandbox, L, revoked } = load();
    L.register('/api/test/ok', async () => ({
        blob: new Blob(['x']), filename: 'f.pdf', message: 'ok',
    }));

    const body = await (await sandbox.window.ffProcess('/api/test/ok', new FormData())).json();
    const url = L.resolve(body.download_token).url;

    L.release(body.download_token);
    assert.deepEqual(revoked, [url], 'the object URL is revoked, not leaked');
    assert.equal(L.resolve(body.download_token), null);
    // Releasing twice must not throw — updateDownloadLink() can be called with
    // the same anchor repeatedly.
    L.release(body.download_token);
});

test('each result gets its own token', async () => {
    const { sandbox, L } = load();
    L.register('/api/test/ok', async () => ({
        blob: new Blob(['x']), filename: 'f.pdf', message: 'ok',
    }));

    const first = await (await sandbox.window.ffProcess('/api/test/ok', new FormData())).json();
    const second = await (await sandbox.window.ffProcess('/api/test/ok', new FormData())).json();
    assert.notEqual(first.download_token, second.download_token);
});
