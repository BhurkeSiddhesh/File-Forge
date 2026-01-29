let selectedFile = null;
let selectedImageFile = null;
let currentTool = null;

// Navigation
function showDrillDown(tool) {
    currentTool = tool;
    const pageId = tool === 'pdf' ? 'pdf-page' : 'image-page';

    document.getElementById('home-page').classList.remove('active');
    setTimeout(() => {
        document.getElementById('home-page').style.display = 'none';
        document.getElementById(pageId).style.display = 'block';
        setTimeout(() => {
            document.getElementById(pageId).classList.add('active');
        }, 50);
    }, 500);
}

function showHome() {
    const pageId = currentTool === 'pdf' ? 'pdf-page' : 'image-page';
    document.getElementById(pageId).classList.remove('active');
    resetUI();
    setTimeout(() => {
        document.getElementById(pageId).style.display = 'none';
        document.getElementById('home-page').style.display = 'block';
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
        handleFile(e.target.files[0]);
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
        handleFile(e.dataTransfer.files[0]);
    }
};

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
    document.getElementById('result-display').classList.add('hidden');
    document.getElementById('password-input-area').classList.add('hidden');
}

// Actions
document.getElementById('remove-password-btn').onclick = () => {
    if (!selectedFile) {
        alert('Please select a file first.');
        return;
    }
    document.getElementById('password-input-area').classList.remove('hidden');
    document.getElementById('convert-password-area').classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');
};

document.getElementById('convert-word-btn').onclick = () => {
    if (!selectedFile) {
        alert('Please select a file first.');
        return;
    }
    // Show the optional password input for conversion
    document.getElementById('convert-password-area').classList.remove('hidden');
    document.getElementById('password-input-area').classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');
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
        const response = await fetch(url, {
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

function showResult(filename, message) {
    const resultDisplay = document.getElementById('result-display');
    const resultMessage = document.getElementById('result-message');
    const downloadLink = document.getElementById('download-link');

    resultDisplay.classList.remove('hidden');
    resultMessage.textContent = message + ': ' + filename;
    downloadLink.href = `/api/download/${filename}`;
}

function resetUI() {
    selectedFile = null;
    selectedImageFile = null;
    currentTool = null;
    fileInput.value = '';
    filenameDisplay.textContent = 'No file selected';
    fileInfo.classList.add('hidden');
    document.getElementById('password-input-area').classList.add('hidden');
    document.getElementById('convert-password-area').classList.add('hidden');
    document.getElementById('status-display').classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');

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
    const validTypes = ['image/heic', 'image/heif'];
    const validExts = ['.heic', '.heif'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
        alert('Please select a HEIC or HEIF file.');
        return;
    }
    selectedImageFile = file;
    imageFilenameDisplay.textContent = file.name;
    imageFileInfo.classList.remove('hidden');

    // Reset displays
    document.getElementById('image-status-display').classList.add('hidden');
    document.getElementById('image-result-display').classList.add('hidden');
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
        const response = await fetch(url, {
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
    downloadLink.href = `/api/download/${filename}`;
}
