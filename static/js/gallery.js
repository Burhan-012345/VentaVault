/**
 * VantaVault - Gallery Module
 * Handles media gallery and upload functionality
 */

class GalleryManager {
    constructor() {
        this.currentFolder = 'default';
        this.selectedMedia = new Set();
        this.uploadQueue = [];
        this.isUploading = false;
    }

    init() {
        this.setupEventListeners();
        this.loadGallery();
        this.setupUploadArea();
    }

    setupEventListeners() {
        // Folder navigation
        document.querySelectorAll('[data-folder]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const folderId = e.target.dataset.folder;
                this.switchFolder(folderId);
            });
        });

        // Selection
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('media-checkbox')) {
                const mediaId = e.target.dataset.id;
                this.toggleSelection(mediaId, e.target.checked);
            }
        });

        // Context menu
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.media-item')) {
                e.preventDefault();
                const mediaId = e.target.closest('.media-item').dataset.id;
                this.showContextMenu(e, mediaId);
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Delete' && this.selectedMedia.size > 0) {
                this.deleteSelected();
            } else if (e.key === 'Escape') {
                this.clearSelection();
            } else if (e.ctrlKey && e.key === 'a') {
                e.preventDefault();
                this.selectAll();
            }
        });
    }

    async loadGallery() {
        try {
            const response = await fetch(`/api/media/list?folder=${this.currentFolder}`);
            const data = await response.json();

            this.renderGallery(data.media || []);
            this.updateGalleryStats(data.stats || {});

        } catch (error) {
            console.error('Failed to load gallery:', error);
            this.showError('Failed to load media');
        }
    }

    renderGallery(mediaItems) {
        const galleryGrid = document.getElementById('galleryGrid');
        if (!galleryGrid) return;

        galleryGrid.innerHTML = '';

        if (mediaItems.length === 0) {
            galleryGrid.innerHTML = `
                <div class="empty-gallery">
                    <div class="empty-icon">📷</div>
                    <h3>No Media Yet</h3>
                    <p>Upload photos and videos to get started</p>
                    <button class="btn" onclick="showUploadModal()">
                        Upload First File
                    </button>
                </div>
            `;
            return;
        }

        mediaItems.forEach(media => {
            const mediaItem = this.createMediaItem(media);
            galleryGrid.appendChild(mediaItem);
        });
    }

    createMediaItem(media) {
        const item = document.createElement('div');
        item.className = 'media-item';
        item.dataset.id = media.id;
        item.dataset.type = media.type || 'image';

        const isSelected = this.selectedMedia.has(media.id.toString());
        const selectedClass = isSelected ? 'selected' : '';

        item.innerHTML = `
            <div class="media-thumbnail-container">
                <img src="/api/media/thumbnail/${media.id}" 
                     alt="${media.filename}"
                     class="media-thumbnail"
                     onerror="this.onerror=null; this.src='data:image/svg+xml;base64,${this.getPlaceholderSVG(media.type)}';">
                
                ${media.type === 'video' ? `
                    <div class="video-indicator">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                            <path d="M8 5v14l11-7z"/>
                        </svg>
                    </div>
                ` : ''}
                
                <div class="media-overlay">
                    <input type="checkbox" class="media-checkbox" data-id="${media.id}" ${isSelected ? 'checked' : ''}>
                    <button class="media-menu-btn" onclick="event.stopPropagation(); showMediaMenu(event, ${media.id})">
                        ⋮
                    </button>
                </div>
            </div>
            
            <div class="media-info">
                <div class="media-filename" title="${media.filename}">
                    ${this.truncateFilename(media.filename)}
                </div>
                <div class="media-meta">
                    <span class="media-size">${this.formatFileSize(media.file_size)}</span>
                    <span class="media-date">${this.formatDate(media.upload_date)}</span>
                </div>
            </div>
        `;

        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('media-checkbox') && 
                !e.target.classList.contains('media-menu-btn')) {
                this.viewMedia(media.id);
            }
        });

        return item;
    }

    async switchFolder(folderId) {
        this.currentFolder = folderId;
        this.clearSelection();
        
        // Update UI
        document.querySelectorAll('.folder-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-folder="${folderId}"]`).classList.add('active');
        
        await this.loadGallery();
    }

    toggleSelection(mediaId, selected) {
        if (selected) {
            this.selectedMedia.add(mediaId);
        } else {
            this.selectedMedia.delete(mediaId);
        }

        this.updateSelectionUI();
    }

    selectAll() {
        const checkboxes = document.querySelectorAll('.media-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            this.selectedMedia.add(checkbox.dataset.id);
        });
        this.updateSelectionUI();
    }

    clearSelection() {
        this.selectedMedia.clear();
        document.querySelectorAll('.media-checkbox').forEach(cb => {
            cb.checked = false;
        });
        this.updateSelectionUI();
    }

    updateSelectionUI() {
        const selectedCount = this.selectedMedia.size;
        const selectionBar = document.getElementById('selectionBar');
        
        if (selectedCount > 0) {
            selectionBar.style.display = 'flex';
            document.getElementById('selectedCount').textContent = selectedCount;
        } else {
            selectionBar.style.display = 'none';
        }
    }

    async deleteSelected() {
        if (this.selectedMedia.size === 0) return;

        if (!confirm(`Delete ${this.selectedMedia.size} item(s)? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch('/api/media/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    media_ids: Array.from(this.selectedMedia)
                })
            });

            if (response.ok) {
                this.showSuccess(`${this.selectedMedia.size} item(s) deleted`);
                this.clearSelection();
                await this.loadGallery();
            } else {
                throw new Error('Delete failed');
            }

        } catch (error) {
            console.error('Delete error:', error);
            this.showError('Failed to delete items');
        }
    }

    viewMedia(mediaId) {
        // Show media viewer modal
        this.showMediaViewer(mediaId);
    }

    async showMediaViewer(mediaId) {
        try {
            const response = await fetch(`/api/media/info/${mediaId}`);
            const mediaInfo = await response.json();

            const viewer = document.createElement('div');
            viewer.className = 'media-viewer';
            viewer.innerHTML = `
                <div class="viewer-overlay" onclick="closeMediaViewer()"></div>
                <div class="viewer-content">
                    <div class="viewer-header">
                        <h3>${mediaInfo.filename}</h3>
                        <button class="viewer-close" onclick="closeMediaViewer()">×</button>
                    </div>
                    
                    <div class="viewer-body">
                        ${mediaInfo.type === 'image' ? 
                            `<img src="/api/media/${mediaId}" alt="${mediaInfo.filename}">` :
                            `<video controls src="/api/media/${mediaId}"></video>`
                        }
                    </div>
                    
                    <div class="viewer-footer">
                        <div class="media-details">
                            <div><strong>Size:</strong> ${this.formatFileSize(mediaInfo.file_size)}</div>
                            <div><strong>Type:</strong> ${mediaInfo.mimetype}</div>
                            <div><strong>Uploaded:</strong> ${this.formatDate(mediaInfo.upload_date)}</div>
                            <div><strong>Dimensions:</strong> ${mediaInfo.width || 'N/A'} × ${mediaInfo.height || 'N/A'}</div>
                        </div>
                        
                        <div class="viewer-actions">
                            <button class="btn" onclick="downloadMedia(${mediaId})">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                Download
                            </button>
                            <button class="btn btn-secondary" onclick="shareMedia(${mediaId})">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
                                    <polyline points="16 6 12 2 8 6"/>
                                    <line x1="12" y1="2" x2="12" y2="15"/>
                                </svg>
                                Share
                            </button>
                            <button class="btn btn-danger" onclick="deleteMedia(${mediaId})">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                </svg>
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(viewer);
            document.body.style.overflow = 'hidden';

        } catch (error) {
            console.error('Failed to load media:', error);
            this.showError('Failed to load media');
        }
    }

    setupUploadArea() {
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');

        if (!uploadArea || !fileInput || !uploadBtn) return;

        // Click to browse
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            this.handleFileSelection(files);
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            this.handleFileSelection(files);
        });

        // Upload button
        uploadBtn.addEventListener('click', () => {
            this.processUploadQueue();
        });
    }

    handleFileSelection(files) {
        const validFiles = files.filter(file => {
            const isValidType = file.type.startsWith('image/') || file.type.startsWith('video/');
            const isValidSize = file.size <= (500 * 1024 * 1024); // 500MB limit
            
            if (!isValidType) {
                this.showError(`${file.name}: Invalid file type`);
            }
            if (!isValidSize) {
                this.showError(`${file.name}: File too large (max 500MB)`);
            }
            
            return isValidType && isValidSize;
        });

        if (validFiles.length === 0) return;

        // Add to upload queue
        validFiles.forEach(file => {
            this.uploadQueue.push({
                file: file,
                progress: 0,
                status: 'pending'
            });
        });

        this.updateUploadQueueUI();
    }

    updateUploadQueueUI() {
        const queueList = document.getElementById('uploadQueueList');
        const uploadBtn = document.getElementById('uploadBtn');
        
        if (!queueList || !uploadBtn) return;

        queueList.innerHTML = '';
        
        this.uploadQueue.forEach((item, index) => {
            const queueItem = document.createElement('div');
            queueItem.className = `queue-item ${item.status}`;
            queueItem.innerHTML = `
                <div class="queue-item-info">
                    <div class="queue-filename">${item.file.name}</div>
                    <div class="queue-size">${this.formatFileSize(item.file.size)}</div>
                </div>
                <div class="queue-item-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${item.progress}%"></div>
                    </div>
                    <div class="queue-status">${item.status}</div>
                </div>
                <button class="queue-remove" onclick="gallery.removeFromQueue(${index})" ${item.status === 'uploading' ? 'disabled' : ''}>
                    ×
                </button>
            `;
            queueList.appendChild(queueItem);
        });

        uploadBtn.disabled = this.uploadQueue.length === 0 || this.isUploading;
        uploadBtn.textContent = this.isUploading ? 'Uploading...' : `Upload (${this.uploadQueue.length})`;
    }

    removeFromQueue(index) {
        this.uploadQueue.splice(index, 1);
        this.updateUploadQueueUI();
    }

    async processUploadQueue() {
        if (this.isUploading || this.uploadQueue.length === 0) return;

        this.isUploading = true;
        this.updateUploadQueueUI();

        const folderId = this.currentFolder;

        for (let i = 0; i < this.uploadQueue.length; i++) {
            const item = this.uploadQueue[i];
            
            if (item.status === 'completed') continue;

            item.status = 'uploading';
            this.updateUploadQueueUI();

            try {
                await this.uploadFile(item.file, folderId, (progress) => {
                    item.progress = progress;
                    this.updateUploadQueueUI();
                });

                item.status = 'completed';
                item.progress = 100;

            } catch (error) {
                console.error('Upload failed:', error);
                item.status = 'failed';
                this.showError(`Failed to upload ${item.file.name}`);
            }

            this.updateUploadQueueUI();
        }

        this.isUploading = false;
        this.updateUploadQueueUI();

        // Refresh gallery after successful uploads
        const hasSuccess = this.uploadQueue.some(item => item.status === 'completed');
        if (hasSuccess) {
            await this.loadGallery();
            
            // Clear completed items from queue after delay
            setTimeout(() => {
                this.uploadQueue = this.uploadQueue.filter(item => item.status !== 'completed');
                this.updateUploadQueueUI();
            }, 2000);
        }
    }

    async uploadFile(file, folderId, onProgress) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('folder_id', folderId);

            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    onProgress(Math.round(percent));
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(`Upload failed: ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Network error'));
            });

            xhr.open('POST', '/api/media/upload');
            xhr.send(formData);
        });
    }

    // Utility methods
    truncateFilename(filename, maxLength = 20) {
        if (filename.length <= maxLength) return filename;
        const extension = filename.split('.').pop();
        const name = filename.substring(0, maxLength - extension.length - 4);
        return `${name}... .${extension}`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    getPlaceholderSVG(type) {
        const svg = type === 'video' ? 
            `<svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="120" height="120" fill="#1a1a1a"/>
                <path d="M45 40L75 60L45 80V40Z" fill="#262626"/>
            </svg>` :
            `<svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="120" height="120" fill="#1a1a1a"/>
                <path d="M75 45H41C38.7909 45 37 46.7909 37 49V79C37 81.2091 38.7909 83 41 83H79C81.2091 83 83 81.2091 83 79V55C83 52.7909 81.2091 51 79 51H75V45Z" fill="#262626"/>
            </svg>`;
        
        return btoa(svg);
    }

    updateGalleryStats(stats) {
        const statsElement = document.getElementById('galleryStats');
        if (statsElement) {
            statsElement.innerHTML = `
                <span>${stats.count || 0} items</span>
                <span>•</span>
                <span>${this.formatFileSize(stats.total_size || 0)}</span>
            `;
        }
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div>${type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️'} ${message}</div>
            <button onclick="this.parentElement.remove()">×</button>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? 'rgba(255, 51, 51, 0.1)' : 
                         type === 'success' ? 'rgba(0, 255, 0, 0.1)' : 
                         'rgba(255, 255, 255, 0.1)'};
            color: ${type === 'error' ? '#ff3333' : 
                    type === 'success' ? '#00ff00' : 
                    'var(--text-primary)'};
            padding: 1rem 1.5rem;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 1rem;
            z-index: 10000;
            border: 1px solid ${type === 'error' ? 'rgba(255, 51, 51, 0.3)' : 
                              type === 'success' ? 'rgba(0, 255, 0, 0.3)' : 
                              'rgba(255, 255, 255, 0.2)'};
            backdrop-filter: blur(10px);
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }
}

// Global gallery instance
let gallery = null;

// Initialize gallery on page load
document.addEventListener('DOMContentLoaded', () => {
    gallery = new GalleryManager();
    gallery.init();
});

// Global functions for HTML onclick handlers
function showUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeUploadModal() {
    const modal = document.getElementById('uploadModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function closeMediaViewer() {
    const viewer = document.querySelector('.media-viewer');
    if (viewer) {
        viewer.remove();
        document.body.style.overflow = '';
    }
}

function showMediaMenu(event, mediaId) {
    // Prevent default context menu
    event.preventDefault();
    
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.cssText = `
        position: fixed;
        top: ${event.clientY}px;
        left: ${event.clientX}px;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.5rem;
        z-index: 1000;
        backdrop-filter: blur(10px);
        min-width: 180px;
    `;
    
    menu.innerHTML = `
        <button class="context-menu-item" onclick="viewMedia(${mediaId}); this.closest('.context-menu').remove()">
            👁️ View
        </button>
        <button class="context-menu-item" onclick="downloadMedia(${mediaId}); this.closest('.context-menu').remove()">
            📥 Download
        </button>
        <button class="context-menu-item" onclick="shareMedia(${mediaId}); this.closest('.context-menu').remove()">
            🔗 Share
        </button>
        <button class="context-menu-item" onclick="moveMedia(${mediaId}); this.closest('.context-menu').remove()">
            📂 Move
        </button>
        <hr style="border: none; border-top: 1px solid var(--border-color); margin: 0.5rem 0;">
        <button class="context-menu-item danger" onclick="deleteMedia(${mediaId}); this.closest('.context-menu').remove()">
            🗑️ Delete
        </button>
    `;
    
    document.body.appendChild(menu);
    
    // Close menu when clicking elsewhere
    setTimeout(() => {
        const closeMenu = (e) => {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        };
        document.addEventListener('click', closeMenu);
    });
}

// Media action functions
async function downloadMedia(mediaId) {
    try {
        const response = await fetch(`/api/media/${mediaId}`);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `media_${mediaId}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Download failed:', error);
        alert('Download failed');
    }
}

