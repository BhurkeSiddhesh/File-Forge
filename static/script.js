
// === Authentication ===

function getApiKey() {
    return localStorage.getItem('fileForgeApiKey');
}

function saveApiKey(key) {
    localStorage.setItem('fileForgeApiKey', key);
}

function showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.remove('hidden');
}

function hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.add('hidden');
}

const loginBtn = document.getElementById('login-submit-btn');
if (loginBtn) {
    loginBtn.onclick = () => {
        const key = document.getElementById('api-key-input').value;
        if (key) {
            saveApiKey(key);
            hideLoginModal();
            alert("API Key saved. Please retry your action.");
        }
    };
}

const keyInput = document.getElementById('api-key-input');
if (keyInput) {
    keyInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('login-submit-btn').click();
        }
    });
}

async function fetchWithAuth(url, options = {}) {
    const headers = options.headers || {};
    const key = getApiKey();
    if (key) {
        headers['X-API-Key'] = key;
    }
    options.headers = headers;

    const response = await fetch(url, options);

    if (response.status === 401 || response.status === 403) {
        showLoginModal();
        throw new Error("Authentication required. Please enter your API Key.");
    }

    return response;
}

function updateDownloadLink(element, filename) {
    if (!element) return;
    const key = getApiKey();
    const url = `/api/download/${encodeURIComponent(filename)}`;
    
    // Construct authenticated direct link for native browser features (Save As..., etc.)
    const authenticatedUrl = key ? `${url}?api_key=${encodeURIComponent(key)}` : url;
    element.href = authenticatedUrl;

    element.onclick = async (e) => {
        // We intercept left-clicks to provide a friendly 404 alert if the file is gone.
        // For context-menu actions (Save As...), the browser hits the href directly.
        
        try {
            // HEAD request is lightweight and verifies existence/auth without downloading.
            const response = await fetch(url, {
                method: 'HEAD',
                headers: key ? { 'X-API-Key': key } : {}
            });

            if (response.status === 404) {
                e.preventDefault();
                alert("The converted file no longer exists. Please re-process.");
                return false;
            }

            if (!response.ok) {
                e.preventDefault();
                if (response.status === 401 || response.status === 403) {
                    showLoginModal();
                    return false;
                }
                throw new Error(`Status ${response.status}`);
            }
            
            // If OK, let the browser proceed with the native download via element.href.
            // This avoids loading the entire file into memory as a Blob.
            return true;

        } catch (error) {
            console.error('Download check failed:', error);
            // On network error, still try to let the browser handle it
            return true;
        }
    };
}

// === End Authentication ===

let selectedFile = null;
let selectedFiles = [];
let selectedImageFile = null;
let currentTool = null;

// Navigation
function showDrillDown(tool) {
    currentTool = tool;
    let pageId;
    if (tool === 'pdf') pageId = 'pdf-page';
    else if (tool === 'image') pageId = 'image-page';
    else if (tool === 'excel') pageId = 'excel-page';
    else if (tool === 'ppt') pageId = 'ppt-page';
    else if (tool === 'workflow') pageId = 'workflow-page';
    else return;

    document.getElementById('home-page').classList.remove('active');
    setTimeout(() => {
        document.getElementById('home-page').style.display = 'none';
        document.getElementById(pageId).style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'instant' });
        setTimeout(() => {
            document.getElementById(pageId).classList.add('active');
        }, 50);
    }, 500);
}

function showHome() {
    let pageId;
    if (currentTool === 'pdf') pageId = 'pdf-page';
    else if (currentTool === 'image') pageId = 'image-page';
    else if (currentTool === 'excel') pageId = 'excel-page';
    else if (currentTool === 'ppt') pageId = 'ppt-page';
    else if (currentTool === 'workflow') pageId = 'workflow-page';
    else pageId = 'pdf-page';

    document.getElementById(pageId).classList.remove('active');
    resetUI();
    setTimeout(() => {
        document.getElementById(pageId).style.display = 'none';
        document.getElementById('home-page').style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'instant' });
        setTimeout(() => {
            document.getElementById('home-page').classList.add('active');
        }, 50);
    }, 500);
}

// File Selection
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const filenameDisplay = document.getElementById('filename-display');
const fileInfo = document.getElementById('file-info');

dropZone.onclick = () => fileInput.click();

fileInput.onchange = (e) => {
    if (e.target.files.length > 0) {
        if (fileInput.multiple) {
            handleFiles(Array.from(e.target.files));
        } else {
            handleFile(e.target.files[0]);
        }
    }
};

dropZone.ondragover = (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
};

dropZone.ondragleave = () => {
    dropZone.classList.remove('drag-over');
};

dropZone.ondrop = (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
        if (fileInput.multiple) {
            handleFiles(Array.from(e.dataTransfer.files));
        } else {
            handleFile(e.dataTransfer.files[0]);
        }
    }
};

function hidePdfActionAreas() {
    document.getElementById('password-input-area').classList.add('hidden');
    document.getElementById('convert-password-area').classList.add('hidden');
    document.getElementById('extract-pages-area')?.classList.add('hidden');
    document.getElementById('compress-area')?.classList.add('hidden');
    document.getElementById('merge-area')?.classList.add('hidden');
    document.getElementById('watermark-area')?.classList.add('hidden');
    document.getElementById('to-images-area')?.classList.add('hidden');
    document.getElementById('sign-area')?.classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');
}

function setMergeMode(on) {
    fileInput.multiple = !!on;
    if (!on) {
        selectedFiles = [];
    } else {
        selectedFile = null;
    }
}

function handleFiles(files) {
    const pdfs = files.filter(f => f.type === 'application/pdf');
    if (pdfs.length === 0) {
        alert('Please select PDF files.');
        return;
    }
    selectedFiles = pdfs;
    selectedFile = pdfs[0];
    filenameDisplay.textContent = pdfs.length === 1
        ? pdfs[0].name
        : `${pdfs.length} files: ${pdfs.map(f => f.name).join(', ')}`;
    fileInfo.classList.remove('hidden');
    document.getElementById('status-display').classList.add('hidden');
}

function handleFile(file) {
    if (file.type !== 'application/pdf') {
        alert('Please select a PDF file.');
        return;
    }
    selectedFile = file;
    filenameDisplay.textContent = file.name;
    fileInfo.classList.remove('hidden');

    // Reset displays
    document.getElementById('status-display').classList.add('hidden');
    hidePdfActionAreas();
    const extractInput = document.getElementById('extract-pages-input');
    const extractPassword = document.getElementById('extract-password');
    if (extractInput) extractInput.value = '';
    if (extractPassword) extractPassword.value = '';
}

// Actions
document.getElementById('remove-password-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('password-input-area').classList.remove('hidden');
};

document.getElementById('convert-word-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('convert-password-area').classList.remove('hidden');
};

document.getElementById('extract-pages-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('extract-pages-area').classList.remove('hidden');
};

document.getElementById('compress-pdf-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('compress-area').classList.remove('hidden');
};

document.getElementById('merge-pdf-btn').onclick = () => {
    setMergeMode(true);
    hidePdfActionAreas();
    document.getElementById('merge-area').classList.remove('hidden');
};

document.getElementById('watermark-pdf-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('watermark-area').classList.remove('hidden');
};

document.getElementById('to-images-pdf-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('to-images-area').classList.remove('hidden');
};

document.getElementById('sign-pdf-btn').onclick = () => {
    setMergeMode(false);
    if (!selectedFile) { alert('Please select a file first.'); return; }
    hidePdfActionAreas();
    document.getElementById('sign-area').classList.remove('hidden');
};

