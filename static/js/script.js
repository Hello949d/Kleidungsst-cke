// static/js/script.js

document.addEventListener('DOMContentLoaded', function() {
    // --- Drag-and-Drop-Logik für Admin ---
    const adminDashboard = document.getElementById('organization');
    if (adminDashboard) {
        const dropZones = adminDashboard.querySelectorAll('.drop-zone');
        dropZones.forEach(zone => {
            new Sortable(zone, {
                group: 'shared-items',
                animation: 150,
                // NEU: MultiDrag aktivieren
                multiDrag: true, 
                selectedClass: 'sortable-selected', // Klasse für ausgewählte Elemente
                handle: '.draggable-item, .folder-header',

                onEnd: function (evt) {
                    const toZone = evt.to;

                    // Fall 1: Produkte wurden verschoben (können mehrere sein)
                    // Das Plugin stellt die gezogenen Elemente im `evt.items` Array bereit
                    if (evt.items.length > 0 && evt.items[0].classList.contains('product-item')) {
                        // Erstelle eine Liste aller Produkt-IDs
                        const productIds = evt.items.map(item => item.dataset.productId);
                        const newCategoryId = toZone.closest('[data-category-id]').dataset.categoryId;
                        
                        // Sende die Liste an den neuen API-Endpunkt
                        fetch('/admin/api/products/move', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                productIds: productIds, // Sende das Array
                                newCategoryId: newCategoryId || null
                            })
                        }).then(res => { if (!res.ok) alert('Fehler beim Verschieben der Produkte.'); });
                    }
                    // Fall 2: Ein Ordner wurde verschoben (immer nur einer)
                    else if (evt.item.classList.contains('category-folder')) {
                        const categoryId = evt.item.dataset.categoryId;
                        const newParentId = toZone.closest('[data-category-id]').dataset.categoryId;

                        fetch('/admin/api/category/move', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                categoryId: categoryId, 
                                newParentId: newParentId || null 
                            })
                        }).then(res => { if (!res.ok) alert('Fehler beim Verschieben des Ordners.'); });
                    }
                }
            });
        });
    }

    // --- Suchfunktionen (unverändert) ---
    const adminSearchInput = document.getElementById('adminProductSearch');
    if (adminSearchInput) {
        adminSearchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            document.querySelectorAll('#organization .product-item').forEach(product => {
                product.style.display = product.textContent.toLowerCase().includes(searchTerm) ? '' : 'none';
            });
        });
    }

    const userSearchInput = document.getElementById('userProductSearch');
    if (userSearchInput) {
        userSearchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            document.querySelectorAll('.product-row').forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(searchTerm) ? '' : 'none';
            });
            document.querySelectorAll('.accordion-item').forEach(item => {
                const hasVisibleProduct = item.querySelector('.product-row[style*="display: table-row"], .product-row:not([style])');
                const collapseElement = item.querySelector('.accordion-collapse');
                if (searchTerm && hasVisibleProduct && collapseElement) {
                    new bootstrap.Collapse(collapseElement, { toggle: false }).show();
                }
            });
        });
    }
});