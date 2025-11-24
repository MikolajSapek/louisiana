const form = document.getElementById('route-form');
const messagesBox = document.getElementById('messages');
const preview = document.getElementById('map-preview');
const downloadLink = document.getElementById('download-link');
const downloadButton = document.getElementById('download-button');
const spinner = document.getElementById('spinner');
const fontSelect = document.getElementById('font');
const fontCustomContainer = document.getElementById('font_custom_container');
const fontCustomInput = document.getElementById('font_custom');
const textFontSelect = document.getElementById('text_font');
const textFontCustomContainer = document.getElementById('text_font_custom_container');
const textFontCustomInput = document.getElementById('text_font_custom');
const signatureEnabledInput = document.getElementById('signature_enabled');
const signatureOptions = document.getElementById('signature_options');
const signaturePathInput = document.getElementById('signature_path');
const signaturePositionSelect = document.getElementById('signature_position');
const signatureScaleInput = document.getElementById('signature_scale');
const modalLabelOverlay = document.getElementById('modal-label-overlay');
const applyLabelsButton = document.getElementById('apply-labels-button');

let lastPayload = null;
let currentMapInfo = null;
let currentLabelData = [];
let currentBounds = null;
let currentStyle = null;
let pendingOffsets = {};
let currentFigure = null;
let currentAxes = null;
let currentAxesBounds = null;
let hiddenLabels = new Set();

function showMessage(text, type = 'warning') {
    const div = document.createElement('div');
    div.className = `alert alert-${type}`;
    div.textContent = text;
    messagesBox.appendChild(div);
}

function clearMessages() {
    messagesBox.innerHTML = '';
}

function clonePayload(payload) {
    try {
        return structuredClone(payload);
    } catch (_err) {
        return JSON.parse(JSON.stringify(payload));
    }
}

async function submitForm(event) {
    event.preventDefault();
    clearMessages();
    preview.style.display = 'none';
    if (downloadButton) downloadButton.style.display = 'none';
    spinner.hidden = false;

    const formData = new FormData(form);

    const selectedFont = formData.get('font');
    let fontValue;
    if (selectedFont === 'custom') {
        fontValue = formData.get('font_custom') || undefined;
    } else {
        fontValue = selectedFont || undefined;
    }

    const selectedTextFont = formData.get('text_font');
    let textFontValue;
    if (selectedTextFont === 'custom') {
        textFontValue = formData.get('text_font_custom') || undefined;
    } else {
        textFontValue = selectedTextFont || undefined;
    }

    const payload = {
        cities: formData.get('cities') || '',
        background: formData.get('background') || undefined,
        font: fontValue,
        font_color: formData.get('font_color') || undefined,
        show_borders: formData.get('show_borders') === 'on',
        paper_format: formData.get('paper_format') || undefined,
        dpi: formData.get('dpi') || undefined,
        line_style: formData.get('line_style') || undefined,
        line_color: formData.get('line_color') || undefined,
        line_width: formData.get('line_width') || undefined,
        point_style: formData.get('point_style') || undefined,
        point_color: formData.get('point_color') || undefined,
        point_size: formData.get('point_size') || undefined,
        title: formData.get('title') || undefined,
        footer_left: formData.get('footer_left') || undefined,
        footer_right: formData.get('footer_right') || undefined,
        text_font: textFontValue,
        signature_enabled: signatureEnabledInput ? signatureEnabledInput.checked : undefined,
        signature_path:
            signatureEnabledInput && signatureEnabledInput.checked
                ? (signaturePathInput && signaturePathInput.value
                    ? signaturePathInput.value
                    : 'static/signature/signature.png')
                : undefined,
        signature_position: signaturePositionSelect ? signaturePositionSelect.value : undefined,
        signature_scale: signatureScaleInput && signatureScaleInput.value ? signatureScaleInput.value : undefined,
        merge_bidirectional_routes: formData.get('merge_bidirectional_routes') === 'on',
    };

    lastPayload = clonePayload(payload);

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        spinner.hidden = true;

        if (!response.ok || !data.success) {
            showMessage(data.error || 'Nie udało się wygenerować mapy.', 'error');
            if (modalLabelOverlay) modalLabelOverlay.innerHTML = '';
            return;
        }

        showMessage('Mapa została wygenerowana!', 'success');
        // Clear hidden labels when generating a new map
        hiddenLabels.clear();
        handleMapResponse(data);
    } catch (error) {
        spinner.hidden = true;
        console.error(error);
        showMessage('Wystąpił nieoczekiwany błąd podczas generowania mapy.', 'error');
        if (modalLabelOverlay) modalLabelOverlay.innerHTML = '';
    }
}