document.getElementById('process-compress-btn').onclick = async () => {
    const level = document.querySelector('input[name="compress-level"]:checked')?.value || 'medium';
    const password = document.getElementById('compress-password').value || null;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('level', level);
    if (password) formData.append('password', password);

    const statusDisplay = document.getElementById('status-display');
    const statusText = document.getElementById('status-text');
    const resultDisplay = document.getElementById('result-display');

    statusDisplay.classList.remove('hidden');
    statusText.textContent = 'Compressing PDF...';
    resultDisplay.classList.add('hidden');

    try {
        const response = await fetchWithAuth('/api/pdf/compress', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (response.ok) {
            statusDisplay.classList.add('hidden');
            showCompressResult(data);
        } else {
            statusDisplay.classList.add('hidden');
            alert('Error: ' + (data.detail || 'Compression failed'));
        }
    } catch (error) {
        statusDisplay.classList.add('hidden');
        alert('An error occurred: ' + error.message);
    }
};

document.getElementById('process-convert-btn').onclick = async () => {
    const useAI = document.getElementById('ai-mode-toggle').checked;
    const password = document.getElementById('convert-password').value || null;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('use_ai', useAI);
    if (password) {
        formData.append('password', password);
    }

    const statusMsg = useAI ? 'Analyzing layout with AI (this may take a while)...' : 'Converting PDF to Word...';
    processAction('/api/pdf/convert-to-word', statusMsg, formData);
};

document.getElementById('process-password-btn').onclick = () => {
    const password = document.getElementById('pdf-password').value;
    if (!password) {
        alert('Please enter a password.');
        return;
    }
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('password', password);

    processAction('/api/pdf/remove-password', 'Removing password...', formData);
};

document.getElementById('process-extract-btn').onclick = () => {
    const pages = document.getElementById('extract-pages-input').value.trim();
    const password = document.getElementById('extract-password').value;

    if (!pages) {
        alert('Please enter pages to extract (e.g., 1,3,5-7 or all).');
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('pages', pages);
    if (password) {
        formData.append('password', password);
    }

    processAction('/api/pdf/extract-pages', 'Extracting selected pages...', formData);
};

document.getElementById('process-merge-btn').onclick = () => {
    if (!selectedFiles || selectedFiles.length < 2) {
        alert('Please select at least two PDF files in the upload area.');
        return;
    }
    const passwords = document.getElementById('merge-passwords').value || '';
    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));
    if (passwords) formData.append('passwords', passwords);
    processAction('/api/pdf/merge', `Merging ${selectedFiles.length} PDFs...`, formData);
};

const watermarkOpacityInput = document.getElementById('watermark-opacity');
if (watermarkOpacityInput) {
    watermarkOpacityInput.addEventListener('input', (e) => {
        document.getElementById('watermark-opacity-value').textContent = e.target.value;
    });
}

document.getElementById('process-watermark-btn').onclick = () => {
    if (!selectedFile) { alert('Please select a file first.'); return; }
    const text = document.getElementById('watermark-text').value.trim();
    if (!text) { alert('Please enter watermark text.'); return; }
    const position = document.getElementById('watermark-position').value;
    const opacity = document.getElementById('watermark-opacity').value;
    const password = document.getElementById('watermark-password').value;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('text', text);
    formData.append('position', position);
    formData.append('opacity', opacity);
    if (password) formData.append('password', password);

    processAction('/api/pdf/watermark', 'Adding watermark...', formData);
};

document.getElementById('process-to-images-btn').onclick = () => {
    if (!selectedFile) { alert('Please select a file first.'); return; }
    const dpi = document.getElementById('to-images-dpi').value;
    const fmt = document.getElementById('to-images-format').value;
    const password = document.getElementById('to-images-password').value;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('dpi', dpi);
    formData.append('fmt', fmt);
    if (password) formData.append('password', password);

    processAction('/api/pdf/to-images', 'Rendering pages to images...', formData);
};

const signWidthInput = document.getElementById('sign-width');
if (signWidthInput) {
    signWidthInput.addEventListener('input', (e) => {
        document.getElementById('sign-width-value').textContent =
            Math.round(parseFloat(e.target.value) * 100) + '%';
    });
}

const SIGN_POSITION_PRESETS = {
    'top-right':      { x: 0.65, y: 0.05 },
    'bottom-right':   { x: 0.65, y: 0.85 },
    'bottom-center':  { x: 0.40, y: 0.85 },
    'bottom-left':    { x: 0.05, y: 0.85 },
};

document.getElementById('process-sign-btn').onclick = () => {
    if (!selectedFile) { alert('Please select a PDF file first.'); return; }
    const sigInput = document.getElementById('signature-image');
    const sigFile = sigInput?.files?.[0];
    if (!sigFile) { alert('Please choose a signature image.'); return; }

    const page = parseInt(document.getElementById('sign-page').value, 10) || 1;
    const positionKey = document.getElementById('sign-position').value;
    const preset = SIGN_POSITION_PRESETS[positionKey] || SIGN_POSITION_PRESETS['bottom-right'];
    const width = document.getElementById('sign-width').value;
    const password = document.getElementById('sign-password').value;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('signature', sigFile);
    formData.append('page', page);
    formData.append('x', preset.x);
    formData.append('y', preset.y);
    formData.append('width', width);
    if (password) formData.append('password', password);

    processAction('/api/pdf/sign', 'Adding signature...', formData);
};

async function processAction(url, text, formData = null) {
    const statusDisplay = document.getElementById('status-display');
    const statusText = document.getElementById('status-text');
    const resultDisplay = document.getElementById('result-display');
    const passwordArea = document.getElementById('password-input-area');

    statusDisplay.classList.remove('hidden');
    statusText.textContent = text;
    resultDisplay.classList.add('hidden');
    if (formData === null) passwordArea.classList.add('hidden');

    if (!formData) {
        formData = new FormData();
        formData.append('file', selectedFile);
    }

    try {
        const response = await fetchWithAuth(url, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            showResult(data.filename, data.message);
        } else {
            // Try to parse as JSON first, fall back to text
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                alert('Error: ' + data.detail);
            } else {
                const text = await response.text();
                alert('Error: ' + text);
            }
        }
    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        statusDisplay.classList.add('hidden');
    }

}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function showResult(filename, message) {
    const resultDisplay = document.getElementById('result-display');
    const resultMessage = document.getElementById('result-message');
    const downloadLink = document.getElementById('download-link');

    // Clear any previous compress stats
    const existingStats = resultDisplay.querySelector('.compress-stats');
    if (existingStats) existingStats.remove();
    const existingBadge = resultDisplay.querySelector('.reduction-badge');
    if (existingBadge) existingBadge.remove();

    resultDisplay.classList.remove('hidden');
    resultMessage.textContent = message + ': ' + filename;
    updateDownloadLink(downloadLink, filename);
}

function showCompressResult(data) {
    const resultDisplay = document.getElementById('result-display');
    const resultMessage = document.getElementById('result-message');
    const downloadLink = document.getElementById('download-link');

    // Clear any previous compress stats
    const existingStats = resultDisplay.querySelector('.compress-stats');
    if (existingStats) existingStats.remove();
    const existingBadge = resultDisplay.querySelector('.reduction-badge');
    if (existingBadge) existingBadge.remove();

    resultDisplay.classList.remove('hidden');
    resultMessage.textContent = 'Compressed: ' + data.filename;
    updateDownloadLink(downloadLink, data.filename);

    // Build size stats display
    const badge = document.createElement('div');
    badge.className = 'reduction-badge';
    badge.textContent = `↓ ${data.reduction_pct}% smaller`;

    const stats = document.createElement('div');
    stats.className = 'compress-stats';
    stats.innerHTML = `
        <div class="compress-stat">
            <span class="stat-label">Original</span>
            <span class="stat-value">${formatBytes(data.original_size)}</span>
        </div>
        <span class="compress-stat-arrow"><i class="fas fa-arrow-right"></i></span>
        <div class="compress-stat">
            <span class="stat-label">Compressed</span>
            <span class="stat-value">${formatBytes(data.compressed_size)}</span>
        </div>
    `;

    // Insert after the message, before the download button
    resultMessage.insertAdjacentElement('afterend', stats);
    stats.insertAdjacentElement('afterend', badge);
}

