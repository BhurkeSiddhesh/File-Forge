let selectedFile = null;
let selectedImageFile = null;
let currentTool = null;

// Navigation
function showDrillDown(tool) {
    currentTool = tool;
    let pageId;
    if (tool === 'pdf') pageId = 'pdf-page';
    else if (tool === 'image') pageId = 'image-page';
    else if (tool === 'workflow') pageId = 'workflow-page';
    else return;

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
    let pageId;
    if (currentTool === 'pdf') pageId = 'pdf-page';
    else if (currentTool === 'image') pageId = 'image-page';
    else if (currentTool === 'workflow') pageId = 'workflow-page';
    else pageId = 'pdf-page';

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

            const response = await fetch('/api/image/heic-to-jpeg', {
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
            image.src = `/api/download/${data.filename}`;

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
        const response = await fetch('/api/image/resize', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            resultMessage.innerText = `${data.message}: ${data.filename}`;
            downloadLink.href = `/api/download/${data.filename}`;
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
        const response = await fetch('/api/image/crop', {
            method: 'POST',
            body: formData
        });

        const respData = await response.json();

        if (response.ok) {
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            resultMessage.innerText = `${respData.message}: ${respData.filename}`;
            downloadLink.href = `/api/download/${respData.filename}`;
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
    }

    workflowSteps.push(step);
    renderWorkflowSteps();

    // If step needs config, open modal
    if (type === 'remove_password' || type === 'resize_image') {
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
            arrow.innerHTML = '<i class="fas fa-arrow-right"></i>';
            container.appendChild(arrow);
        }

        const stepCard = document.createElement('div');
        stepCard.className = 'workflow-step-card';
        stepCard.innerHTML = `
            <i class="fas ${step.icon}"></i>
            <span class="step-label">${step.label}</span>
            ${needsConfig(step.type) ? `<button class="config-btn" onclick="openConfigModal(${index})" aria-label="Configure ${step.label}"><i class="fas fa-cog"></i></button>` : ''}
            <button class="remove-step" onclick="removeStep(${index})" aria-label="Remove ${step.label}"><i class="fas fa-times"></i></button>
        `;
        container.appendChild(stepCard);
    });
}

function needsConfig(type) {
    return ['remove_password', 'resize_image'].includes(type);
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
    statusText.textContent = 'Processing workflow...';

    const formData = new FormData();
    formData.append('file', workflowFile);
    formData.append('steps', JSON.stringify(workflowSteps.map(s => ({
        type: s.type,
        config: s.config
    }))));

    try {
        const response = await fetch('/api/workflow/execute', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            statusDisplay.classList.add('hidden');
            resultDisplay.classList.remove('hidden');
            document.getElementById('workflow-result-message').textContent = `${data.message}: ${data.filename}`;
            document.getElementById('workflow-download-link').href = `/api/download/${data.filename}`;
        } else {
            throw new Error(data.detail || 'Workflow execution failed');
        }
    } catch (error) {
        console.error('Error:', error);
        statusDisplay.classList.add('hidden');
        alert('Workflow error: ' + error.message);
    }
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
};

// === Accessibility Helpers ===

function setupKeyboardAccess() {
    const buttons = document.querySelectorAll('[role="button"]');
    buttons.forEach(btn => {
        btn.removeEventListener('keydown', handleButtonKeydown);
        btn.addEventListener('keydown', handleButtonKeydown);
    });
}

function handleButtonKeydown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.target.click();
    }
}

// Initialize accessibility features when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    setupKeyboardAccess();
});
