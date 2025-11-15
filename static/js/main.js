// État de l'application
let appState = {
  columns: [],
  selectedColumns: [],
  signaturePath: null,
  logoPath: null,
  lastExportedFiles: null,
};

// Initialisation
document.addEventListener("DOMContentLoaded", function () {
  initializeEventListeners();
  initializeColumnsSortable();
});

// Initialisation des écouteurs d'événements
function initializeEventListeners() {
  // Connexion - CORRECTION : utiliser les bons IDs
  document
    .getElementById("connect-btn") // ✅ CORRIGÉ
    .addEventListener("click", loadTables);
  document
    .getElementById("load-columns-btn")
    .addEventListener("click", loadColumns);

  // Table select
  document
    .getElementById("table-select")
    .addEventListener("change", function () {
      // Activer le bouton "Charger les colonnes" quand une table est sélectionnée
      const btn = document.getElementById("load-columns-btn");
      btn.disabled = !this.value;
    });

  // Colonnes
  document
    .getElementById("select-all-columns")
    .addEventListener("click", selectAllColumns);
  document
    .getElementById("deselect-all-columns")
    .addEventListener("click", deselectAllColumns);
  document
    .getElementById("add-filter-btn")
    .addEventListener("click", addAdvancedFilter);

  // Logo
  document
    .getElementById("logo-upload")
    .addEventListener("change", handleLogoUpload);
  document
    .getElementById("remove-logo-btn")
    .addEventListener("click", removeLogo);

  // Signature
  document
    .getElementById("signature-upload")
    .addEventListener("change", handleSignatureUpload);

  // CORRECTION : Vérifier si l'élément existe avant d'ajouter l'écouteur
  const removeSignatureBtn = document.getElementById("remove-signature-btn");
  if (removeSignatureBtn) {
    removeSignatureBtn.addEventListener("click", removeSignature);
  }

  // Export
  document.getElementById("export-btn").addEventListener("click", exportPDFs);

  // Configurations
  document
    .getElementById("save-config-btn")
    .addEventListener("click", saveConfiguration);

  // Upload vers Grist
  document
    .getElementById("upload-to-grist-btn")
    .addEventListener("click", uploadPDFsToGrist);

  // Actualiser le compteur de PDFs
  document
    .getElementById("refresh-count-btn")
    .addEventListener("click", updatePDFCount);

  // Charger les configurations au clic sur l'onglet
  const configTab = document.getElementById("tabpanel-configuration");
  if (configTab) {
    configTab.addEventListener("click", loadConfigurationsList);
  }

  // NOUVEAU : Écouter les changements sur le mode de filtre
  const filterModeRadios = document.querySelectorAll(
    'input[name="filter-mode"]'
  );
  filterModeRadios.forEach((radio) => {
    radio.addEventListener("change", updatePDFCount);
  });
}

// Initialiser Sortable.js pour les colonnes
function initializeColumnsSortable() {
  const columnsList = document.getElementById("sortable-columns");
  new Sortable(columnsList, {
    animation: 150,
    handle: ".drag-handle",
    ghostClass: "sortable-ghost",
    onEnd: function () {
      updateSelectedColumns();
    },
  });
}