function resetUI() {
    selectedFile = null;
    selectedFiles = [];
    selectedImageFile = null;
    currentTool = null;
    fileInput.value = '';
    fileInput.multiple = false;
    filenameDisplay.textContent = 'No file selected';
    fileInfo.classList.add('hidden');
    document.getElementById('password-input-area').classList.add('hidden');
    document.getElementById('convert-password-area').classList.add('hidden');
    document.getElementById('extract-pages-area')?.classList.add('hidden');
    document.getElementById('compress-area')?.classList.add('hidden');
    document.getElementById('merge-area')?.classList.add('hidden');
    document.getElementById('watermark-area')?.classList.add('hidden');
    document.getElementById('to-images-area')?.classList.add('hidden');
    document.getElementById('sign-area')?.classList.add('hidden');
    document.getElementById('status-display').classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');
    const extractInput = document.getElementById('extract-pages-input');
    if (extractInput) extractInput.value = '';
    const extractPwd = document.getElementById('extract-password');
    if (extractPwd) extractPwd.value = '';

    // Reset image tools
    const imageFileInput = document.getElementById('image-file-input');
    const imageFilenameDisplay = document.getElementById('image-filename-display');
    const imageFileInfo = document.getElementById('image-file-info');
    if (imageFileInput) imageFileInput.value = '';
    if (imageFilenameDisplay) imageFilenameDisplay.textContent = 'No file selected';
    if (imageFileInfo) imageFileInfo.classList.add('hidden');
    document.getElementById('image-status-display')?.classList.add('hidden');
    document.getElementById('image-result-display')?.classList.add('hidden');
}

// === Image Tools ===

const imageDropZone = document.getElementById('image-drop-zone');
const imageFileInput = document.getElementById('image-file-input');
const imageFilenameDisplay = document.getElementById('image-filename-display');
const imageFileInfo = document.getElementById('image-file-info');
const qualitySlider = document.getElementById('quality-slider');
const qualityValue = document.getElementById('quality-value');

if (imageDropZone) {
    imageDropZone.onclick = () => imageFileInput.click();

    imageFileInput.onchange = (e) => {
        if (e.target.files.length > 0) {
            handleImageFile(e.target.files[0]);
        }
    };

    imageDropZone.ondragover = (e) => {
        e.preventDefault();
        imageDropZone.classList.add('drag-over');
    };

    imageDropZone.ondragleave = () => {
        imageDropZone.classList.remove('drag-over');
    };

    imageDropZone.ondrop = (e) => {
        e.preventDefault();
        imageDropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleImageFile(e.dataTransfer.files[0]);
        }
    };
}

if (qualitySlider) {
    qualitySlider.oninput = () => {
        qualityValue.textContent = qualitySlider.value;
    };
}

function handleImageFile(file) {
    const validExts = ['.heic', '.heif', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!file.type.startsWith('image/') && !validExts.includes(ext)) {
        alert('Please select an image file (HEIC, JPG, PNG, WebP, BMP, TIFF, GIF).');
        return;
    }
    selectedImageFile = file;
    imageFilenameDisplay.textContent = file.name;
    imageFileInfo.classList.remove('hidden');

    document.getElementById('image-status-display').classList.add('hidden');
    document.getElementById('image-result-display').classList.add('hidden');
    hideImageActionAreas();
}

function hideImageActionAreas() {
    ['rotate-image-area', 'compress-image-area', 'convert-format-area', 'watermark-image-area']
        .forEach(id => document.getElementById(id)?.classList.add('hidden'));
}

// Convert to JPEG
const convertJpegBtn = document.getElementById('convert-jpeg-btn');
if (convertJpegBtn) {
    convertJpegBtn.onclick = () => {
        if (!selectedImageFile) {
            alert('Please select a file first.');
            return;
        }

        const quality = qualitySlider ? parseInt(qualitySlider.value) : 95;
        const formData = new FormData();
        formData.append('file', selectedImageFile);
        formData.append('quality', quality);

        processImageAction('/api/image/heic-to-jpeg', 'Converting HEIC to JPEG...', formData);
    };
}

async function processImageAction(url, text, formData) {
    const statusDisplay = document.getElementById('image-status-display');
    const statusText = document.getElementById('image-status-text');
    const resultDisplay = document.getElementById('image-result-display');

    statusDisplay.classList.remove('hidden');
    statusText.textContent = text;
    resultDisplay.classList.add('hidden');

    try {
        const response = await fetchWithAuth(url, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            showImageResult(data.filename, data.message);
        } else {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                alert('Error: ' + data.detail);
            } else {
                const text = await response.text();
                alert('Error: ' + text);
            }
        }
    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        statusDisplay.classList.add('hidden');
    }
}

function showImageResult(filename, message) {
    const resultDisplay = document.getElementById('image-result-display');
    const resultMessage = document.getElementById('image-result-message');
    const downloadLink = document.getElementById('image-download-link');

    resultDisplay.classList.remove('hidden');
    resultMessage.textContent = message + ': ' + filename;
    updateDownloadLink(downloadLink, filename);
}

// --- Image Resize & Crop Functions ---

let cropper = null;

function toggleImageMode() {
    const isResize = document.getElementById('mode-resize').checked;
    const isCrop = document.getElementById('mode-crop').checked;

    const convertOptions = document.getElementById('convert-options');
    const resizeOptions = document.getElementById('resize-options');
    const cropOptions = document.getElementById('crop-options');

    const convertBtn = document.getElementById('convert-jpeg-btn');
    const resizeBtn = document.getElementById('resize-btn');
    const cropBtn = document.getElementById('crop-btn');

    // Hide all first
    convertOptions.classList.add('hidden');
    resizeOptions.classList.add('hidden');
    cropOptions.classList.add('hidden');

    convertBtn.classList.add('hidden');
    resizeBtn.classList.add('hidden');
    cropBtn.classList.add('hidden');

    if (isResize) {
        resizeOptions.classList.remove('hidden');
        resizeBtn.classList.remove('hidden');
        destroyCropper();
    } else if (isCrop) {
        cropOptions.classList.remove('hidden');
        cropBtn.classList.remove('hidden');
        initCropper();
    } else {
        convertOptions.classList.remove('hidden');
        convertBtn.classList.remove('hidden');
        destroyCropper();
    }
}

function destroyCropper() {
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }
}

