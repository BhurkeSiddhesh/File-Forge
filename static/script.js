let selectedFile = null;
let currentTool = null;

// Navigation
function showDrillDown(tool) {
    currentTool = tool;
    document.getElementById('home-page').classList.remove('active');
    setTimeout(() => {
        document.getElementById('home-page').style.display = 'none';
        document.getElementById('pdf-page').style.display = 'block';
        setTimeout(() => {
            document.getElementById('pdf-page').classList.add('active');
        }, 50);
    }, 500);
}

function showHome() {
    document.getElementById('pdf-page').classList.remove('active');
    resetUI();
    setTimeout(() => {
        document.getElementById('pdf-page').style.display = 'none';
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
    document.getElementById('result-display').classList.add('hidden');
};

document.getElementById('convert-word-btn').onclick = async () => {
    if (!selectedFile) {
        alert('Please select a file first.');
        return;
    }

    const useAI = document.getElementById('ai-mode-toggle').checked;
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('use_ai', useAI);

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

        const data = await response.json();

        if (response.ok) {
            showResult(data.filename, data.message);
        } else {
            alert('Error: ' + data.detail);
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
    currentTool = null;
    fileInput.value = '';
    filenameDisplay.textContent = 'No file selected';
    fileInfo.classList.add('hidden');
    document.getElementById('password-input-area').classList.add('hidden');
    document.getElementById('status-display').classList.add('hidden');
    document.getElementById('result-display').classList.add('hidden');
}