// Gestion de l'upload du logo
async function handleLogoUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Vérifier la taille (2 Mo max)
  if (file.size > 2 * 1024 * 1024) {
    alert("Le fichier est trop volumineux (2 Mo maximum)");
    event.target.value = "";
    return;
  }

  // Vérifier le type
  const allowedTypes = [
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/svg+xml",
  ];
  if (!allowedTypes.includes(file.type)) {
    alert("Format de fichier non autorisé. Utilisez PNG, JPG ou SVG.");
    event.target.value = "";
    return;
  }

  try {
    const formData = new FormData();
    formData.append("logo", file);

    const response = await fetch("/api/upload-logo", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (response.ok) {
      appState.logoPath = data.filepath;
      showLogoPreview(file);
      showSuccess("Logo téléchargé avec succès");
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur lors du téléchargement du logo: " + error.message);
    event.target.value = "";
  }
}

// Afficher l'aperçu du logo
function showLogoPreview(file) {
  const preview = document.getElementById("logo-preview");
  const img = document.getElementById("logo-preview-img");
  const uploadGroup = document
    .getElementById("logo-upload")
    .closest(".fr-upload-group");

  const reader = new FileReader();
  reader.onload = function (e) {
    img.src = e.target.result;
    preview.classList.remove("hidden");
    // Masquer tout le groupe d'upload (label + input + hint)
    uploadGroup.style.display = "none";
  };
  reader.readAsDataURL(file);
}

// Supprimer le logo
function removeLogo() {
  appState.logoPath = null;
  const uploadInput = document.getElementById("logo-upload");
  const uploadGroup = uploadInput.closest(".fr-upload-group");

  uploadInput.value = "";
  document.getElementById("logo-preview").classList.add("hidden");

  // Réafficher tout le groupe d'upload
  uploadGroup.style.display = "block";

  showSuccess("Logo supprimé");
}

// Chargement des tables
async function loadTables() {
  const apiUrl = document.getElementById("api-url").value;
  const apiToken = document.getElementById("api-token").value;
  const docId = document.getElementById("doc-id").value;

  if (!apiUrl || !apiToken || !docId) {
    alert("Veuillez remplir tous les champs de connexion");
    return;
  }

  try {
    showLoading("connect-btn");

    const response = await fetch("/api/tables", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        api_url: apiUrl,
        api_token: apiToken,
        doc_id: docId,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      populateTableSelect(data.tables);

      // Activer le select de table
      const tableSelect = document.getElementById("table-select");
      tableSelect.disabled = false;

      // Afficher le statut de connexion
      const connectionStatus = document.getElementById("connection-status");
      connectionStatus.classList.remove("hidden");

      showSuccess("Tables chargées avec succès");

      // NOUVEAU : Ne PAS effacer les colonnes si elles existent déjà
      // Cela permet de garder la sélection après chargement d'une config
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur de connexion : " + error.message);
  } finally {
    hideLoading("connect-btn");
  }
}

// Remplir le select des tables
function populateTableSelect(tables) {
  const select = document.getElementById("table-select");
  select.innerHTML = '<option value="">Sélectionnez une table</option>';

  tables.forEach((table) => {
    const option = document.createElement("option");
    option.value = table.id;
    option.textContent = table.id;
    select.appendChild(option);
  });
}

// Chargement des colonnes
async function loadColumns() {
  const tableId = document.getElementById("table-select").value;

  if (!tableId) {
    alert("Veuillez sélectionner une table");
    return;
  }

  try {
    showLoading("load-columns-btn");

    const response = await fetch(`/api/columns/${tableId}`);
    const data = await response.json();

    if (response.ok) {
      appState.columns = data.columns;
      populateColumnsList(data.columns);
      populateFilterColumn(data.columns);
      showSuccess("Colonnes chargées avec succès");

      // Actualiser le compteur de PDFs après chargement des colonnes
      setTimeout(() => updatePDFCount(), 500);
    } else {
      if (data.error && data.error.includes("non initialisé")) {
        throw new Error(
          "Veuillez d'abord cliquer sur 'Charger les tables' dans l'onglet Connexion"
        );
      }
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur de chargement des colonnes : " + error.message);
  } finally {
    hideLoading("load-columns-btn");
  }
}

// Remplir la liste des colonnes (drag & drop)
function populateColumnsList(columns) {
  const list = document.getElementById("sortable-columns");
  list.innerHTML = "";

  columns.forEach((col) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="drag-handle">☰</span>
      <input type="checkbox" id="col-${col}" value="${col}" class="fr-mr-2w" checked>
      <label for="col-${col}">${col}</label>
    `;
    list.appendChild(li);
  });

  // Ajouter les listeners
  list.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectedColumns);
  });

  updateSelectedColumns();
}

// Remplir le select de la colonne de filtrage
function populateFilterColumn(columns) {
  const select = document.getElementById("filter-column");
  select.innerHTML = '<option value="">Sélectionnez une colonne</option>';

  columns.forEach((col) => {
    const option = document.createElement("option");
    option.value = col;
    option.textContent = col;
    select.appendChild(option);
  });

  // Déclencher le compteur quand on change la colonne de filtrage
  select.addEventListener("change", updatePDFCount);
}

// Mettre à jour le compteur de PDFs
async function updatePDFCount() {
  const tableId = document.getElementById("table-select").value;
  const filterColumn = document.getElementById("filter-column").value;
  const advancedFilters = getAdvancedFilters();

  const indicator = document.getElementById("pdf-count-indicator");
  if (!tableId || !filterColumn) {
    indicator.style.display = "none";
    return;
  }

  try {
    const response = await fetch("/api/count-pdfs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        table_id: tableId,
        filter_column: filterColumn,
        advanced_filters: advancedFilters,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      const countNumber = document.getElementById("pdf-count-number");
      const countDetails = document.getElementById("pdf-count-details");

      countNumber.textContent = data.count;

      // Afficher le mode de filtre si des filtres sont actifs
      let modeInfo = "";
      if (advancedFilters.filters && advancedFilters.filters.length > 0) {
        const modeLabel = advancedFilters.mode === "or" ? "OU" : "ET";
        modeInfo = `<br/><span class="fr-text--xs" style="color: #0063CB;">🔍 Mode ${modeLabel} actif (${advancedFilters.filters.length} filtre(s))</span>`;
      }

      if (data.unique_values && data.unique_values.length > 0) {
        const preview = data.unique_values.slice(0, 5).join(", ");
        const more =
          data.unique_values.length > 5
            ? `, ... (+${data.unique_values.length - 5})`
            : "";

        const dateInfo = data.is_date_column
          ? '<br/><span class="fr-text--xs" style="color: #666;">📅 Colonne de dates détectée - Utilisez le format DD/MM/YYYY pour filtrer</span>'
          : "";

        countDetails.innerHTML = `<br/><span class="fr-text--xs">Valeurs: ${preview}${more}</span>${dateInfo}${modeInfo}`;
      } else {
        countDetails.innerHTML = modeInfo;
      }

      indicator.style.display = "block";
    } else {
      console.error("Erreur compteur:", data.error);
      if (
        data.error &&
        (data.error.includes("non initialisé") ||
          data.error.includes("not initialized"))
      ) {
        const countNumber = document.getElementById("pdf-count-number");
        const countDetails = document.getElementById("pdf-count-details");
        countNumber.textContent = "?";
        countDetails.innerHTML =
          '<br/><span class="fr-text--xs" style="color: #ce0500;">⚠️ Veuillez d\'abord charger les tables et colonnes</span>';
        indicator.style.display = "block";
      } else {
        indicator.style.display = "none";
      }
    }
  } catch (error) {
    console.error("Erreur lors du comptage:", error);
    indicator.style.display = "none";
  }
}

// Mettre à jour les colonnes sélectionnées
function updateSelectedColumns() {
  const checkboxes = document.querySelectorAll(
    '#sortable-columns input[type="checkbox"]:checked'
  );
  appState.selectedColumns = Array.from(checkboxes).map((cb) => cb.value);
}

// Sélectionner toutes les colonnes
function selectAllColumns() {
  document
    .querySelectorAll('#sortable-columns input[type="checkbox"]')
    .forEach((cb) => (cb.checked = true));
  updateSelectedColumns();
}

// Désélectionner toutes les colonnes
function deselectAllColumns() {
  document
    .querySelectorAll('#sortable-columns input[type="checkbox"]')
    .forEach((cb) => (cb.checked = false));
  updateSelectedColumns();
}

// Ajouter un filtre avancé
let filterIdCounter = 0;
function addAdvancedFilter() {
  filterIdCounter++;
  const filterId = `filter-${filterIdCounter}`;
  const container = document.getElementById("advanced-filters-container");

  const filterDiv = document.createElement("div");
  filterDiv.className = "filter-row fr-mb-3w";
  filterDiv.setAttribute("data-filter-id", filterId);

  filterDiv.innerHTML = `
    <div class="fr-grid-row fr-grid-row--gutters">
      <div class="fr-col-12 fr-col-md-4">
        <div class="fr-select-group">
          <label class="fr-label" for="filter-col-${filterId}">Colonne</label>
          <select class="fr-select" id="filter-col-${filterId}">
            ${appState.columns
              .map((col) => `<option value="${col}">${col}</option>`)
              .join("")}
          </select>
        </div>
      </div>
      <div class="fr-col-12 fr-col-md-3">
        <div class="fr-select-group">
          <label class="fr-label" for="filter-op-${filterId}">Opérateur</label>
          <select class="fr-select" id="filter-op-${filterId}">
            <option value="equals">Égal à</option>
            <option value="not_equals">Différent de</option>
            <option value="greater_than">Plus grand que</option>
            <option value="less_than">Plus petit que</option>
          </select>
        </div>
      </div>
      <div class="fr-col-12 fr-col-md-4">
        <div class="fr-input-group">
          <label class="fr-label" for="filter-val-${filterId}">Valeur</label>
          <input class="fr-input" type="text" id="filter-val-${filterId}">
        </div>
      </div>
      <div class="fr-col-12 fr-col-md-1">
        <button type="button" class="fr-btn fr-btn--secondary fr-btn--sm fr-mt-4w" onclick="removeFilter('${filterId}')">
          ✕
        </button>
      </div>
    </div>
  `;

  container.appendChild(filterDiv);

  // CORRECTION : Ne PAS actualiser automatiquement le compteur après ajout
  // L'utilisateur doit d'abord remplir les valeurs du filtre
  // setTimeout(() => updatePDFCount(), 100);
}

// Supprimer un filtre
function removeFilter(filterId) {
  const filterDiv = document.querySelector(`[data-filter-id="${filterId}"]`);
  if (filterDiv) {
    filterDiv.remove();
    // Actualiser le compteur après suppression
    setTimeout(() => updatePDFCount(), 100);
  }
}

// Récupérer les filtres avancés
function getAdvancedFilters() {
  const filters = [];
  const filterRows = document.querySelectorAll(".filter-row");

  // Récupérer le mode de combinaison
  const filterMode =
    document.querySelector('input[name="filter-mode"]:checked')?.value || "and";

  filterRows.forEach((row) => {
    const filterId = row.getAttribute("data-filter-id");
    const column = document.getElementById(`filter-col-${filterId}`).value;
    const operator = document.getElementById(`filter-op-${filterId}`).value;
    const value = document.getElementById(`filter-val-${filterId}`).value;

    if (column && operator && value) {
      filters.push({ column, operator, value });
    }
  });

  return {
    mode: filterMode,
    filters,
  };
}

// Gestion de l'upload de signature
async function handleSignatureUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (file.size > 5 * 1024 * 1024) {
    alert("Le fichier est trop volumineux (5 Mo maximum)");
    event.target.value = "";
    return;
  }

  const allowedTypes = ["image/png", "image/jpeg", "image/jpg"];
  if (!allowedTypes.includes(file.type)) {
    alert("Format de fichier non autorisé. Utilisez PNG, JPG ou JPEG.");
    event.target.value = "";
    return;
  }

  try {
    const formData = new FormData();
    formData.append("signature", file);

    const response = await fetch("/api/upload-signature", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (response.ok) {
      appState.signaturePath = data.filepath;
      showSignaturePreview(file);
      showSuccess("Signature téléchargée avec succès");
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError(
      "Erreur lors du téléchargement de la signature: " + error.message
    );
    event.target.value = "";
  }
}

// Afficher l'aperçu de la signature
function showSignaturePreview(file) {
  const preview = document.getElementById("signature-preview");
  const img = document.getElementById("signature-preview-img");
  const uploadGroup = document
    .getElementById("signature-upload")
    .closest(".fr-upload-group");

  const reader = new FileReader();
  reader.onload = function (e) {
    img.src = e.target.result;
    preview.classList.remove("hidden");
    // Masquer tout le groupe d'upload (label + input + hint)
    uploadGroup.style.display = "none";
  };
  reader.readAsDataURL(file);
}

// Supprimer la signature
function removeSignature() {
  appState.signaturePath = null;
  const uploadInput = document.getElementById("signature-upload");
  const uploadGroup = uploadInput.closest(".fr-upload-group");

  uploadInput.value = "";
  document.getElementById("signature-preview").classList.add("hidden");

  // Réafficher tout le groupe d'upload
  uploadGroup.style.display = "block";

  showSuccess("Signature supprimée");
}

// Export des PDFs
async function exportPDFs() {
  const tableId = document.getElementById("table-select").value;
  const filterColumn = document.getElementById("filter-column").value;
  const outputDir = document.getElementById("output-dir").value;
  const filenamePattern = document.getElementById("filename-pattern").value;
  const serviceName = document.getElementById("service-name").value;
  const signerFirstname = document.getElementById("signer-firstname").value;
  const signerName = document.getElementById("signer-name").value;
  const signerTitle = document.getElementById("signer-title").value;

  if (!tableId || !filterColumn || appState.selectedColumns.length === 0) {
    alert(
      "Veuillez sélectionner une table, une colonne de filtrage et au moins une colonne à inclure"
    );
    return;
  }

  if (!outputDir) {
    alert("Veuillez spécifier un dossier de destination");
    return;
  }

  const advancedFilters = getAdvancedFilters();

  // NOUVEAU : Debug - Vérifier le logo
  console.log("🖼️ Logo path avant export:", appState.logoPath);

  try {
    showLoading("export-btn");

    const exportData = {
      table_id: tableId,
      filter_column: filterColumn,
      selected_columns: appState.selectedColumns,
      output_dir: outputDir,
      filename_pattern: filenamePattern,
      service_name: serviceName,
      signer_firstname: signerFirstname,
      signer_name: signerName,
      signer_title: signerTitle,
      signature_path: appState.signaturePath,
      logo_path: appState.logoPath,
      advanced_filters: advancedFilters,
    };

    console.log("📤 Données d'export envoyées:", exportData);

    const response = await fetch("/api/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(exportData),
    });

    const data = await response.json();

    if (response.ok) {
      showExportResults(data);
      showSuccess(`${data.files_count} fichier(s) PDF généré(s) avec succès`);
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur lors de l'export : " + error.message);
  } finally {
    hideLoading("export-btn");
  }
}

// Afficher les résultats de l'export
function showExportResults(data) {
  const resultsDiv = document.getElementById("export-results");
  const messageP = document.getElementById("export-message");
  const filesList = document.getElementById("files-list");

  messageP.textContent = `${data.files_count} fichier(s) PDF généré(s)`;

  filesList.innerHTML =
    '<h4 class="fr-h6">Fichiers générés :</h4><ul class="fr-raw-list">';
  data.files.forEach((file) => {
    filesList.innerHTML += `
      <li class="fr-py-1w">
        <strong>${file.filename}</strong> - 
        Valeur: ${file.filter_value}, 
        ${file.records_count} enregistrement(s)
      </li>
    `;
  });
  filesList.innerHTML += "</ul>";

  resultsDiv.classList.remove("hidden");
  appState.lastExportedFiles = data.files;
}

// Upload des PDFs vers Grist
async function uploadPDFsToGrist() {
  if (!appState.lastExportedFiles || appState.lastExportedFiles.length === 0) {
    alert("Aucun fichier à uploader. Générez d'abord des PDFs.");
    return;
  }

  const tableId = document.getElementById("table-select").value;
  const filterColumn = document.getElementById("filter-column").value;
  const attachmentColumn = document.getElementById("attachment-column").value;

  if (!tableId || !filterColumn) {
    alert(
      "Informations manquantes. Assurez-vous d'avoir configuré la table et la colonne de filtrage."
    );
    return;
  }

  if (!attachmentColumn) {
    alert("Veuillez spécifier le nom de la colonne de pièces jointes.");
    return;
  }

  if (
    !confirm(
      `Uploader ${appState.lastExportedFiles.length} PDF(s) vers la colonne "${attachmentColumn}" dans Grist ?`
    )
  ) {
    return;
  }

  try {
    showLoading("upload-to-grist-btn");

    const response = await fetch("/api/upload-pdfs-to-grist", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        table_id: tableId,
        filter_column: filterColumn,
        attachment_column: attachmentColumn,
        pdf_files: appState.lastExportedFiles,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      showUploadResults(data);
      showSuccess(
        `${data.success_count} PDF(s) uploadé(s) vers Grist avec succès`
      );
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur lors de l'upload vers Grist : " + error.message);
  } finally {
    hideLoading("upload-to-grist-btn");
  }
}

// Afficher les résultats de l'upload vers Grist
function showUploadResults(data) {
  const uploadResultsDiv = document.getElementById("upload-results");

  let html = '<div class="fr-alert fr-alert--';
  html += data.error_count > 0 ? "warning" : "success";
  html += '">';
  html += `<h4 class="fr-alert__title">Upload terminé</h4>`;
  html += `<p>${data.success_count} PDF(s) uploadé(s) avec succès`;
  if (data.error_count > 0) {
    html += `, ${data.error_count} erreur(s)`;
  }
  html += `</p></div>`;

  if (data.results && data.results.length > 0) {
    html +=
      '<div class="fr-mt-2w"><h5 class="fr-h6">Détails :</h5><ul class="fr-raw-list">';

    data.results.forEach((result) => {
      const icon = result.success ? "✅" : "❌";
      const status = result.success
        ? `Record ID: ${result.record_id}, Attachment ID: ${result.attachment_id}`
        : `Erreur: ${result.error}`;

      html += `<li class="fr-py-1w">${icon} <strong>${result.filter_value}</strong> - ${status}</li>`;
    });

    html += "</ul></div>";
  }

  uploadResultsDiv.innerHTML = html;
  uploadResultsDiv.classList.remove("hidden");
}

// Utilitaires UI
function showLoading(buttonId) {
  const btn = document.getElementById(buttonId);
  if (!btn.dataset.originalText) {
    btn.dataset.originalText = btn.textContent;
  }
  btn.disabled = true;
  btn.textContent = "Chargement...";
}

function hideLoading(buttonId) {
  const btn = document.getElementById(buttonId);
  btn.disabled = false;
  if (btn.dataset.originalText) {
    btn.textContent = btn.dataset.originalText;
  }
}

function showSuccess(message) {
  console.log("✓ " + message);
  showToast(message, "success");
}

function showError(message) {
  console.error("✗ " + message);
  showToast("Erreur: " + message, "error");
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  const alertClass = type === "error" ? "fr-alert--error" : "fr-alert--success";
  toast.className = `fr-alert ${alertClass}`;
  toast.style.cssText =
    "position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px; background-color: white;";

  toast.innerHTML = `
    <h3 class="fr-alert__title">${type === "error" ? "Erreur" : "Succès"}</h3>
    <p>${message}</p>
  `;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

// ============================================
// Gestion des Configurations
// ============================================

async function saveConfiguration() {
  const configName = document.getElementById("config-name").value;

  if (!configName) {
    alert("Veuillez donner un nom à la configuration");
    return;
  }

  try {
    showLoading("save-config-btn");

    const configData = {
      config_name: configName,
      api_url: document.getElementById("api-url").value,
      doc_id: document.getElementById("doc-id").value,
      table_id: document.getElementById("table-select").value,
      filter_column: document.getElementById("filter-column").value,
      selected_columns: appState.selectedColumns,
      advanced_filters: getAdvancedFilters(),
      service_name: document.getElementById("service-name").value,
      signer_firstname: document.getElementById("signer-firstname").value,
      signer_name: document.getElementById("signer-name").value,
      signer_title: document.getElementById("signer-title").value,
      logo_path: appState.logoPath,
      signature_path: appState.signaturePath,
      output_dir: document.getElementById("output-dir").value,
      filename_pattern: document.getElementById("filename-pattern").value,
    };

    const response = await fetch("/api/config/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(configData),
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess(`Configuration "${configName}" sauvegardée avec succès`);
      document.getElementById("config-name").value = "";
      loadConfigurationsList();
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur lors de la sauvegarde : " + error.message);
  } finally {
    hideLoading("save-config-btn");
  }
}

// Charger la liste des configurations
async function loadConfigurationsList() {
  try {
    const response = await fetch("/api/config/list");
    const data = await response.json();

    const configsList = document.getElementById("configs-list");

    if (!response.ok) {
      throw new Error(data.error);
    }

    if (data.configs.length === 0) {
      configsList.innerHTML = `
        <div class="fr-alert fr-alert--info">
          <p>Aucune configuration sauvegardée pour le moment.</p>
          <p class="fr-text--sm">Allez dans l'onglet "Personnalisation" pour sauvegarder votre première configuration.</p>
        </div>
      `;
      return;
    }

    // Afficher les configurations
    let html = '<div class="fr-table fr-table--no-caption">';
    html += "<table><thead><tr>";
    html += "<th>Nom</th>";
    html += "<th>Table</th>";
    html += "<th>Date de création</th>";
    html += "<th>Actions</th>";
    html += "</tr></thead><tbody>";

    data.configs.forEach((config) => {
      const date = config.created_at
        ? new Date(config.created_at).toLocaleString("fr-FR")
        : "N/A";

      let badges = "";
      if (config.has_logo) {
        badges +=
          '<span class="fr-badge fr-badge--sm fr-badge--info fr-mr-1w">📷 Logo</span>';
      }
      if (config.has_signature) {
        badges +=
          '<span class="fr-badge fr-badge--sm fr-badge--info">✍️ Signature</span>';
      }

      html += `<tr>`;
      html += `<td><strong>${config.name}</strong><br/><span class="fr-text--xs">${badges}</span></td>`;
      html += `<td>${config.table_id || "N/A"}</td>`;
      html += `<td>${date}</td>`;
      html += `<td>`;
      html += `<button class="fr-btn fr-btn--sm fr-btn--icon-left fr-icon-download-line fr-mr-2w" onclick="loadConfiguration('${config.filename}')">Charger</button>`;
      html += `<button class="fr-btn fr-btn--sm fr-btn--secondary fr-btn--icon-left fr-icon-delete-line" onclick="deleteConfiguration('${config.filename}', '${config.name}')">Supprimer</button>`;
      html += `</td>`;
      html += `</tr>`;
    });

    html += "</tbody></table></div>";
    configsList.innerHTML = html;
  } catch (error) {
    showError(
      "Erreur lors du chargement des configurations : " + error.message
    );
  }
}

// Charger une configuration spécifique
async function loadConfiguration(filename) {
  if (
    !confirm(
      "Charger cette configuration ? Les paramètres actuels seront remplacés."
    )
  ) {
    return;
  }

  try {
    const response = await fetch(`/api/config/load/${filename}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error);
    }

    const config = data.config;

    // Connexion
    if (config.connection) {
      document.getElementById("api-url").value =
        config.connection.api_url || "";
      document.getElementById("doc-id").value = config.connection.doc_id || "";
    }

    // Table
    if (config.table && config.table.table_id) {
      const tableSelect = document.getElementById("table-select");
      if (tableSelect) {
        tableSelect.value = config.table.table_id;
        tableSelect.disabled = false;
      }

      // Colonne de filtrage
      if (config.table.filter_column) {
        setTimeout(() => {
          const filterCol = document.getElementById("filter-column");
          if (filterCol) {
            filterCol.value = config.table.filter_column;
          }
        }, 500);
      }

      // Colonnes sélectionnées - stocker et restaurer après chargement
      if (
        config.table.selected_columns &&
        config.table.selected_columns.length > 0
      ) {
        appState.selectedColumns = config.table.selected_columns;

        setTimeout(() => {
          const checkboxes = document.querySelectorAll(
            '#sortable-columns input[type="checkbox"]'
          );
          if (checkboxes.length === 0) {
            console.log(
              "⚠️ Colonnes pas encore chargées, cliquez sur 'Charger les colonnes'"
            );
          } else {
            checkboxes.forEach((cb) => {
              cb.checked = appState.selectedColumns.includes(cb.value);
            });
            updateSelectedColumns();
          }
        }, 1000);
      }
    }

    // Personnalisation
    if (config.customization) {
      document.getElementById("service-name").value =
        config.customization.service_name || "";
      document.getElementById("signer-firstname").value =
        config.customization.signer_firstname || "";
      document.getElementById("signer-name").value =
        config.customization.signer_name || "";
      document.getElementById("signer-title").value =
        config.customization.signer_title || "";

      // Logo
      const logoUploadGroup = document
        .getElementById("logo-upload")
        .closest(".fr-upload-group");
      const logoUploadInput = document.getElementById("logo-upload");
      logoUploadInput.value = "";
      logoUploadGroup.style.display = "block";

      if (config.customization.logo_path) {
        const logoPath = config.customization.logo_path.replace(/\\/g, "/");
        appState.logoPath = logoPath;
        const logoPreview = document.getElementById("logo-preview");
        const logoImg = document.getElementById("logo-preview-img");
        logoImg.src = "/" + logoPath;
        logoImg.onerror = function () {
          logoPreview.classList.add("hidden");
          logoUploadGroup.style.display = "block";
          appState.logoPath = null;
          showError(
            "Le fichier logo n'existe plus sur le serveur. Veuillez uploader un nouveau logo."
          );
        };
        logoImg.onload = function () {
          logoPreview.classList.remove("hidden");
          logoUploadGroup.style.display = "none";
        };
      } else {
        document.getElementById("logo-preview").classList.add("hidden");
        logoUploadGroup.style.display = "block";
        appState.logoPath = null;
      }

      // Signature
      const signatureUploadGroup = document
        .getElementById("signature-upload")
        .closest(".fr-upload-group");
      const signatureUploadInput = document.getElementById("signature-upload");
      signatureUploadInput.value = "";
      signatureUploadGroup.style.display = "block";

      if (config.customization.signature_path) {
        const signaturePath = config.customization.signature_path.replace(
          /\\/g,
          "/"
        );
        appState.signaturePath = signaturePath;
        const sigPreview = document.getElementById("signature-preview");
        const sigImg = document.getElementById("signature-preview-img");
        sigImg.src = "/" + signaturePath;
        sigImg.onerror = function () {
          sigPreview.classList.add("hidden");
          signatureUploadGroup.style.display = "block";
          appState.signaturePath = null;
          showError(
            "Le fichier signature n'existe plus sur le serveur. Veuillez uploader une nouvelle signature."
          );
        };
        sigImg.onload = function () {
          sigPreview.classList.remove("hidden");
          signatureUploadGroup.style.display = "none";
        };
      } else {
        document.getElementById("signature-preview").classList.add("hidden");
        signatureUploadGroup.style.display = "block";
        appState.signaturePath = null;
      }
    }

    // Export
    if (config.export) {
      document.getElementById("output-dir").value =
        config.export.output_dir || "";
      document.getElementById("filename-pattern").value =
        config.export.filename_pattern || "";
    }

    // Filtres avancés
    if (config.filters && config.filters.advanced_filters) {
      document.getElementById("advanced-filters-container").innerHTML = "";

      if (config.filters.advanced_filters.mode) {
        const modeRadio = document.querySelector(
          `input[name="filter-mode"][value="${config.filters.advanced_filters.mode}"]`
        );
        if (modeRadio) {
          modeRadio.checked = true;
        }
      }

      const filters =
        config.filters.advanced_filters.filters ||
        config.filters.advanced_filters;
      filters.forEach((filter) => {
        addAdvancedFilter();
        const lastFilter = document.querySelector(".filter-row:last-child");
        if (lastFilter) {
          const filterId = lastFilter.getAttribute("data-filter-id");
          document.getElementById(`filter-col-${filterId}`).value =
            filter.column || "";
          document.getElementById(`filter-op-${filterId}`).value =
            filter.operator || "";
          document.getElementById(`filter-val-${filterId}`).value =
            filter.value || "";
        }
      });
    }

    showSuccess(
      `Configuration "${config.config_name || filename}" chargée avec succès`
    );

    if (config.table?.table_id && config.table?.filter_column) {
      setTimeout(() => updatePDFCount(), 1000);
    }
  } catch (error) {
    showError("Erreur lors du chargement : " + error.message);
  }
}

// Supprimer une configuration
async function deleteConfiguration(filename, configName) {
  if (
    !confirm(
      `Êtes-vous sûr de vouloir supprimer la configuration "${configName}" ?`
    )
  ) {
    return;
  }

  try {
    const response = await fetch(`/api/config/delete/${filename}`, {
      method: "DELETE",
    });

    const data = await response.json();

    if (response.ok) {
      showSuccess(`Configuration supprimée`);
      loadConfigurationsList();
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    showError("Erreur lors de la suppression : " + error.message);
  }
}
