// On-device image operations — the canvas equivalents of scripts/image_utils.py.
//
// Every handler here mirrors its Python counterpart's output filename, message
// string and validation errors so a local result is indistinguishable from a
// server one. Where behaviour deliberately differs it is called out inline.
//
// Not ported: heic-to-jpeg. Only Safari can decode HEIC in a canvas; everywhere
// else `pillow_heif` on the server is the only thing that can read the file.
(function () {
    'use strict';

    var L = window.ffLocal;
    if (!L) return;

    // ── Decoding ──────────────────────────────────────────────────────────

    // Pillow calls ImageOps.exif_transpose() on every input, baking the EXIF
    // orientation into the pixels. The browser equivalent is simply to decode
    // through an <img>: `image-orientation: from-image` is the CSS initial
    // value, so naturalWidth/naturalHeight and drawImage() are all already
    // oriented. createImageBitmap() would be faster but its `imageOrientation`
    // option is silently ignored on older Safari, which would hand back
    // sideways photos with no way to detect it — a wrong result is worse than
    // a slower one.
    function decode(file) {
        return new Promise(function (fulfil, fail) {
            var url = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function () {
                URL.revokeObjectURL(url);
                if (!img.naturalWidth || !img.naturalHeight) {
                    fail(new L.Unsupported('image decoded to zero dimensions'));
                    return;
                }
                fulfil(img);
            };
            img.onerror = function () {
                URL.revokeObjectURL(url);
                // A format this browser can't read (HEIC, TIFF, some BMPs).
                // Pillow on the server can, so let it.
                fail(new L.Unsupported('browser cannot decode this image format'));
            };
            img.src = url;
        });
    }

    // ── Encoding ──────────────────────────────────────────────────────────

    var FORMAT_EXT = { jpg: 'jpg', jpeg: 'jpg', png: 'png', webp: 'webp' };
    var MIME = { jpg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };

    /** scripts/image_utils.py picks the output format from the input suffix,
     *  falling back to jpg for anything it doesn't recognise. */
    function formatOf(filename) {
        var dot = String(filename || '').lastIndexOf('.');
        var ext = dot >= 0 ? filename.slice(dot + 1).toLowerCase() : '';
        return FORMAT_EXT[ext] || 'jpg';
    }

    function canvasOf(w, h) {
        var c = document.createElement('canvas');
        c.width = Math.max(1, Math.round(w));
        c.height = Math.max(1, Math.round(h));
        return c;
    }

    /**
     * Encode a canvas, rejecting rather than silently returning the wrong
     * format. Browsers that can't encode WebP quietly hand back a PNG from
     * toBlob(), which would ship a .webp file containing PNG bytes — better to
     * defer to Pillow.
     */
    function encode(canvas, fmt, quality) {
        var mime = MIME[fmt];
        return new Promise(function (fulfil, fail) {
            canvas.toBlob(function (blob) {
                if (!blob) {
                    fail(new L.Unsupported('canvas could not encode ' + fmt));
                    return;
                }
                if (blob.type && blob.type !== mime) {
                    fail(new L.Unsupported('browser encoded ' + blob.type + ' when asked for ' + mime));
                    return;
                }
                fulfil(blob);
            }, mime, fmt === 'png' ? undefined : (quality / 100));
        });
    }

    /** Draw a decoded image onto a fresh canvas at the given size. */
    function render(img, w, h, drawer) {
        var canvas = canvasOf(w, h);
        var ctx = canvas.getContext('2d');
        if (!ctx) throw new L.Unsupported('2d canvas context unavailable');
        // A transparent source encoded as JPEG composites onto black here, which
        // is also where Pillow's RGBA->RGB conversion lands for fully
        // transparent pixels — so the two agree without special-casing.
        if (drawer) drawer(ctx, canvas);
        else ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        return canvas;
    }

    function only(fd) {
        var all = L.files(fd, 'file');
        if (!all.length) throw new L.Error('No file provided.');
        return all[0];
    }

    // ── /api/image/resize ─────────────────────────────────────────────────

    L.register('/api/image/resize', async function (fd) {
        var mode = L.str(fd, 'mode', null);
        if (['dimensions', 'percentage', 'target_size'].indexOf(mode) < 0) {
            throw new L.Error('mode must be one of: dimensions, percentage, target_size');
        }
        var width = L.range('width', L.int(fd, 'width', null), 1);
        var height = L.range('height', L.int(fd, 'height', null), 1);
        var percentage = L.range('percentage', L.int(fd, 'percentage', null), 1, 500);
        var targetKb = L.range('target_size_kb', L.int(fd, 'target_size_kb', null), 1);

        var file = only(fd);
        var img = await decode(file);
        var ow = img.naturalWidth, oh = img.naturalHeight;
        var nw, nh;

        if (mode === 'dimensions') {
            if (!width && !height) {
                throw new L.Error('Width or height must be provided for dimensions mode.');
            }
            if (width && !height) {
                nw = width; nh = Math.trunc(oh * (width / ow));
            } else if (height && !width) {
                nh = height; nw = Math.trunc(ow * (height / oh));
            } else {
                nw = width; nh = height;
            }
        } else if (mode === 'percentage') {
            if (!percentage) throw new L.Error('Percentage must be provided for percentage mode.');
            nw = Math.trunc(ow * percentage / 100);
            nh = Math.trunc(oh * percentage / 100);
        } else {
            if (!targetKb) throw new L.Error('Target size must be provided for target_size mode.');
            nw = ow; nh = oh;
        }

        // resize_image() always writes JPEG, whatever went in.
        var blob;
        if (mode === 'target_size') {
            blob = await toTargetSize(img, ow, oh, targetKb * 1024);
        } else {
            blob = await encode(render(img, nw, nh), 'jpg', 95);
        }

        return {
            blob: blob,
            filename: L.brandedName(file.name, 'jpg'),
            message: 'Image Resized',
        };
    });

    /**
     * Hit a byte budget the same way resize_image() does: try quality 95, then
     * binary-search quality down to 30, then shrink the canvas by 10% at a time
     * until it fits (stopping before either side goes under 10px).
     */
    async function toTargetSize(img, w, h, targetBytes) {
        var canvas = render(img, w, h);
        var best = await encode(canvas, 'jpg', 95);
        if (best.size <= targetBytes) return best;

        var lo = 30, hi = 95, bestQuality = 30;
        while (lo <= hi) {
            var mid = Math.floor((lo + hi) / 2);
            var candidate = await encode(canvas, 'jpg', mid);
            if (candidate.size <= targetBytes) {
                bestQuality = mid; best = candidate; lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }

        var out = await encode(canvas, 'jpg', bestQuality);
        var cw = w, ch = h;
        while (out.size > targetBytes) {
            cw = Math.trunc(cw * 0.9);
            ch = Math.trunc(ch * 0.9);
            if (cw < 10 || ch < 10) break;
            canvas = render(img, cw, ch);
            out = await encode(canvas, 'jpg', bestQuality);
        }
        return out;
    }

    // ── /api/image/crop ───────────────────────────────────────────────────

    L.register('/api/image/crop', async function (fd) {
        var x = L.range('x', L.int(fd, 'x', null), 0);
        var y = L.range('y', L.int(fd, 'y', null), 0);
        var w = L.range('width', L.int(fd, 'width', null), 1);
        var h = L.range('height', L.int(fd, 'height', null), 1);
        if (x === null || y === null || w === null || h === null) {
            throw new L.Error('x, y, width and height are required.');
        }

        var file = only(fd);
        var img = await decode(file);

        // crop_image() clamps the box to the image rather than erroring.
        x = Math.max(0, x);
        y = Math.max(0, y);
        var right = Math.min(img.naturalWidth, x + w);
        var lower = Math.min(img.naturalHeight, y + h);
        var cw = right - x, ch = lower - y;
        if (cw <= 0 || ch <= 0) {
            throw new L.Error('The crop area falls outside the image.');
        }

        var canvas = canvasOf(cw, ch);
        canvas.getContext('2d').drawImage(img, x, y, cw, ch, 0, 0, cw, ch);

        return {
            blob: await encode(canvas, 'jpg', 95),
            filename: L.brandedName(file.name, 'jpg'),
            message: 'Image Cropped',
        };
    });

    // ── /api/image/rotate ─────────────────────────────────────────────────

    L.register('/api/image/rotate', async function (fd) {
        var angle = L.num(fd, 'angle', 90);
        var quality = L.range('quality', L.int(fd, 'quality', 95), 1, 100);

        var file = only(fd);
        var fmt = formatOf(file.name);
        var img = await decode(file);
        var w = img.naturalWidth, h = img.naturalHeight;

        // Pillow's Image.rotate() turns counter-clockwise and expand=True grows
        // the canvas to the rotated bounding box; canvas rotate() is clockwise,
        // hence the negated radians.
        var rad = -angle * Math.PI / 180;
        var cos = Math.abs(Math.cos(rad)), sin = Math.abs(Math.sin(rad));
        var bw = Math.round(w * cos + h * sin);
        var bh = Math.round(w * sin + h * cos);

        var canvas = render(img, bw, bh, function (ctx) {
            ctx.translate(bw / 2, bh / 2);
            ctx.rotate(rad);
            ctx.drawImage(img, -w / 2, -h / 2);
        });

        return {
            blob: await encode(canvas, fmt, quality),
            filename: L.brandedName(file.name, FORMAT_EXT[fmt]),
            message: 'Rotated by ' + angle + '°',
        };
    });

    // ── /api/image/compress ───────────────────────────────────────────────

    L.register('/api/image/compress', async function (fd) {
        var quality = L.int(fd, 'quality', 70);
        if (!(quality >= 1 && quality <= 100)) {
            throw new L.Error('quality must be between 1 and 100.');
        }

        var file = only(fd);
        var fmt = formatOf(file.name);
        var img = await decode(file);
        var blob = await encode(render(img, img.naturalWidth, img.naturalHeight), fmt, quality);

        return {
            blob: blob,
            filename: L.brandedName(file.name, FORMAT_EXT[fmt]),
            message: 'Image compressed',
            // compress_image() also reports these; the image UI ignores them,
            // but returning them keeps the response shapes identical.
            extra: {
                original_size: file.size,
                compressed_size: blob.size,
                reduction_pct: file.size
                    ? Math.round(Math.max(0, (1 - blob.size / file.size) * 100) * 10) / 10
                    : 0,
            },
        };
    });

    // ── /api/image/convert ────────────────────────────────────────────────

    L.register('/api/image/convert', async function (fd) {
        var target = String(L.str(fd, 'target_format', '') || '').toLowerCase();
        if (!FORMAT_EXT[target]) {
            throw new L.Error('target_format must be one of: jpg, png, webp.');
        }
        var quality = L.range('quality', L.int(fd, 'quality', 90), 1, 100);

        var file = only(fd);
        var img = await decode(file);
        var fmt = FORMAT_EXT[target];
        var canvas = render(img, img.naturalWidth, img.naturalHeight);

        return {
            blob: await encode(canvas, fmt, quality),
            filename: L.brandedName(file.name, fmt),
            message: 'Converted to ' + target.toUpperCase(),
        };
    });

    // ── /api/image/watermark ──────────────────────────────────────────────

    var COLORS = {
        white: 'rgb(255,255,255)',
        black: 'rgb(0,0,0)',
        red: 'rgb(220,30,30)',
        blue: 'rgb(30,30,220)',
    };
    var POSITIONS = ['top-left', 'top-right', 'center', 'bottom-left', 'bottom-right', 'diagonal'];

    L.register('/api/image/watermark', async function (fd) {
        var text = L.str(fd, 'text', '');
        if (!text || !text.trim()) throw new L.Error('Watermark text cannot be empty.');

        var position = L.str(fd, 'position', 'bottom-right');
        if (POSITIONS.indexOf(position) < 0) {
            throw new L.Error('position must be one of: ' + POSITIONS.join(', ') + '.');
        }
        var opacity = L.num(fd, 'opacity', 0.4);
        if (!(opacity >= 0.05 && opacity <= 1.0)) {
            throw new L.Error('opacity must be between 0.05 and 1.0.');
        }
        var color = COLORS[String(L.str(fd, 'color', 'white')).toLowerCase()] || COLORS.white;

        var file = only(fd);
        var fmt = formatOf(file.name);
        var img = await decode(file);
        var w = img.naturalWidth, h = img.naturalHeight;

        // watermark_image() sizes the type off the shorter edge. Note it asks
        // Pillow for arial.ttf and falls back to load_default() — a ~11px
        // bitmap face — on any machine without it, which is every Linux box the
        // app has ever run on. Here the requested size is actually honoured, so
        // on-device watermarks are legible where server ones are not; matching
        // that bug is not worth doing.
        var fontSize = Math.max(20, Math.trunc(Math.min(w, h) / 20));
        var margin = Math.max(10, Math.trunc(Math.min(w, h) * 0.02));

        var canvas = render(img, w, h, function (ctx) {
            ctx.drawImage(img, 0, 0);
            ctx.globalAlpha = opacity;
            ctx.fillStyle = color;
            ctx.font = fontSize + 'px sans-serif';

            if (position === 'diagonal') {
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.translate(w / 2, h / 2);
                ctx.rotate(-30 * Math.PI / 180);
                ctx.fillText(text, 0, 0);
                return;
            }

            // Pillow anchors text at its top-left corner; so does canvas with
            // textBaseline 'top', which keeps the offsets below identical.
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            var metrics = ctx.measureText(text);
            var tw = metrics.width;
            var th = (metrics.actualBoundingBoxAscent && metrics.actualBoundingBoxDescent)
                ? metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent
                : fontSize;

            var x, y;
            if (position === 'top-left') { x = margin; y = margin; }
            else if (position === 'top-right') { x = w - tw - margin; y = margin; }
            else if (position === 'center') { x = (w - tw) / 2; y = (h - th) / 2; }
            else if (position === 'bottom-left') { x = margin; y = h - th - margin; }
            else { x = w - tw - margin; y = h - th - margin; }

            ctx.fillText(text, x, y);
        });

        return {
            blob: await encode(canvas, fmt, 95),
            filename: L.brandedName(file.name, FORMAT_EXT[fmt]),
            message: 'Watermark added',
        };
    });

    // Exposed for the unit tests, which run this file under Node with a DOM
    // shim and need the pure helpers without going through a handler.
    L.image = { formatOf: formatOf, FORMAT_EXT: FORMAT_EXT };
})();
