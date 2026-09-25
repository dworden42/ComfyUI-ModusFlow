// ModusFlow Image Gallery v1.2.0 - Browse output directory with lazy loading and breadcrumb navigation
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "modusflow.ImageGallery",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "ModusFlowImageGallery") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);
                
                this.serialize_widgets = false;
                this.isVirtualNode = true;
                this.size = [600, 350];
                this.resizable = true;
                
                // Create container
                const container = document.createElement("div");
                container.style.cssText = `
                    width: 100%;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    background: #1a1a1a;
                    border-radius: 4px;
                    box-sizing: border-box;
                    position: relative;
                `;
                
                // Create breadcrumb
                const breadcrumb = document.createElement("div");
                breadcrumb.style.cssText = `
                    padding: 8px 12px;
                    background: #252525;
                    border-bottom: 1px solid #3a3a3a;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    flex-wrap: wrap;
                    font-size: 12px;
                    color: #ccc;
                    flex-shrink: 0;
                `;
                
                // Create toolbar (search and sort)
                const toolbar = document.createElement("div");
                toolbar.style.cssText = `
                    padding: 8px 12px;
                    background: #202020;
                    border-bottom: 1px solid #3a3a3a;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    font-size: 12px;
                    flex-shrink: 0;
                `;
                
                // Search wrapper with clear button
                const searchWrapper = document.createElement("div");
                searchWrapper.style.cssText = `
                    flex: 1;
                    position: relative;
                    display: flex;
                    align-items: center;
                `;
                
                const searchInput = document.createElement("input");
                searchInput.type = "text";
                searchInput.placeholder = "Search...";
                searchInput.style.cssText = `
                    width: 100%;
                    background: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    color: #ccc;
                    padding: 6px 30px 6px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                    outline: none;
                `;
                searchInput.oninput = (e) => {
                    searchTerm = e.target.value.toLowerCase();
                    clearBtn.style.display = searchTerm ? 'flex' : 'none';
                    loadGallery();
                };
                
                const clearBtn = document.createElement("button");
                clearBtn.textContent = "✕";
                clearBtn.style.cssText = `
                    position: absolute;
                    right: 5px;
                    background: none;
                    border: none;
                    color: #888;
                    cursor: pointer;
                    padding: 4px 8px;
                    font-size: 14px;
                    display: none;
                    align-items: center;
                    justify-content: center;
                `;
                clearBtn.onmouseover = () => clearBtn.style.color = '#ccc';
                clearBtn.onmouseout = () => clearBtn.style.color = '#888';
                clearBtn.onclick = () => {
                    searchInput.value = '';
                    searchTerm = '';
                    clearBtn.style.display = 'none';
                    loadGallery();
                };
                
                searchWrapper.appendChild(searchInput);
                searchWrapper.appendChild(clearBtn);
                
                // Sort label
                const sortLabel = document.createElement("span");
                sortLabel.textContent = "Sort:";
                sortLabel.style.color = "#888";
                
                // Sort dropdown
                const sortSelect = document.createElement("select");
                sortSelect.style.cssText = `
                    background: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    color: #ccc;
                    padding: 6px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                    cursor: pointer;
                    outline: none;
                `;
                sortSelect.innerHTML = `
                    <option value="name_asc">Name (A-Z)</option>
                    <option value="name_desc">Name (Z-A)</option>
                    <option value="modified_desc" selected>Date Modified (Newest)</option>
                    <option value="modified_asc">Date Modified (Oldest)</option>
                    <option value="created_desc">Date Created (Newest)</option>
                    <option value="created_asc">Date Created (Oldest)</option>
                `;
                sortSelect.onchange = (e) => {
                    sortBy = e.target.value;
                    loadGallery();
                };
                
                toolbar.appendChild(searchWrapper);
                toolbar.appendChild(sortLabel);
                toolbar.appendChild(sortSelect);
                
                // Create grid container
                const gridContainer = document.createElement("div");
                gridContainer.style.cssText = `
                    flex: 1 1 auto;
                    overflow-y: auto;
                    overflow-x: hidden;
                    min-height: 0;
                    padding: 10px;
                    box-sizing: border-box;
                `;
                
                const grid = document.createElement("div");
                grid.style.cssText = `
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                    gap: 10px;
                    width: 100%;
                `;
                
                // Initial loading indicator
                grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #888;">Loading...</div>';
                
                gridContainer.appendChild(grid);
                container.appendChild(breadcrumb);
                container.appendChild(toolbar);
                container.appendChild(gridContainer);
                
                // State
                let currentPath = [];
                let autoRefreshEnabled = true;
                let lastImageCount = 0;
                let sortBy = 'modified_desc'; // name_asc, name_desc, modified_asc, modified_desc, created_asc, created_desc
                let searchTerm = '';
                let currentImages = []; // Track current image list for navigation
                
                // Show image preview with navigation
                const showImagePreview = (filename, imageList, currentIndex) => {
                    let index = currentIndex;
                    let modal = null;
                    let fullImg = null;
                    
                    const updateImage = () => {
                        const imgFilename = imageList[index];
                        const imgUrl = `/view?filename=${encodeURIComponent(imgFilename)}&subfolder=${encodeURIComponent(currentPath.join("/"))}&type=output`;
                        if (fullImg) {
                            fullImg.src = imgUrl;
                        }
                    };
                    
                    const showNext = () => {
                        if (index < imageList.length - 1) {
                            index++;
                            updateImage();
                        }
                    };
                    
                    const showPrevious = () => {
                        if (index > 0) {
                            index--;
                            updateImage();
                        }
                    };
                    
                    const closeModal = () => {
                        if (modal && modal.parentNode) {
                            document.body.removeChild(modal);
                            document.removeEventListener('keydown', keyHandler);
                        }
                    };
                    
                    const keyHandler = (e) => {
                        if (e.key === 'ArrowRight') {
                            e.preventDefault();
                            showNext();
                        } else if (e.key === 'ArrowLeft') {
                            e.preventDefault();
                            showPrevious();
                        } else if (e.key === 'Escape') {
                            e.preventDefault();
                            closeModal();
                        }
                    };
                    
                    modal = document.createElement("div");
                    modal.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100vw;
                        height: 100vh;
                        background: rgba(0, 0, 0, 0.9);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 10000;
                        cursor: pointer;
                        padding: 20px;
                    `;
                    
                    fullImg = document.createElement("img");
                    const imgUrl = `/view?filename=${encodeURIComponent(filename)}&subfolder=${encodeURIComponent(currentPath.join("/"))}&type=output`;
                    fullImg.src = imgUrl;
                    fullImg.style.cssText = "max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px; pointer-events: none;";
                    
                    modal.onclick = closeModal;
                    modal.onwheel = (e) => {
                        e.preventDefault();
                        if (e.deltaY < 0) {
                            showPrevious();
                        } else if (e.deltaY > 0) {
                            showNext();
                        }
                    };
                    
                    document.addEventListener('keydown', keyHandler);
                    modal.appendChild(fullImg);
                    document.body.appendChild(modal);
                };
                
                // Update breadcrumb
                const updateBreadcrumb = () => {
                    breadcrumb.innerHTML = "";
                    
                    const homeLink = document.createElement("span");
                    homeLink.textContent = "📁 Output";
                    homeLink.style.cssText = "cursor: pointer; padding: 4px 8px; border-radius: 3px;";
                    homeLink.onmouseenter = () => homeLink.style.background = "#3a3a3a";
                    homeLink.onmouseleave = () => homeLink.style.background = "transparent";
                    homeLink.onclick = () => {
                        currentPath = [];
                        loadGallery();
                    };
                    breadcrumb.appendChild(homeLink);
                    
                    currentPath.forEach((segment, index) => {
                        const separator = document.createElement("span");
                        separator.textContent = " / ";
                        separator.style.color = "#666";
                        breadcrumb.appendChild(separator);
                        
                        const link = document.createElement("span");
                        link.textContent = segment;
                        link.style.cssText = "cursor: pointer; padding: 4px 8px; border-radius: 3px;";
                        link.onmouseenter = () => link.style.background = "#3a3a3a";
                        link.onmouseleave = () => link.style.background = "transparent";
                        link.onclick = () => {
                            currentPath = currentPath.slice(0, index + 1);
                            loadGallery();
                        };
                        breadcrumb.appendChild(link);
                    });
                    
                    const autoBtn = document.createElement("button");
                    autoBtn.textContent = autoRefreshEnabled ? "🔄 Auto" : "⏸ Auto";
                    autoBtn.style.cssText = `
                        margin-left: auto;
                        background: ${autoRefreshEnabled ? '#3a7a3a' : '#3a3a3a'};
                        border: none;
                        color: #ccc;
                        padding: 4px 12px;
                        border-radius: 3px;
                        cursor: pointer;
                        font-size: 11px;
                    `;
                    autoBtn.onclick = () => {
                        autoRefreshEnabled = !autoRefreshEnabled;
                        autoBtn.textContent = autoRefreshEnabled ? "🔄 Auto" : "⏸ Auto";
                        autoBtn.style.background = autoRefreshEnabled ? '#3a7a3a' : '#3a3a3a';
                    };
                    breadcrumb.appendChild(autoBtn);
                    
                    const refreshBtn = document.createElement("button");
                    refreshBtn.textContent = "🔄";
                    refreshBtn.style.cssText = `
                        margin-left: 5px;
                        background: #3a3a3a;
                        border: none;
                        color: #ccc;
                        padding: 4px 12px;
                        border-radius: 3px;
                        cursor: pointer;
                    `;
                    refreshBtn.onclick = () => loadGallery();
                    breadcrumb.appendChild(refreshBtn);
                };
                
                // Create folder item
                const createFolderItem = (name) => {
                    const item = document.createElement("div");
                    item.style.cssText = `
                        aspect-ratio: 1;
                        background: #2a2a2a;
                        border: 1px solid #3a3a3a;
                        border-radius: 4px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        cursor: pointer;
                        padding: 10px;
                        text-align: center;
                    `;
                    
                    const icon = document.createElement("div");
                    icon.textContent = "📁";
                    icon.style.fontSize = "48px";
                    
                    const label = document.createElement("div");
                    label.textContent = name;
                    label.style.cssText = "margin-top: 8px; font-size: 11px; color: #ccc; word-break: break-word;";
                    
                    item.appendChild(icon);
                    item.appendChild(label);
                    item.onclick = () => {
                        currentPath.push(name);
                        loadGallery();
                    };
                    
                    return item;
                };
                
                // Create image item
                const createImageItem = (filename) => {
                    const item = document.createElement("div");
                    item.style.cssText = `
                        aspect-ratio: 1;
                        background: #2a2a2a;
                        border: 1px solid #3a3a3a;
                        border-radius: 4px;
                        overflow: hidden;
                        cursor: pointer;
                        position: relative;
                    `;
                    
                    const img = document.createElement("img");
                    img.style.cssText = "width: 100%; height: 100%; object-fit: cover; opacity: 0; transition: opacity 0.3s;";
                    
                    const observer = new IntersectionObserver((entries) => {
                        entries.forEach(entry => {
                            if (entry.isIntersecting) {
                                const imgUrl = `/view?filename=${encodeURIComponent(filename)}&subfolder=${encodeURIComponent(currentPath.join("/"))}&type=output`;
                                img.src = imgUrl;
                                img.onload = () => img.style.opacity = "1";
                                observer.unobserve(item);
                            }
                        });
                    }, { rootMargin: "50px" });
                    
                    observer.observe(item);
                    item.appendChild(img);
                    
                    item.onclick = () => {
                        const imageIndex = currentImages.indexOf(filename);
                        showImagePreview(filename, currentImages, imageIndex);
                    };
                    
                    item.oncontextmenu = (e) => {
                        e.preventDefault();
                        showMetadata(filename);
                    };
                    
                    return item;
                };
                
                // Show metadata
                const showMetadata = async (filename) => {
                    try {
                        const subpath = currentPath.join("/");
                        const response = await api.fetchApi(`/modusflow/gallery/metadata?filename=${encodeURIComponent(filename)}&path=${encodeURIComponent(subpath)}`);
                        const data = await response.json();
                        
                        const modal = document.createElement("div");
                        modal.style.cssText = `
                            position: fixed;
                            top: 0;
                            left: 0;
                            width: 100vw;
                            height: 100vh;
                            background: rgba(0, 0, 0, 0.8);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            z-index: 10001;
                            padding: 20px;
                        `;
                        
                        const box = document.createElement("div");
                        box.style.cssText = `
                            background: #1e1e1e;
                            border: 1px solid #3a3a3a;
                            border-radius: 8px;
                            max-width: 800px;
                            max-height: 80vh;
                            width: 100%;
                            display: flex;
                            flex-direction: column;
                        `;
                        
                        const header = document.createElement("div");
                        header.style.cssText = "padding: 16px 20px; background: #252525; border-bottom: 1px solid #3a3a3a; display: flex; justify-content: space-between;";
                        header.innerHTML = `<div style="color: #ccc; font-size: 14px;">${filename}</div><button style="background: transparent; border: none; color: #888; font-size: 20px; cursor: pointer;">✕</button>`;
                        
                        const content = document.createElement("div");
                        content.style.cssText = "flex: 1; overflow-y: auto; padding: 20px;";
                        
                        if (data.success && data.metadata) {
                            const pre = document.createElement("pre");
                            pre.style.cssText = "margin: 0; padding: 16px; background: #0d1117; border: 1px solid #2a2a2a; border-radius: 6px; color: #e6edf3; font-family: monospace; font-size: 12px; white-space: pre-wrap;";
                            pre.textContent = JSON.stringify(data.metadata, null, 2);
                            content.appendChild(pre);
                        } else {
                            content.innerHTML = `<div style="text-align: center; padding: 40px; color: #888;">No metadata found</div>`;
                        }
                        
                        box.appendChild(header);
                        box.appendChild(content);
                        modal.appendChild(box);
                        
                        const close = () => document.body.removeChild(modal);
                        modal.onclick = (e) => { if (e.target === modal) close(); };
                        header.querySelector("button").onclick = close;
                        
                        document.body.appendChild(modal);
                    } catch (error) {
                        console.error("Error loading metadata:", error);
                    }
                };
                
                // Load gallery
                const loadGallery = async () => {
                    try {
                        const subpath = currentPath.join("/");
                        const url = `/modusflow/gallery/list?path=${encodeURIComponent(subpath)}&sort=${sortBy}`;
                        console.log('[Gallery] Loading:', url);
                        const response = await api.fetchApi(url);
                        const data = await response.json();
                        
                        console.log('[Gallery] Response:', data);
                        
                        if (!data.success) {
                            console.error('[Gallery] Error:', data.message);
                            grid.innerHTML = `<div style="color: #f88; padding: 20px;">Error: ${data.message}</div>`;
                            return;
                        }
                        
                        grid.innerHTML = "";
                        updateBreadcrumb();
                        
                        let { folders, images, folderStats, imageStats } = data.data;
                        
                        // Apply search filter
                        if (searchTerm) {
                            folders = folders.filter(f => f.toLowerCase().includes(searchTerm));
                            images = images.filter(i => i.toLowerCase().includes(searchTerm));
                        }
                        
                        // Parse sort option
                        const [sortField, sortDir] = sortBy.split('_'); // e.g., "name_asc" -> ["name", "asc"]
                        const isAsc = sortDir === 'asc';
                        
                        // Sort folders
                        if (sortField === 'name') {
                            folders.sort((a, b) => {
                                const result = a.localeCompare(b);
                                return isAsc ? result : -result;
                            });
                        } else if (folderStats) {
                            folders.sort((a, b) => {
                                const statA = folderStats[a];
                                const statB = folderStats[b];
                                if (!statA || !statB) return 0;
                                const timeA = sortField === 'modified' ? statA.modified : statA.created;
                                const timeB = sortField === 'modified' ? statB.modified : statB.created;
                                const result = timeB - timeA;
                                return isAsc ? -result : result; // Flip for ascending
                            });
                        }
                        
                        // Sort images
                        if (sortField === 'name') {
                            images.sort((a, b) => {
                                const result = a.localeCompare(b);
                                return isAsc ? result : -result;
                            });
                        } else if (imageStats) {
                            images.sort((a, b) => {
                                const statA = imageStats[a];
                                const statB = imageStats[b];
                                if (!statA || !statB) return 0;
                                const timeA = sortField === 'modified' ? statA.modified : statA.created;
                                const timeB = sortField === 'modified' ? statB.modified : statB.created;
                                const result = timeB - timeA;
                                return isAsc ? -result : result; // Flip for ascending
                            });
                        }
                        
                        folders.forEach(folder => grid.appendChild(createFolderItem(folder)));
                        
                        // Store current images for navigation
                        currentImages = images;
                        images.forEach(img => grid.appendChild(createImageItem(img)));
                        
                        console.log(`[Gallery] Displayed ${folders.length} folders and ${images.length} images`);
                        
                        if (folders.length === 0 && images.length === 0) {
                            const empty = document.createElement("div");
                            empty.style.cssText = "grid-column: 1 / -1; text-align: center; padding: 40px; color: #888; font-size: 14px;";
                            empty.textContent = searchTerm ? "No results found" : "No images or folders found";
                            grid.appendChild(empty);
                        }
                        
                        lastImageCount = images.length;
                        
                        // Update tracked image list for change detection
                        lastImageList = images.sort().join(',');
                    } catch (error) {
                        console.error("[Gallery] Error loading gallery:", error);
                        grid.innerHTML = `<div style="color: #f88; padding: 20px;">Error: ${error.message}</div>`;
                    }
                };
                
                // Auto-refresh with polling
                let pollInterval = null;
                let lastImageList = [];
                
                const checkForNewImages = async () => {
                    if (!autoRefreshEnabled) return;
                    
                    try {
                        const subpath = currentPath.join("/");
                        const url = `/modusflow/gallery/list?path=${encodeURIComponent(subpath)}&sort=${sortBy}`;
                        const response = await api.fetchApi(url);
                        const data = await response.json();
                        
                        if (data.success) {
                            const newImageList = data.data.images.sort().join(',');
                            
                            // Check if images have changed
                            if (lastImageList.length > 0 && newImageList !== lastImageList) {
                                console.log('[Gallery] New images detected, refreshing...');
                                await loadGallery();
                            }
                            
                            lastImageList = newImageList;
                        }
                    } catch (error) {
                        console.error('[Gallery] Error checking for new images:', error);
                    }
                };
                
                const setupAutoRefresh = () => {
                    // Poll every 2 seconds when auto-refresh is enabled
                    pollInterval = setInterval(checkForNewImages, 2000);
                    
                    this._galleryCleanup = () => {
                        if (pollInterval) {
                            clearInterval(pollInterval);
                            pollInterval = null;
                        }
                    };
                };
                
                loadGallery();
                setupAutoRefresh();
                
                // Create widget
                const widget = this.addDOMWidget("gallery", "customtext", container, {
                    getValue: () => "",
                    setValue: () => {},
                    serialize: false
                });
                
                // Return fixed size that matches initial container
                widget.computeSize = () => [600, 350];
                
                // Force container to respect exact height (account for title bar and padding)
                const updateContainerSize = () => {
                    const height = this.size[1] - 35; // Account for title bar
                    container.style.height = `${height}px`;
                    container.style.maxHeight = `${height}px`;
                    container.style.minHeight = `${height}px`;
                };
                
                // Update on resize
                const originalOnResize = this.onResize;
                this.onResize = function(size) {
                    originalOnResize?.apply(this, arguments);
                    updateContainerSize();
                };
                
                // Set initial size to match widget
                updateContainerSize();
            };
            
            const onRemoved = nodeType.prototype.onRemoved;
            nodeType.prototype.onRemoved = function () {
                if (this._galleryCleanup) {
                    this._galleryCleanup();
                }
                return onRemoved?.apply(this, arguments);
            };
        }
    },
});