async function shareMedia(mediaId) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h2>Share Media</h2>
            <p>Create a secure share link</p>
            
            <div class="form-group">
                <label>Expiry Time</label>
                <select id="shareExpirySelect" class="form-control">
                    <option value="1">1 hour</option>
                    <option value="24" selected>24 hours</option>
                    <option value="168">7 days</option>
                    <option value="720">30 days</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Maximum Views</label>
                <input type="number" id="shareMaxViews" class="form-control" value="1" min="1" max="10">
            </div>
            
            <div class="share-link-container" style="display: none;">
                <label>Share Link</label>
                <div class="input-group">
                    <input type="text" id="shareLinkInput" class="form-control" readonly>
                    <button class="btn" onclick="copyShareLink()">Copy</button>
                </div>
                <small style="color: var(--text-secondary);">This link will expire after the specified time</small>
            </div>
            
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">Cancel</button>
                <button class="btn" onclick="createShareLink(${mediaId})">Create Link</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

async function createShareLink(mediaId) {
    const expiry = document.getElementById('shareExpirySelect').value;
    const maxViews = document.getElementById('shareMaxViews').value;
    
    try {
        const response = await fetch('/api/share/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                media_id: mediaId,
                expiry_hours: parseInt(expiry),
                max_views: parseInt(maxViews)
            })
        });
        
        const data = await response.json();
        
        if (data.share_token) {
            const shareUrl = `${window.location.origin}/share/${data.share_token}`;
            document.getElementById('shareLinkInput').value = shareUrl;
            document.querySelector('.share-link-container').style.display = 'block';
        }
        
    } catch (error) {
        console.error('Failed to create share link:', error);
        alert('Failed to create share link');
    }
}