form.addEventListener('submit', submitForm);

function toggleCustomFont(selectEl, containerEl, inputEl) {
    if (!selectEl || !containerEl || !inputEl) {
        return;
    }
    const shouldShow = selectEl.value === 'custom';
    containerEl.hidden = !shouldShow;
    if (!shouldShow) {
        inputEl.value = '';
    }
}

if (fontSelect) {
    fontSelect.addEventListener('change', () =>
        toggleCustomFont(fontSelect, fontCustomContainer, fontCustomInput)
    );
    toggleCustomFont(fontSelect, fontCustomContainer, fontCustomInput);
}

if (textFontSelect) {
    textFontSelect.addEventListener('change', () =>
        toggleCustomFont(textFontSelect, textFontCustomContainer, textFontCustomInput)
    );
    toggleCustomFont(textFontSelect, textFontCustomContainer, textFontCustomInput);
}

if (signatureEnabledInput && signatureOptions) {
    const syncSignatureOptions = () => {
        signatureOptions.hidden = !signatureEnabledInput.checked;
    };
    signatureEnabledInput.addEventListener('change', syncSignatureOptions);
    syncSignatureOptions();
}

const modalOverlay = document.getElementById('modal-overlay');
const modalImage = document.getElementById('modal-image');
const modalCloseButton = document.getElementById('modal-close');

function openModal() {
    if (!preview || !preview.src || preview.style.display === 'none') {
        return;
    }
    modalImage.src = preview.src;
    modalImage.alt = preview.alt || 'Podgląd plakatu';
    if (applyLabelsButton) {
        applyLabelsButton.style.display = 'inline-flex';
    }
    if (downloadButton) {
        downloadButton.style.display = 'none'; // Hidden until "Zastosuj etykiety"
    }
    modalOverlay.hidden = false;
    document.body.style.overflow = 'hidden';
    modalImage.onload = () => {
        renderLabelOverlay();
    };
    if (modalImage.complete && modalImage.naturalWidth) {
        renderLabelOverlay();
    }
}

function closeModal() {
    modalOverlay.hidden = true;
    modalImage.src = '';
    if (modalLabelOverlay) {
        modalLabelOverlay.hidden = true;
        modalLabelOverlay.innerHTML = '';
    }
    document.body.style.overflow = '';
}

if (modalOverlay) {
    modalOverlay.hidden = true;
}

if (preview) {
    preview.addEventListener('click', () => {
        if (preview.style.display !== 'none' && preview.src) {
            openModal();
        }
    });
}

if (modalCloseButton) {
    modalCloseButton.addEventListener('click', closeModal);
}

if (modalOverlay) {
    modalOverlay.addEventListener('click', (event) => {
        if (event.target === modalOverlay) {
            closeModal();
        }
    });
}

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modalOverlay.hidden) {
        closeModal();
    }
});

if (preview) {
    preview.addEventListener('load', () => {
        // no inline overlay; editing happens in modal
    });
}

if (applyLabelsButton) {
    applyLabelsButton.addEventListener('click', async () => {
        if (!lastPayload) {
            showMessage('Najpierw wygeneruj mapę, zanim zapiszesz etykiety.', 'warning');
            return;
        }
        const mapUrl = await applyManualAdjustments(false);
        if (mapUrl) {
            showMessage('Zapisano przesunięcia etykiet.', 'success');
        }
    });
}

window.addEventListener('resize', () => {
    renderLabelOverlay();
});

// Old downloadLink code removed - now using downloadButton