async function initCropper() {
    if (!selectedImageFile) return;

    const image = document.getElementById('crop-image-preview');
    const container = document.getElementById('crop-editor-container');
    const statusDisplay = document.getElementById('image-status-display');
    const statusText = document.getElementById('image-status-text');

    // Check for HEIC/HEIF
    const ext = '.' + selectedImageFile.name.split('.').pop().toLowerCase();
    const isHeic = ext === '.heic' || ext === '.heif' || selectedImageFile.type === 'image/heic' || selectedImageFile.type === 'image/heif';

    if (isHeic) {
        // Show loading state
        if (statusDisplay) {
            statusDisplay.classList.remove('hidden');
            statusText.innerText = "Generating preview...";
        }
        container.classList.add('hidden'); // Hide until ready

        try {
            const formData = new FormData();
            formData.append('file', selectedImageFile);
            formData.append('quality', 80); // Faster preview

            const response = await fetchWithAuth('/api/image/heic-to-jpeg', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Preview generation failed");
            }

            const data = await response.json();

            // Set up onload before setting src
            image.onload = () => {
                if (statusDisplay) statusDisplay.classList.add('hidden');
                container.classList.remove('hidden');

                destroyCropper();
                cropper = new Cropper(image, {
                    viewMode: 1,
                    autoCropArea: 0.8,
                    movable: false,
                    zoomable: true,
                    rotatable: false,
                    scalable: false,
                });
            };
            image.src = `/api/download/${data.filename}?api_key=${encodeURIComponent(getApiKey() || "")}`;

        } catch (e) {
            console.error(e);
            alert("Could not load HEIC preview: " + e.message);
            if (statusDisplay) statusDisplay.classList.add('hidden');
        }

    } else {
        // Standard flow for supported images (JPG, PNG)
        const reader = new FileReader();
        reader.onload = (e) => {
            image.src = e.target.result;
            container.classList.remove('hidden');

            // Destroy existing to avoid duplicates
            destroyCropper();

            cropper = new Cropper(image, {
                viewMode: 1,
                autoCropArea: 0.8,
                movable: false,
                zoomable: true,
                rotatable: false,
                scalable: false,
            });
        };
        reader.readAsDataURL(selectedImageFile);
    }
}

// Hook into existing handleImageFile to trigger cropper if in crop mode
const originalHandleImageFile = handleImageFile;
handleImageFile = function (file) {
    // Call original logic
    const validTypes = ['image/heic', 'image/heif', 'image/jpeg', 'image/png', 'image/webp'];
    const validExts = ['.heic', '.heif', '.jpg', '.jpeg', '.png', '.webp'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
        alert('Please select a valid image file (HEIC, JPG, PNG).');
        return;
    }
    selectedImageFile = file;
    document.getElementById('image-filename-display').textContent = file.name;
    document.getElementById('image-file-info').classList.remove('hidden');
    document.getElementById('image-status-display').classList.add('hidden');
    document.getElementById('image-result-display').classList.add('hidden');

    // If currently in crop mode, init cropper
    if (document.getElementById('mode-crop').checked) {
        initCropper();
    }
};

function toggleResizeInputs() {
    const method = document.getElementById('resize-method').value;
    document.getElementById('input-dimensions').classList.add('hidden');
    document.getElementById('input-percentage').classList.add('hidden');
    document.getElementById('input-target-size').classList.add('hidden');

    if (method === 'dimensions') {
        document.getElementById('input-dimensions').classList.remove('hidden');
    } else if (method === 'percentage') {
        document.getElementById('input-percentage').classList.remove('hidden');
    } else if (method === 'target_size') {
        document.getElementById('input-target-size').classList.remove('hidden');
    }
}

async function resizeImage() {
    if (!selectedImageFile) {
        alert("Please select an image file first.");
        return;
    }
    const file = selectedImageFile;

    const mode = document.getElementById('resize-method').value;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);

    if (mode === 'dimensions') {
        const width = document.getElementById('resize-width').value;
        const height = document.getElementById('resize-height').value;
        if (!width && !height) {
            alert("Please enter at least width or height.");
            return;
        }
        if (width) formData.append('width', width);
        if (height) formData.append('height', height);
    } else if (mode === 'percentage') {
        const percentage = document.getElementById('scale-slider').value;
        formData.append('percentage', percentage);
    } else if (mode === 'target_size') {
        const targetSize = document.getElementById('target-size-kb').value;
        if (!targetSize) {
            alert("Please enter a target size.");
            return;
        }
        formData.append('target_size_kb', targetSize);
    }

    const statusDisplay = document.getElementById('image-status-display');
    const resultDisplay = document.getElementById('image-result-display');
    const statusText = document.getElementById('image-status-text');
    const resultMessage = document.getElementById('image-result-message');
    const downloadLink = document.getElementById('image-download-link');

    // Reset UI
    statusDisplay.classList.remove('hidden');
    resultDisplay.classList.add('hidden');
    statusText.innerText = "Resizing image...";

    try {
        const response = await fetchWithAuth('/api/image/resize', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            resultMessage.innerText = `${data.message}: ${data.filename}`;
            updateDownloadLink(downloadLink, data.filename);
            downloadLink.innerText = `Download ${data.filename}`;
        } else {
            throw new Error(data.detail || 'Resize failed');
        }
    } catch (error) {
        console.error('Error:', error);
        statusDisplay.classList.add('hidden');
        alert("An error occurred: " + error.message);
    }
}

async function cropImage() {
    if (!cropper) {
        alert("Please start cropping first.");
        return;
    }

    // Get crop data (x, y, width, height)
    const data = cropper.getData(true); // true for rounded integers

    const formData = new FormData();
    formData.append('file', selectedImageFile);
    formData.append('x', data.x);
    formData.append('y', data.y);
    formData.append('width', data.width);
    formData.append('height', data.height);

    const statusDisplay = document.getElementById('image-status-display');
    const resultDisplay = document.getElementById('image-result-display');
    const statusText = document.getElementById('image-status-text');
    const resultMessage = document.getElementById('image-result-message');
    const downloadLink = document.getElementById('image-download-link');

    // Reset UI
    statusDisplay.classList.remove('hidden');
    resultDisplay.classList.add('hidden');
    statusText.innerText = "Cropping image...";

    try {
        const response = await fetchWithAuth('/api/image/crop', {
            method: 'POST',
            body: formData
        });

        const respData = await response.json();

        if (response.ok) {
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            resultMessage.innerText = `${respData.message}: ${respData.filename}`;
            updateDownloadLink(downloadLink, respData.filename);
            downloadLink.innerText = `Download ${respData.filename}`;
        } else {
            throw new Error(respData.detail || 'Crop failed');
        }
    } catch (error) {
        console.error('Error:', error);
        statusDisplay.classList.add('hidden');
        alert("An error occurred: " + error.message);
    }
}

// === Workflow Builder ===

let workflowFile = null;
let workflowSteps = [];
let currentConfigStepIndex = null;

// Initialize workflow builder when DOM is ready
document.addEventListener('DOMContentLoaded', initWorkflowBuilder);

function initWorkflowBuilder() {
    const dropZone = document.getElementById('workflow-drop-zone');
    const fileInput = document.getElementById('workflow-file-input');
    const canvas = document.getElementById('workflow-canvas');
    const stepItems = document.querySelectorAll('.step-item');

    if (!dropZone || !fileInput || !canvas) return;

    // File drop handling
    dropZone.onclick = () => fileInput.click();

    fileInput.onchange = (e) => {
        if (e.target.files.length > 0) {
            handleWorkflowFile(e.target.files[0]);
        }
    };

    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    };

    dropZone.ondragleave = () => dropZone.classList.remove('drag-over');

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleWorkflowFile(e.dataTransfer.files[0]);
        }
    };

    // Step palette drag start
    stepItems.forEach(item => {
        item.ondragstart = (e) => {
            e.dataTransfer.setData('step-type', item.dataset.stepType);
            e.dataTransfer.setData('step-label', item.dataset.stepLabel);
            e.dataTransfer.setData('step-icon', item.dataset.stepIcon);
            item.style.opacity = '0.5';
        };
        item.ondragend = () => {
            item.style.opacity = '1';
        };

        // A11y: Click to add step
        item.onclick = () => {
            addStepToWorkflow(item.dataset.stepType, item.dataset.stepLabel, item.dataset.stepIcon);
        };
    });

    // Canvas drop handling
    canvas.ondragover = (e) => {
        e.preventDefault();
        canvas.classList.add('drag-over');
    };

    canvas.ondragleave = () => canvas.classList.remove('drag-over');

    canvas.ondrop = (e) => {
        e.preventDefault();
        canvas.classList.remove('drag-over');

        const stepType = e.dataTransfer.getData('step-type');
        const stepLabel = e.dataTransfer.getData('step-label');
        const stepIcon = e.dataTransfer.getData('step-icon');

        if (stepType) {
            addStepToWorkflow(stepType, stepLabel, stepIcon);
        }
    };
}

