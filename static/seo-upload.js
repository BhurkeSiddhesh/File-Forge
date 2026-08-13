// Upload box for the server-rendered SEO landing pages.
//
// Why this exists: a visitor who searched "pdf to word" and landed on
// /pdf-to-word used to find a text CTA linking to the app. Doing anything at
// all cost them a click plus a full page load *before* the first upload box
// appeared, and the measured result was that ~89% of landing sessions never
// opened a tool at all. The first thing you can do on a file-conversion page
// should be to give it a file.
//
// The file is handed to the app through IndexedDB rather than a query
// parameter — a File can't survive a navigation any other way, and re-asking
// for it on the far side would rebuild the exact friction this removes.
// IndexedDB (not sessionStorage) because these are documents, routinely tens
// of megabytes, and it stores a Blob natively without base64 inflating it by a
// third.
//
// Every failure path falls back to the old behaviour — navigate to the app and
// let the visitor pick the file there. A handoff that half-works would be
// worse than the link it replaces.
(function () {
    'use strict';

    var DB_NAME = 'ff_handoff';
    var STORE = 'files';
    var KEY = 'pending';

    function openDb() {
        return new Promise(function (resolve, reject) {
            if (!window.indexedDB) return reject(new Error('no indexedDB'));
            var req = indexedDB.open(DB_NAME, 1);
            req.onupgradeneeded = function () {
                if (!req.result.objectStoreNames.contains(STORE)) {
                    req.result.createObjectStore(STORE);
                }
            };
            req.onsuccess = function () { resolve(req.result); };
            req.onerror = function () { reject(req.error); };
        });
    }

    function stash(file) {
        return openDb().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(STORE, 'readwrite');
                // Stored as a plain object, not the File itself: structured
                // clone keeps File in every browser that matters, but the name
                // is the part we cannot afford to lose (the app derives the
                // output filename from it) so it is carried explicitly.
                tx.objectStore(STORE).put(
                    { blob: file, name: file.name, type: file.type, at: Date.now() },
                    KEY
                );
                tx.oncomplete = function () { db.close(); resolve(); };
                tx.onerror = function () { db.close(); reject(tx.error); };
            });
        });
    }

    var zone = document.querySelector('[data-ff-upload]');
    if (!zone) return;

    var input = zone.querySelector('input[type=file]');
    var target = zone.getAttribute('data-ff-target') || '/';
    if (!input) return;

    function go(withHandoff) {
        window.location.href = withHandoff
            ? target + (target.indexOf('?') === -1 ? '?' : '&') + 'handoff=1'
            : target;
    }

    function accept(file) {
        if (!file) return;
        zone.classList.add('is-busy');
        // Never let a storage failure strand the visitor on this page: on any
        // error, go to the app anyway and let them pick the file there.
        stash(file).then(function () { go(true); }, function () { go(false); });
    }

    input.addEventListener('change', function () {
        accept(input.files && input.files[0]);
    });

    // Drag and drop over the whole box. Files arrive on a conversion page by
    // being dragged onto it at least as often as by a file picker.
    ['dragenter', 'dragover'].forEach(function (evt) {
        zone.addEventListener(evt, function (e) {
            e.preventDefault();
            zone.classList.add('is-dragover');
        });
    });
    ['dragleave', 'drop'].forEach(function (evt) {
        zone.addEventListener(evt, function (e) {
            e.preventDefault();
            if (evt === 'dragleave' && zone.contains(e.relatedTarget)) return;
            zone.classList.remove('is-dragover');
        });
    });
    zone.addEventListener('drop', function (e) {
        accept(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]);
    });
})();