function handleMapResponse(data) {
    const warnings = data.warnings || [];
    warnings.forEach((message) => showMessage(message, 'warning'));

    currentMapInfo = data.map || null;
    currentStyle = currentMapInfo?.style || null;
    currentFigure = currentMapInfo?.figure || null;
    currentAxes = currentMapInfo?.axes || null;
    currentAxesBounds = null;
    currentLabelData = (currentMapInfo?.labels || []).map((entry) => {
        const anchorLon = Number(entry.anchor_lon ?? 0);
        const anchorLat = Number(entry.anchor_lat ?? 0);
        const dx = Number(entry.dx ?? 0);
        const dy = Number(entry.dy ?? 0);
        return {
            name: entry.name,
            anchor_lon: anchorLon,
            anchor_lat: anchorLat,
            dx,
            dy,
            locked: Boolean(entry.locked),
        };
    });
    currentBounds = currentMapInfo?.bounds
        ? {
            lon_min: Number(currentMapInfo.bounds.lon_min ?? 0),
            lon_max: Number(currentMapInfo.bounds.lon_max ?? 0),
            lat_min: Number(currentMapInfo.bounds.lat_min ?? 0),
            lat_max: Number(currentMapInfo.bounds.lat_max ?? 0),
        }
        : null;

    pendingOffsets = {};
    currentLabelData.forEach((label) => {
        pendingOffsets[label.name] = {
            lon: label.anchor_lon + label.dx,
            lat: label.anchor_lat + label.dy,
        };
    });

    if (currentMapInfo?.mapUrl) {
        const finalUrl = updatePreviewImage(currentMapInfo.mapUrl);
        if (!modalOverlay.hidden && finalUrl) {
            modalImage.onload = () => {
                renderLabelOverlay();
            };
            modalImage.src = finalUrl;
        }
        renderLabelOverlay();
    }
}

// Re-enable label editing overlay
function renderLabelOverlay() {
    if (!modalLabelOverlay || !currentLabelData.length || !modalImage.naturalWidth) {
        if (modalLabelOverlay) {
            modalLabelOverlay.hidden = true;
            modalLabelOverlay.innerHTML = '';
        }
        return;
    }

    modalLabelOverlay.innerHTML = '';

    // Overlay must match the displayed image size and position
    // Use offsetLeft/offsetTop for position relative to parent (.modal-map-wrapper)
    const width = modalImage.naturalWidth;
    const height = modalImage.naturalHeight;
    
    modalLabelOverlay.style.width = `${modalImage.clientWidth || width}px`;
    modalLabelOverlay.style.height = `${modalImage.clientHeight || height}px`;
    modalLabelOverlay.style.position = 'absolute';
    modalLabelOverlay.style.left = `${modalImage.offsetLeft}px`;
    modalLabelOverlay.style.top = `${modalImage.offsetTop}px`;

    const lonMin = Number(currentBounds?.lon_min ?? 0);
    const lonMax = Number(currentBounds?.lon_max ?? 1);
    const latMin = Number(currentBounds?.lat_min ?? 0);
    const latMax = Number(currentBounds?.lat_max ?? 1);
    const lonSpan = Math.max(lonMax - lonMin, 1e-9);
    const latSpan = Math.max(latMax - latMin, 1e-9);

    // Get figure and axes info for precise coordinate mapping
    const fig = currentMapInfo?.figure;
    const axes = currentMapInfo?.axes;
    const figWidth = Number(fig?.width_px || width);
    const figHeight = Number(fig?.height_px || height);
    const axX0 = Number(axes?.x0 || 0);
    const axY0 = Number(axes?.y0 || 0);
    const axWidth = Number(axes?.width || figWidth);
    const axHeight = Number(axes?.height || figHeight);
    
    // Scale from figure pixels to displayed image pixels
    const scaleX = width / figWidth;
    const scaleY = height / figHeight;

    const labelFontPxBase = Number(currentStyle?.label_font_size_px ?? 24);
    const labelFontFamily = currentStyle?.font_family || 'Helvetica, Arial, sans-serif';
    const labelFontColor = currentStyle?.font_color || '#ffffff';
    const backgroundColor = currentMapInfo?.style?.background_color || currentMapInfo?.background_color || '#0a3dbb';

    function hideLabel(item) {
        item.style.color = backgroundColor;
        item.style.opacity = '0';
        item.style.pointerEvents = 'none';
    }

    currentLabelData.forEach((label) => {
        const isHidden = hiddenLabels.has(label.name);

        const item = document.createElement('div');
        item.className = 'label-overlay-item';
        item.textContent = label.name;
        item.dataset.city = label.name;
        item.dataset.anchorLon = label.anchor_lon;
        item.dataset.anchorLat = label.anchor_lat;
        item.dataset.defaultLon = label.position_lon;
        item.dataset.defaultLat = label.position_lat;
        item.title = label.name;

        const position =
            pendingOffsets[label.name] || {
                lon: label.anchor_lon + label.dx,
                lat: label.anchor_lat + label.dy,
            };

        const xRel = (position.lon - lonMin) / lonSpan;
        const yRel = (position.lat - latMin) / latSpan;
        const xFig = axX0 + xRel * axWidth;
        const yFig = axY0 + yRel * axHeight;
        const anchorX = (xFig / figWidth) * width;
        const anchorY = (1 - (yFig / figHeight)) * height;

        const displayWidth = modalImage.clientWidth || width;
        const displayHeight = modalImage.clientHeight || height;
        const scaleXDisplay = displayWidth / width;
        const scaleYDisplay = displayHeight / height;
        item.style.left = `${anchorX * scaleXDisplay}px`;
        item.style.top = `${anchorY * scaleYDisplay}px`;
        item.style.fontSize = `${labelFontPxBase * scaleYDisplay}px`;
        item.style.fontFamily = labelFontFamily;
        item.style.color = labelFontColor;

        if (isHidden) {
            hideLabel(item);
        }

        // Add delete button (X) that appears on hover
        const deleteButton = document.createElement('button');
        deleteButton.className = 'label-delete-button';
        deleteButton.textContent = '×';
        deleteButton.title = 'Ukryj etykietę';
        deleteButton.style.cssText = `
            position: absolute;
            top: -8px;
            right: -8px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: rgba(255, 77, 77, 0.9);
            color: white;
            border: none;
            font-size: 16px;
            line-height: 1;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            pointer-events: auto;
        `;
        deleteButton.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            hiddenLabels.add(label.name);
            hideLabel(item);
            deleteButton.style.display = 'none';
        });

        item.addEventListener('mouseenter', () => {
            if (!hiddenLabels.has(label.name)) {
                deleteButton.style.display = 'flex';
            }
        });
        item.addEventListener('mouseleave', () => {
            if (!hiddenLabels.has(label.name)) {
                deleteButton.style.display = 'none';
            }
        });

        item.appendChild(deleteButton);
        makeDraggable(item);
        modalLabelOverlay.appendChild(item);
    });

    modalLabelOverlay.hidden = false;
}