function handleWorkflowFile(file) {
    workflowFile = file;
    document.getElementById('workflow-filename-display').textContent = file.name;
    document.getElementById('workflow-file-info').classList.remove('hidden');

    // Reset status displays
    document.getElementById('workflow-status-display').classList.add('hidden');
    document.getElementById('workflow-result-display').classList.add('hidden');
}

function addStepToWorkflow(type, label, icon) {
    const step = {
        id: Date.now(),
        type: type,
        label: label,
        icon: icon,
        config: {}
    };

    // Steps that need configuration
    if (type === 'remove_password') {
        step.config.password = '';
    } else if (type === 'resize_image') {
        step.config.mode = 'percentage';
        step.config.percentage = 50;
    } else if (type === 'compress_pdf') {
        step.config.level = 'medium';
    }

    workflowSteps.push(step);
    renderWorkflowSteps();

    // If step needs config, open modal
    if (type === 'remove_password' || type === 'resize_image' || type === 'compress_pdf') {
        openConfigModal(workflowSteps.length - 1);
    }
}

function renderWorkflowSteps() {
    const container = document.getElementById('workflow-steps-container');
    const placeholder = document.querySelector('.canvas-placeholder');

    if (workflowSteps.length === 0) {
        container.classList.add('hidden');
        placeholder.style.display = 'flex';
        return;
    }

    placeholder.style.display = 'none';
    container.classList.remove('hidden');
    container.innerHTML = '';

    workflowSteps.forEach((step, index) => {
        // Add arrow before step (except first)
        if (index > 0) {
            const arrow = document.createElement('span');
            arrow.className = 'step-arrow';
            arrow.dataset.arrowIndex = index - 1; // Arrow between step[index-1] and step[index]
            arrow.innerHTML = '<i class="fas fa-arrow-right"></i>';
            container.appendChild(arrow);
        }

        const stepCard = document.createElement('div');
        stepCard.className = 'workflow-step-card';
        stepCard.dataset.stepIndex = index;
        stepCard.innerHTML = `
            <i class="fas ${step.icon}"></i>
            <span class="step-label">${step.label}</span>
            ${needsConfig(step.type) ? `<button class="config-btn" onclick="openConfigModal(${index})"><i class="fas fa-cog"></i></button>` : ''}
            <button class="remove-step" onclick="removeStep(${index})"><i class="fas fa-times"></i></button>
        `;
        container.appendChild(stepCard);
    });
}

function needsConfig(type) {
    return [
        'remove_password', 'resize_image', 'compress_pdf',
        'rotate_image', 'compress_image', 'convert_image', 'watermark_image',
        'csv_to_xlsx', 'xlsx_to_csv', 'ppt_to_images',
    ].includes(type);
}

function removeStep(index) {
    workflowSteps.splice(index, 1);
    renderWorkflowSteps();
}

function openConfigModal(index) {
    currentConfigStepIndex = index;
    const step = workflowSteps[index];
    const modal = document.getElementById('step-config-modal');
    const title = document.getElementById('config-modal-title');
    const body = document.getElementById('config-modal-body');

    title.textContent = `Configure: ${step.label}`;

    if (step.type === 'remove_password') {
        body.innerHTML = `
            <label>
                <span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">PDF Password</span>
                <input type="password" id="config-password" placeholder="Enter password" value="${step.config.password || ''}">
            </label>
        `;
    } else if (step.type === 'resize_image') {
        body.innerHTML = `
            <label>
                <span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Resize Percentage</span>
                <input type="number" id="config-percentage" placeholder="e.g., 50" value="${step.config.percentage || 50}" min="1" max="200">
            </label>
        `;
    } else if (step.type === 'compress_pdf') {
        const lvl = step.config.level || 'medium';
        body.innerHTML = `
            <label>
                <span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Compression Level</span>
                <select id="config-compress-level">
                    <option value="low" ${lvl === 'low' ? 'selected' : ''}>Low — Best Quality</option>
                    <option value="medium" ${lvl === 'medium' ? 'selected' : ''}>Medium — Balanced</option>
                    <option value="high" ${lvl === 'high' ? 'selected' : ''}>High — Smallest Size</option>
                </select>
            </label>
        `;
    } else if (step.type === 'rotate_image') {
        const a = step.config.angle ?? 90;
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Rotation angle</span>
            <select id="config-angle">
                <option value="90" ${a == 90 ? 'selected' : ''}>90°</option>
                <option value="180" ${a == 180 ? 'selected' : ''}>180°</option>
                <option value="270" ${a == 270 ? 'selected' : ''}>270°</option>
            </select></label>`;
    } else if (step.type === 'compress_image') {
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Quality (1-100)</span>
            <input type="number" id="config-quality" min="10" max="95" value="${step.config.quality ?? 70}"></label>`;
    } else if (step.type === 'convert_image') {
        const t = step.config.target_format || 'jpg';
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Target format</span>
            <select id="config-target-format">
                <option value="jpg" ${t === 'jpg' ? 'selected' : ''}>JPG</option>
                <option value="png" ${t === 'png' ? 'selected' : ''}>PNG</option>
                <option value="webp" ${t === 'webp' ? 'selected' : ''}>WebP</option>
            </select></label>
            <label><span style="display:block; margin:0.75rem 0 0.5rem; color:var(--text-muted)">Quality</span>
            <input type="number" id="config-quality" min="10" max="100" value="${step.config.quality ?? 90}"></label>`;
    } else if (step.type === 'watermark_image') {
        const pos = step.config.position || 'bottom-right';
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Text</span>
            <input type="text" id="config-wm-text" value="${step.config.text || ''}"></label>
            <label><span style="display:block; margin:0.75rem 0 0.5rem; color:var(--text-muted)">Position</span>
            <select id="config-wm-position">
                ${['top-left','top-right','center','bottom-left','bottom-right','diagonal']
                    .map(p => `<option value="${p}" ${p === pos ? 'selected' : ''}>${p}</option>`).join('')}
            </select></label>
            <label><span style="display:block; margin:0.75rem 0 0.5rem; color:var(--text-muted)">Opacity (0.05-1.0)</span>
            <input type="number" id="config-wm-opacity" min="0.05" max="1" step="0.05" value="${step.config.opacity ?? 0.4}"></label>`;
    } else if (step.type === 'csv_to_xlsx') {
        const d = step.config.delimiter || ',';
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Delimiter</span>
            <select id="config-delimiter">
                <option value="," ${d === ',' ? 'selected' : ''}>Comma</option>
                <option value=";" ${d === ';' ? 'selected' : ''}>Semicolon</option>
                <option value="\\t" ${d === '\\t' ? 'selected' : ''}>Tab</option>
                <option value="|" ${d === '|' ? 'selected' : ''}>Pipe</option>
            </select></label>`;
    } else if (step.type === 'xlsx_to_csv') {
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Sheet name (blank = first)</span>
            <input type="text" id="config-sheet" value="${step.config.sheet || ''}"></label>`;
    } else if (step.type === 'ppt_to_images') {
        const f = step.config.fmt || 'png';
        body.innerHTML = `
            <label><span style="display:block; margin-bottom:0.5rem; color:var(--text-muted)">Image format</span>
            <select id="config-fmt">
                <option value="png" ${f === 'png' ? 'selected' : ''}>PNG</option>
                <option value="jpg" ${f === 'jpg' ? 'selected' : ''}>JPG</option>
            </select></label>`;
    }

    modal.classList.remove('hidden');
}