function copyShareLink() {
    const input = document.getElementById('shareLinkInput');
    input.select();
    document.execCommand('copy');
    alert('Link copied to clipboard!');
}

async function deleteMedia(mediaId) {
    if (!confirm('Are you sure you want to delete this media?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/media/${mediaId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            if (gallery) {
                gallery.showSuccess('Media deleted');
                gallery.loadGallery();
            }
            closeMediaViewer();
        } else {
            throw new Error('Delete failed');
        }
        
    } catch (error) {
        console.error('Delete error:', error);
        alert('Failed to delete media');
    }
}

async function moveMedia(mediaId) {
    // Get available folders
    try {
        const response = await fetch('/api/folders');
        const data = await response.json();
        
        const folderSelect = document.createElement('select');
        folderSelect.className = 'form-control';
        folderSelect.innerHTML = '<option value="">Select Folder</option>';
        
        data.folders.forEach(folder => {
            folderSelect.innerHTML += `<option value="${folder.id}">${folder.name}</option>`;
        });
        
        const targetFolder = prompt('Select folder to move to:', folderSelect.outerHTML);
        if (targetFolder) {
            await fetch(`/api/media/${mediaId}/move`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ folder_id: targetFolder })
            });
            
            if (gallery) {
                gallery.showSuccess('Media moved');
                gallery.loadGallery();
            }
        }
        
    } catch (error) {
        console.error('Move error:', error);
        alert('Failed to move media');
    }
}