if (applyLabelsButton) {
    applyLabelsButton.style.display = 'inline-flex';
}

// Update preview image
function updatePreviewImage(mapUrl) {
    if (!mapUrl) {
        preview.style.display = 'none';
        renderLabelOverlay();
        return null;
    }

    const cacheBuster = `?_=${Date.now()}`;
    const finalUrl = `${mapUrl}${cacheBuster}`;
    preview.src = finalUrl;
    preview.style.display = 'block';

    return finalUrl;
}

function makeDraggable(element) {
    element.addEventListener('pointerdown', (event) => {
        // Ignore clicks on buttons within the draggable element
        if (event.target.tagName === 'BUTTON' || event.target.closest('button')) {
            return;
        }
        event.preventDefault();
        element.setPointerCapture(event.pointerId);
        element.classList.add('dragging');

        const overlayRect = modalLabelOverlay.getBoundingClientRect();
        const elementRect = element.getBoundingClientRect();
        const startX = event.clientX;
        const startY = event.clientY;
        const startAnchorX = elementRect.left + elementRect.width / 2 - overlayRect.left;
        const startAnchorY = elementRect.bottom - overlayRect.top;

        const onMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            let newAnchorX = startAnchorX + deltaX;
            let newAnchorY = startAnchorY + deltaY;

            newAnchorX = Math.max(0, Math.min(newAnchorX, overlayRect.width));
            newAnchorY = Math.max(0, Math.min(newAnchorY, overlayRect.height));

            element.style.left = `${newAnchorX}px`;
            element.style.top = `${newAnchorY}px`;
        };

        const onUp = () => {
            element.releasePointerCapture(event.pointerId);
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            element.classList.remove('dragging');
            updatePendingOffset(element);
        };

        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
    });
}