function closeConfigModal() {
    document.getElementById('step-config-modal').classList.add('hidden');
    currentConfigStepIndex = null;
}

function saveStepConfig() {
    if (currentConfigStepIndex === null) return;

    const step = workflowSteps[currentConfigStepIndex];

    if (step.type === 'remove_password') {
        step.config.password = document.getElementById('config-password').value;
    } else if (step.type === 'resize_image') {
        step.config.percentage = parseInt(document.getElementById('config-percentage').value) || 50;
    } else if (step.type === 'compress_pdf') {
        step.config.level = document.getElementById('config-compress-level').value;
    } else if (step.type === 'rotate_image') {
        step.config.angle = parseInt(document.getElementById('config-angle').value) || 90;
    } else if (step.type === 'compress_image') {
        step.config.quality = parseInt(document.getElementById('config-quality').value) || 70;
    } else if (step.type === 'convert_image') {
        step.config.target_format = document.getElementById('config-target-format').value;
        step.config.quality = parseInt(document.getElementById('config-quality').value) || 90;
    } else if (step.type === 'watermark_image') {
        step.config.text = document.getElementById('config-wm-text').value;
        step.config.position = document.getElementById('config-wm-position').value;
        step.config.opacity = parseFloat(document.getElementById('config-wm-opacity').value) || 0.4;
    } else if (step.type === 'csv_to_xlsx') {
        step.config.delimiter = document.getElementById('config-delimiter').value;
    } else if (step.type === 'xlsx_to_csv') {
        step.config.sheet = document.getElementById('config-sheet').value;
    } else if (step.type === 'ppt_to_images') {
        step.config.fmt = document.getElementById('config-fmt').value;
    }

    closeConfigModal();
    renderWorkflowSteps();
}

async function runWorkflow() {
    if (!workflowFile) {
        alert('Please select an input file first.');
        return;
    }

    if (workflowSteps.length === 0) {
        alert('Please add at least one step to your workflow.');
        return;
    }

    // Validate required configs
    for (const step of workflowSteps) {
        if (step.type === 'remove_password' && !step.config.password) {
            alert(`Please configure the password for "${step.label}" step.`);
            return;
        }
    }

    const statusDisplay = document.getElementById('workflow-status-display');
    const statusText = document.getElementById('workflow-status-text');
    const resultDisplay = document.getElementById('workflow-result-display');

    statusDisplay.classList.remove('hidden');
    resultDisplay.classList.add('hidden');

    // Initialize all steps as pending
    setAllStepsPending();
    updateStatusText('Starting workflow...', 0, workflowSteps.length);

    const formData = new FormData();
    formData.append('file', workflowFile);
    formData.append('steps', JSON.stringify(workflowSteps.map(s => ({
        type: s.type,
        label: s.label,
        config: s.config
    }))));

    try {
        const response = await fetchWithAuth('/api/workflow/execute', {
            method: 'POST',
            body: formData
        });

        if (!response.ok && !response.headers.get('content-type')?.includes('text/event-stream')) {
            const data = await response.json();
            throw new Error(data.detail || 'Workflow execution failed');
        }

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE messages
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete message in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        console.log("Workflow Event:", data); // Debug log
                        handleWorkflowEvent(data, statusDisplay, resultDisplay);
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error:', error);
        statusDisplay.classList.add('hidden');
        clearStepStates();
        alert('Workflow error: ' + error.message);
    }
}

function handleWorkflowEvent(data, statusDisplay, resultDisplay) {
    switch (data.event) {
        case 'step_start':
            setStepProcessing(data.step);
            updateStatusText(`Processing: ${data.label}`, data.step + 1, data.total);
            break;

        case 'step_complete':
            setStepCompleted(data.step);
            break;

        case 'complete':
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            document.getElementById('workflow-result-message').textContent = `${data.message}: ${data.filename}`;
            updateDownloadLink(document.getElementById('workflow-download-link'), data.filename);
            // Keep completed states visible for a moment
            setTimeout(() => clearStepStates(), 3000);
            break;

        case 'error':
            statusDisplay.classList.add('hidden');
            clearStepStates();
            alert('Workflow error: ' + data.detail);
            break;
    }
}

function setAllStepsPending() {
    const cards = document.querySelectorAll('.workflow-step-card');
    const arrows = document.querySelectorAll('.step-arrow');

    cards.forEach(card => {
        card.classList.remove('processing', 'completed');
        card.classList.add('pending');
    });

    arrows.forEach(arrow => {
        arrow.classList.remove('processing', 'completed');
    });
}

function setStepProcessing(index) {
    const card = document.querySelector(`.workflow-step-card[data-step-index="${index}"]`);
    if (card) {
        card.classList.remove('pending', 'completed');
        card.classList.add('processing');
    }

    // Highlight arrow leading to this step
    if (index > 0) {
        const arrow = document.querySelector(`.step-arrow[data-arrow-index="${index - 1}"]`);
        if (arrow) {
            arrow.classList.add('processing');
        }
    }
}

function setStepCompleted(index) {
    const card = document.querySelector(`.workflow-step-card[data-step-index="${index}"]`);
    if (card) {
        card.classList.remove('pending', 'processing');
        card.classList.add('completed');
    }

    // Mark arrow as completed
    if (index > 0) {
        const arrow = document.querySelector(`.step-arrow[data-arrow-index="${index - 1}"]`);
        if (arrow) {
            arrow.classList.remove('processing');
            arrow.classList.add('completed');
        }
    }
}

function clearStepStates() {
    const cards = document.querySelectorAll('.workflow-step-card');
    const arrows = document.querySelectorAll('.step-arrow');

    cards.forEach(card => {
        card.classList.remove('pending', 'processing', 'completed');
    });

    arrows.forEach(arrow => {
        arrow.classList.remove('processing', 'completed');
    });
}

function updateStatusText(message, currentStep, totalSteps) {
    const statusText = document.getElementById('workflow-status-text');
    statusText.innerHTML = `
        <span>${message}</span>
        <span class="workflow-step-progress">Step ${currentStep} of ${totalSteps}</span>
    `;
}

// Reset workflow UI
function resetWorkflowUI() {
    workflowFile = null;
    workflowSteps = [];
    const fileInput = document.getElementById('workflow-file-input');
    if (fileInput) fileInput.value = '';
    const filenameDisplay = document.getElementById('workflow-filename-display');
    if (filenameDisplay) filenameDisplay.textContent = 'No file selected';
    const fileInfo = document.getElementById('workflow-file-info');
    if (fileInfo) fileInfo.classList.add('hidden');
    renderWorkflowSteps();
    document.getElementById('workflow-status-display')?.classList.add('hidden');
    document.getElementById('workflow-result-display')?.classList.add('hidden');
}

// Extend resetUI to include workflow reset
const originalResetUI = resetUI;
resetUI = function () {
    originalResetUI();
    resetWorkflowUI();
    selectedExcelFile = null;
    selectedExcelFiles = [];
    if (excelFileInput) { excelFileInput.value = ''; excelFileInput.multiple = false; }
    if (excelFilenameDisplay) excelFilenameDisplay.textContent = 'No file selected';
    document.getElementById('excel-file-info')?.classList.add('hidden');
    hideExcelActionAreas();
    document.getElementById('excel-status-display')?.classList.add('hidden');
    document.getElementById('excel-result-display')?.classList.add('hidden');

    selectedPptFile = null;
    selectedPptFiles = [];
    if (pptFileInput) { pptFileInput.value = ''; pptFileInput.multiple = false; }
    if (pptFilenameDisplay) pptFilenameDisplay.textContent = 'No file selected';
    document.getElementById('ppt-file-info')?.classList.add('hidden');
    hidePptActionAreas();
    document.getElementById('ppt-status-display')?.classList.add('hidden');
    document.getElementById('ppt-result-display')?.classList.add('hidden');
};

// === Image Page: new feature handlers (rotate, compress, convert format, watermark) ===

function showImageOptionPanel(id) {
    if (!selectedImageFile) { alert('Please select an image first.'); return false; }
    hideImageActionAreas();
    document.getElementById(id).classList.remove('hidden');
    return true;
}

document.getElementById('rotate-image-btn')?.addEventListener('click', () => {
    showImageOptionPanel('rotate-image-area');
});
document.getElementById('compress-image-btn')?.addEventListener('click', () => {
    showImageOptionPanel('compress-image-area');
});
document.getElementById('convert-format-btn')?.addEventListener('click', () => {
    showImageOptionPanel('convert-format-area');
});
document.getElementById('watermark-image-btn')?.addEventListener('click', () => {
    showImageOptionPanel('watermark-image-area');
});

const compressImgQ = document.getElementById('compress-image-quality');
if (compressImgQ) compressImgQ.addEventListener('input', e => {
    document.getElementById('compress-image-quality-value').textContent = e.target.value;
});
const convertFmtQ = document.getElementById('convert-format-quality');
if (convertFmtQ) convertFmtQ.addEventListener('input', e => {
    document.getElementById('convert-format-quality-value').textContent = e.target.value;
});
const wmImgOpacity = document.getElementById('watermark-image-opacity');
if (wmImgOpacity) wmImgOpacity.addEventListener('input', e => {
    document.getElementById('watermark-image-opacity-value').textContent = e.target.value;
});

document.getElementById('process-rotate-image-btn')?.addEventListener('click', () => {
    if (!selectedImageFile) { alert('Please select an image first.'); return; }
    const angle = document.getElementById('rotate-angle').value;
    const fd = new FormData();
    fd.append('file', selectedImageFile);
    fd.append('angle', angle);
    processImageAction('/api/image/rotate', `Rotating ${angle}°...`, fd);
});

document.getElementById('process-compress-image-btn')?.addEventListener('click', () => {
    if (!selectedImageFile) { alert('Please select an image first.'); return; }
    const quality = document.getElementById('compress-image-quality').value;
    const fd = new FormData();
    fd.append('file', selectedImageFile);
    fd.append('quality', quality);
    processImageAction('/api/image/compress', 'Compressing image...', fd);
});

document.getElementById('process-convert-format-btn')?.addEventListener('click', () => {
    if (!selectedImageFile) { alert('Please select an image first.'); return; }
    const target_format = document.getElementById('convert-target-format').value;
    const quality = document.getElementById('convert-format-quality').value;
    const fd = new FormData();
    fd.append('file', selectedImageFile);
    fd.append('target_format', target_format);
    fd.append('quality', quality);
    processImageAction('/api/image/convert', `Converting to ${target_format.toUpperCase()}...`, fd);
});

document.getElementById('process-watermark-image-btn')?.addEventListener('click', () => {
    if (!selectedImageFile) { alert('Please select an image first.'); return; }
    const text = document.getElementById('watermark-image-text').value.trim();
    if (!text) { alert('Please enter watermark text.'); return; }
    const position = document.getElementById('watermark-image-position').value;
    const opacity = document.getElementById('watermark-image-opacity').value;
    const color = document.getElementById('watermark-image-color').value;

    const fd = new FormData();
    fd.append('file', selectedImageFile);
    fd.append('text', text);
    fd.append('position', position);
    fd.append('opacity', opacity);
    fd.append('color', color);
    processImageAction('/api/image/watermark', 'Adding watermark...', fd);
});

// === Excel Page ===

let selectedExcelFile = null;
let selectedExcelFiles = [];

const excelDropZone = document.getElementById('excel-drop-zone');
const excelFileInput = document.getElementById('excel-file-input');
const excelFilenameDisplay = document.getElementById('excel-filename-display');
const excelFileInfo = document.getElementById('excel-file-info');

function handleExcelFiles(files) {
    if (excelFileInput.multiple) {
        const xlsxs = files.filter(f => f.name.toLowerCase().endsWith('.xlsx'));
        if (xlsxs.length === 0) { alert('Please select .xlsx files.'); return; }
        selectedExcelFiles = xlsxs;
        selectedExcelFile = xlsxs[0];
        excelFilenameDisplay.textContent = xlsxs.length === 1
            ? xlsxs[0].name
            : `${xlsxs.length} files: ${xlsxs.map(f => f.name).join(', ')}`;
    } else {
        selectedExcelFile = files[0];
        selectedExcelFiles = [files[0]];
        excelFilenameDisplay.textContent = files[0].name;
    }
    excelFileInfo.classList.remove('hidden');
    document.getElementById('excel-status-display').classList.add('hidden');
    document.getElementById('excel-result-display').classList.add('hidden');
}

if (excelDropZone) {
    excelDropZone.onclick = () => excelFileInput.click();
    excelFileInput.onchange = e => { if (e.target.files.length) handleExcelFiles(Array.from(e.target.files)); };
    excelDropZone.ondragover = e => { e.preventDefault(); excelDropZone.classList.add('drag-over'); };
    excelDropZone.ondragleave = () => excelDropZone.classList.remove('drag-over');
    excelDropZone.ondrop = e => {
        e.preventDefault();
        excelDropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) handleExcelFiles(Array.from(e.dataTransfer.files));
    };
}

function hideExcelActionAreas() {
    ['excel-to-pdf-area', 'csv-to-xlsx-area', 'xlsx-to-csv-area', 'merge-excel-area']
        .forEach(id => document.getElementById(id)?.classList.add('hidden'));
    document.getElementById('excel-result-display')?.classList.add('hidden');
}

function setExcelMergeMode(on) {
    if (excelFileInput) excelFileInput.multiple = !!on;
    if (!on) selectedExcelFiles = [];
}

document.getElementById('excel-to-pdf-btn')?.addEventListener('click', () => {
    setExcelMergeMode(false);
    if (!selectedExcelFile) { alert('Please select a file.'); return; }
    hideExcelActionAreas();
    document.getElementById('excel-to-pdf-area').classList.remove('hidden');
});
document.getElementById('csv-to-xlsx-btn')?.addEventListener('click', () => {
    setExcelMergeMode(false);
    if (!selectedExcelFile) { alert('Please select a CSV file.'); return; }
    hideExcelActionAreas();
    document.getElementById('csv-to-xlsx-area').classList.remove('hidden');
});
document.getElementById('xlsx-to-csv-btn')?.addEventListener('click', () => {
    setExcelMergeMode(false);
    if (!selectedExcelFile) { alert('Please select a file.'); return; }
    hideExcelActionAreas();
    document.getElementById('xlsx-to-csv-area').classList.remove('hidden');
});
document.getElementById('merge-excel-btn')?.addEventListener('click', () => {
    setExcelMergeMode(true);
    hideExcelActionAreas();
    document.getElementById('merge-excel-area').classList.remove('hidden');
});