function updatePendingOffset(element) {
    const overlayRect = modalLabelOverlay.getBoundingClientRect();
    const rect = element.getBoundingClientRect();
    const city = element.dataset.city;
    const anchorX = rect.left + rect.width / 2 - overlayRect.left;
    const anchorY = rect.bottom - overlayRect.top;
    
    // Get figure and axes info
    const width = modalImage.clientWidth || modalImage.naturalWidth;
    const height = modalImage.clientHeight || modalImage.naturalHeight;
    const fig = currentMapInfo?.figure;
    const axes = currentMapInfo?.axes;
    const figWidth = Number(fig?.width_px || width);
    const figHeight = Number(fig?.height_px || height);
    const axX0 = Number(axes?.x0 || 0);
    const axY0 = Number(axes?.y0 || 0);
    const axWidth = Number(axes?.width || figWidth);
    const axHeight = Number(axes?.height || figHeight);
    const scaleX = width / figWidth;
    const scaleY = height / figHeight;
    
    const lonMin = Number(currentBounds?.lon_min ?? 0);
    const lonMax = Number(currentBounds?.lon_max ?? 1);
    const latMin = Number(currentBounds?.lat_min ?? 0);
    const latMax = Number(currentBounds?.lat_max ?? 1);
    const lonSpan = Math.max(lonMax - lonMin, 1e-9);
    const latSpan = Math.max(latMax - latMin, 1e-9);

    // Convert display pixels back to figure pixels, then to axes relative, then to lon/lat
    const xFig = anchorX / scaleX;
    const yFig = figHeight - (anchorY / scaleY); // Y axis flipped
    const xRel = (xFig - axX0) / axWidth;
    const yRel = (yFig - axY0) / axHeight;
    const lon = lonMin + xRel * lonSpan;
    const lat = latMin + yRel * latSpan;

    const defaultLon = parseFloat(element.dataset.defaultLon || `${lon}`);
    const defaultLat = parseFloat(element.dataset.defaultLat || `${lat}`);
    const tolerance = 0.0005;

    if (
        Math.abs(lon - defaultLon) < tolerance &&
        Math.abs(lat - defaultLat) < tolerance
    ) {
        delete pendingOffsets[city];
    } else {
        pendingOffsets[city] = { lon, lat };
    }
}

async function applyManualAdjustments(triggerDownload = false) {
    if (!lastPayload || !currentBounds || !currentLabelData.length) {
        return currentMapInfo?.mapUrl || null;
    }

    // Filter out hidden labels from adjustments
    const adjustments = currentLabelData
        .filter((meta) => !hiddenLabels.has(meta.name))
        .map((meta) => {
        const pos =
            pendingOffsets[meta.name] || {
                lon: meta.position_lon,
                lat: meta.position_lat,
            };
        return {
            city: meta.name,
            dx: pos.lon - meta.anchor_lon,
            dy: pos.lat - meta.anchor_lat,
        };
    });

    spinner.hidden = false;

    try {
        const response = await fetch('/api/labels/apply', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                labels: adjustments, 
                payload: lastPayload, 
                final: triggerDownload,
                hidden_labels: Array.from(hiddenLabels)
            }),
        });

        const data = await response.json();
        spinner.hidden = true;

        if (!response.ok || !data.success) {
            showMessage(data.error || 'Nie udało się zastosować etykiet.', 'error');
            return null;
        }

        pendingOffsets = {};
        handleMapResponse(data);
        renderLabelOverlay();
        
        // Show download button after applying labels
        if (downloadButton && !triggerDownload) {
            downloadButton.style.display = 'inline-flex';
        }

        return data.map?.mapUrl || null;
    } catch (error) {
        spinner.hidden = true;
        console.error(error);
        showMessage('Wystąpił błąd podczas zapisywania etykiet.', 'error');
        return null;
    }
}

// Download button handler - generates final image with labels rendered
if (downloadButton) {
    downloadButton.addEventListener('click', async (event) => {
        event.preventDefault();
        
        if (!lastPayload || !currentLabelData.length) {
            showMessage('Brak danych do pobrania.', 'error');
            return;
        }
        
        spinner.hidden = false;
        
        // Prepare all label adjustments (including unchanged ones), but filter out hidden labels
        const adjustments = currentLabelData
            .filter((meta) => !hiddenLabels.has(meta.name))
            .map((meta) => {
            const pos = pendingOffsets[meta.name] || {
                lon: meta.position_lon,
                lat: meta.position_lat,
            };
            return {
                city: meta.name,
                dx: pos.lon - meta.anchor_lon,
                dy: pos.lat - meta.anchor_lat,
            };
        });
        
        try {
            // Generate final image with render_labels=true (don't update preview)
            const response = await fetch('/api/labels/apply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    labels: adjustments, 
                    payload: lastPayload, 
                    final: true,
                    hidden_labels: Array.from(hiddenLabels)
                }),
            });

            const data = await response.json();
            spinner.hidden = true;

            if (!response.ok || !data.success) {
                showMessage(data.error || 'Nie udało się wygenerować pliku do pobrania.', 'error');
                return;
            }
            
            const mapUrl = data.map?.mapUrl;
            if (mapUrl) {
                // Download without updating preview
                const a = document.createElement('a');
                a.href = mapUrl + `?_=${Date.now()}`;
                a.download = 'mapa.png';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                
                showMessage('Obraz został pobrany!', 'success');
            }
        } catch (error) {
            spinner.hidden = true;
            console.error(error);
            showMessage('Wystąpił błąd podczas pobierania obrazu.', 'error');
        }
    });
}