async function processExcelAction(url, text, formData) {
    const statusDisplay = document.getElementById('excel-status-display');
    const statusText = document.getElementById('excel-status-text');
    const resultDisplay = document.getElementById('excel-result-display');

    statusDisplay.classList.remove('hidden');
    statusText.textContent = text;
    resultDisplay.classList.add('hidden');

    try {
        const response = await fetchWithAuth(url, { method: 'POST', body: formData });
        if (response.ok) {
            const data = await response.json();
            resultDisplay.classList.remove('hidden');
            document.getElementById('excel-result-message').textContent = `${data.message}: ${data.filename}`;
            updateDownloadLink(document.getElementById('excel-download-link'), data.filename);
        } else {
            const data = await response.json().catch(() => ({ detail: 'Failed' }));
            alert('Error: ' + (data.detail || 'Failed'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        statusDisplay.classList.add('hidden');
    }
}

document.getElementById('process-excel-to-pdf-btn')?.addEventListener('click', () => {
    if (!selectedExcelFile) { alert('Please select a file.'); return; }
    const fd = new FormData();
    fd.append('file', selectedExcelFile);
    processExcelAction('/api/excel/to-pdf', 'Converting Excel to PDF...', fd);
});
document.getElementById('process-csv-to-xlsx-btn')?.addEventListener('click', () => {
    if (!selectedExcelFile) { alert('Please select a CSV file.'); return; }
    const fd = new FormData();
    fd.append('file', selectedExcelFile);
    fd.append('delimiter', document.getElementById('csv-delimiter').value);
    processExcelAction('/api/excel/csv-to-xlsx', 'Converting CSV to XLSX...', fd);
});
document.getElementById('process-xlsx-to-csv-btn')?.addEventListener('click', () => {
    if (!selectedExcelFile) { alert('Please select an XLSX file.'); return; }
    const fd = new FormData();
    fd.append('file', selectedExcelFile);
    const sheet = document.getElementById('xlsx-sheet-name').value.trim();
    if (sheet) fd.append('sheet', sheet);
    processExcelAction('/api/excel/xlsx-to-csv', 'Exporting CSV...', fd);
});
document.getElementById('process-merge-excel-btn')?.addEventListener('click', () => {
    if (!selectedExcelFiles || selectedExcelFiles.length < 2) {
        alert('Please select at least two .xlsx files.'); return;
    }
    const fd = new FormData();
    selectedExcelFiles.forEach(f => fd.append('files', f));
    processExcelAction('/api/excel/merge', `Merging ${selectedExcelFiles.length} workbooks...`, fd);
});

// === PPT Page ===

let selectedPptFile = null;
let selectedPptFiles = [];

const pptDropZone = document.getElementById('ppt-drop-zone');
const pptFileInput = document.getElementById('ppt-file-input');
const pptFilenameDisplay = document.getElementById('ppt-filename-display');
const pptFileInfo = document.getElementById('ppt-file-info');

function handlePptFiles(files) {
    if (pptFileInput.multiple) {
        const pptxs = files.filter(f => f.name.toLowerCase().endsWith('.pptx'));
        if (pptxs.length === 0) { alert('Please select .pptx files.'); return; }
        selectedPptFiles = pptxs;
        selectedPptFile = pptxs[0];
        pptFilenameDisplay.textContent = pptxs.length === 1
            ? pptxs[0].name
            : `${pptxs.length} files: ${pptxs.map(f => f.name).join(', ')}`;
    } else {
        if (!files[0].name.toLowerCase().endsWith('.pptx')) {
            alert('Please select a .pptx file.'); return;
        }
        selectedPptFile = files[0];
        selectedPptFiles = [files[0]];
        pptFilenameDisplay.textContent = files[0].name;
    }
    pptFileInfo.classList.remove('hidden');
    document.getElementById('ppt-status-display').classList.add('hidden');
    document.getElementById('ppt-result-display').classList.add('hidden');
}

if (pptDropZone) {
    pptDropZone.onclick = () => pptFileInput.click();
    pptFileInput.onchange = e => { if (e.target.files.length) handlePptFiles(Array.from(e.target.files)); };
    pptDropZone.ondragover = e => { e.preventDefault(); pptDropZone.classList.add('drag-over'); };
    pptDropZone.ondragleave = () => pptDropZone.classList.remove('drag-over');
    pptDropZone.ondrop = e => {
        e.preventDefault();
        pptDropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) handlePptFiles(Array.from(e.dataTransfer.files));
    };
}

function hidePptActionAreas() {
    ['ppt-to-pdf-area', 'ppt-to-images-area', 'merge-ppt-area']
        .forEach(id => document.getElementById(id)?.classList.add('hidden'));
    document.getElementById('ppt-result-display')?.classList.add('hidden');
}

function setPptMergeMode(on) {
    if (pptFileInput) pptFileInput.multiple = !!on;
    if (!on) selectedPptFiles = [];
}

document.getElementById('ppt-to-pdf-btn')?.addEventListener('click', () => {
    setPptMergeMode(false);
    if (!selectedPptFile) { alert('Please select a PPTX file.'); return; }
    hidePptActionAreas();
    document.getElementById('ppt-to-pdf-area').classList.remove('hidden');
});
document.getElementById('ppt-to-images-btn')?.addEventListener('click', () => {
    setPptMergeMode(false);
    if (!selectedPptFile) { alert('Please select a PPTX file.'); return; }
    hidePptActionAreas();
    document.getElementById('ppt-to-images-area').classList.remove('hidden');
});
document.getElementById('merge-ppt-btn')?.addEventListener('click', () => {
    setPptMergeMode(true);
    hidePptActionAreas();
    document.getElementById('merge-ppt-area').classList.remove('hidden');
});

async function processPptAction(url, text, formData) {
    const statusDisplay = document.getElementById('ppt-status-display');
    const statusText = document.getElementById('ppt-status-text');
    const resultDisplay = document.getElementById('ppt-result-display');

    statusDisplay.classList.remove('hidden');
    statusText.textContent = text;
    resultDisplay.classList.add('hidden');

    try {
        const response = await fetchWithAuth(url, { method: 'POST', body: formData });
        if (response.ok) {
            const data = await response.json();
            resultDisplay.classList.remove('hidden');
            document.getElementById('ppt-result-message').textContent = `${data.message}: ${data.filename}`;
            updateDownloadLink(document.getElementById('ppt-download-link'), data.filename);
        } else {
            const data = await response.json().catch(() => ({ detail: 'Failed' }));
            alert('Error: ' + (data.detail || 'Failed'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        statusDisplay.classList.add('hidden');
    }
}

document.getElementById('process-ppt-to-pdf-btn')?.addEventListener('click', () => {
    if (!selectedPptFile) { alert('Please select a PPTX file.'); return; }
    const fd = new FormData();
    fd.append('file', selectedPptFile);
    processPptAction('/api/ppt/to-pdf', 'Converting PPT to PDF...', fd);
});
document.getElementById('process-ppt-to-images-btn')?.addEventListener('click', () => {
    if (!selectedPptFile) { alert('Please select a PPTX file.'); return; }
    const fd = new FormData();
    fd.append('file', selectedPptFile);
    fd.append('fmt', document.getElementById('ppt-images-format').value);
    processPptAction('/api/ppt/to-images', 'Rendering slides...', fd);
});
document.getElementById('process-merge-ppt-btn')?.addEventListener('click', () => {
    if (!selectedPptFiles || selectedPptFiles.length < 2) {
        alert('Please select at least two .pptx files.'); return;
    }
    const fd = new FormData();
    selectedPptFiles.forEach(f => fd.append('files', f));
    processPptAction('/api/ppt/merge', `Merging ${selectedPptFiles.length} presentations...`, fd);
});

// Global Accessibility: Handle keyboard activation for role="button"
document.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute('role') === 'button') {
        e.preventDefault();
        e.target.click();
    }
});
