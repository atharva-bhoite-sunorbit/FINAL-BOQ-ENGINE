const fileInput = document.getElementById('drawing-file');
const generateBtn = document.getElementById('generate-btn');
const statusEl = document.getElementById('status');
const boqBody = document.getElementById('boq-body');
const materialsBody = document.getElementById('materials-body');
const itemCountEl = document.getElementById('item-count');
const materialCountEl = document.getElementById('material-count');
const grandTotalEl = document.getElementById('grand-total');
const materialCostEl = document.getElementById('material-cost');
const excelLink = document.getElementById('excel-download');
const pdfLink = document.getElementById('pdf-download');
const materialExcelLink = document.getElementById('material-excel-download');
const detailedBoqLink = document.getElementById('detailed-boq-download');
const rateGrid = document.getElementById('rate-grid');
const fileNameEl = document.getElementById('file-name');
const entityCountEl = document.getElementById('entity-count');
const layerCountEl = document.getElementById('layer-count');
const unitCountEl = document.getElementById('unit-count');
const elementCountEl = document.getElementById('element-count');
const referenceFileInput = document.getElementById('reference-file');
const validateButton = document.getElementById('validate-btn');
const validationBody = document.getElementById('validation-body');
const validationStatus = document.getElementById('validation-status');
const documentPanel = document.getElementById('document-panel');
const documentList = document.getElementById('document-list');
const documentCount = document.getElementById('document-count');

const elementsBody = document.getElementById('elements-body');
const elementsSummaryBadge = document.getElementById('elements-summary-badge');
const valBadge = document.getElementById('val-badge');
const valStatusTxt = document.getElementById('val-status-txt');
const valVersionTxt = document.getElementById('val-version-txt');
const valUnitsTxt = document.getElementById('val-units-txt');
const valExtentsTxt = document.getElementById('val-extents-txt');
const valLayersBlocksTxt = document.getElementById('val-layers-blocks-txt');
const valDimTextTxt = document.getElementById('val-dim-text-txt');
const valEntitiesTxt = document.getElementById('val-entities-txt');
const valHealthTxt = document.getElementById('val-health-txt');
const valEntityBreakdown = document.getElementById('val-entity-breakdown');

// Modal Elements (Traceability Section 25)
const traceModal = document.getElementById('trace-modal');
const modalClose = document.getElementById('modal-close');
const traceBoqItem = document.getElementById('trace-boq-item');
const traceMaterial = document.getElementById('trace-material');
const traceElement = document.getElementById('trace-element');
const traceHandle = document.getElementById('trace-handle');
const traceCoords = document.getElementById('trace-coords');
const traceDetailRows = document.getElementById('trace-detail-rows');

let currentDocId = null;
let processedDocuments = [];

fileInput.addEventListener('change', () => {
  fileNameEl.textContent = fileInput.files.length
    ? `${fileInput.files.length} drawing file(s) selected: ${[...fileInput.files].map(f => f.name).join(', ')}`
    : 'No drawing selected';
});

// Setup Tab Navigation
const tabButtons = document.querySelectorAll('.tab-btn, .nav-link');
const tabPanels = {
  boq: document.getElementById('boq-panel'),
  materials: document.getElementById('materials-panel'),
  elements: document.getElementById('elements-panel'),
  'validation-report': document.getElementById('validation-report-panel'),
  rates: document.getElementById('rates-panel'),
  validation: document.getElementById('validation-panel'),
};

function switchTab(targetTab) {
  tabButtons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === targetTab);
  });
  Object.entries(tabPanels).forEach(([key, panel]) => {
    if (panel) {
      panel.classList.toggle('hidden', key !== targetTab);
    }
  });
}

tabButtons.forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    if (btn.dataset.tab) {
      switchTab(btn.dataset.tab);
    }
  });
});

const rateDefaults = [
  ['RCC-021', 'RCC M25 Structural Concrete (cum)', 7100],
  ['SHU-001', 'Film-Faced Shuttering & Props (sqm)', 420],
  ['STR-022', 'TMT Fe 500D Rebar Steel (kg)', 68],
  ['AAC-009', 'AAC Block Masonry (cum)', 3800],
  ['ADH-002', 'Thin-Bed Adhesive Mortar IS:15477 (kg)', 15],
  ['CPL-011', 'Internal Cement Plaster 12/15mm (sqm)', 220],
  ['PLS-010', 'External Sand-Faced Plaster (sqm)', 380],
  ['GPR-012', 'Gypsum Plaster Finish (sqm)', 225],
  ['VFT-003', 'Vitrified Floor Tiles with Grout (sqm)', 950],
  ['SKR-018', 'Vitrified Tile Skirting 100mm (rmt)', 180],
  ['DOR-008', 'Flush Door with Frame & SS Hardware (unit)', 13000],
  ['ALU-036', 'Aluminium Glazed Sliding Windows (sqm)', 3800],
  ['GLP-001', 'Glass Aluminium Partition 10/12mm (sqm)', 1950],
  ['GYP-004', 'Gypsum Board Partition / Ceiling (sqm)', 850],
  ['PNT-007', 'Putty (2 coats) + Primer + Paint (sqm)', 120],
  ['EXT-051', 'External Weather-Proof Paint (sqm)', 145],
  ['WSR-017', 'Sanitary Package EWC + Basin (set)', 17500],
  ['ELE-043', 'Electrical Point Wiring in Conduit (point)', 1250],
  ['PLB-040', 'Plumbing CPVC Water Distribution (rmt)', 280],
  ['WTR-014', 'Water Tank & Supply Setup (unit)', 8700],
  ['ROF-015', 'Roofing & Waterproofing Screed (sqm)', 450],
];

rateDefaults.forEach(([code, label, value]) => {
  const field = document.createElement('label');
  field.className = 'rate-field';
  field.innerHTML = `<span>${label}<small>${code}</small></span><input data-rate-code="${code}" type="number" min="0" step="0.01" value="${value}" />`;
  rateGrid.appendChild(field);
});

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value || 0);
}

function renderBOQRows(items) {
  boqBody.innerHTML = '';
  (items || []).forEach((item, idx) => {
    const srNo = item.sr_no ?? item.item_no ?? (idx + 1);
    const code = item.code ?? item.element_type ?? '';
    const desc = item.description || item.material || '';
    const unit = item.unit || '';
    const drawQty = Number(item.drawing_quantity ?? item.gross_quantity ?? item.quantity ?? 0);
    const grossQty = Number(item.gross_quantity ?? item.quantity ?? 0);
    const opDed = Number(item.opening_deduction ?? item.deduction_quantity ?? 0);
    const netQty = Number(item.net_quantity ?? item.quantity ?? 0);
    const wastage = Number(item.wastage_pct ?? item.wastage_percent ?? 0);

    const isRebarRequired = item.status === 'STRUCTURAL_REBAR_DATA_REQUIRED' || item.final_quantity === null || item.total_quantity === null;

    let finalQtyDisplay = '';
    let amtDisplay = '';
    let rateDisplay = '';

    if (isRebarRequired) {
      finalQtyDisplay = `<span class="badge-pill warning" title="Strict Rule (Sec 23): Rebar quantities require structural schedule & BBS; not fabricated from architectural geometry.">⚠️ Schedule Required</span>`;
      amtDisplay = `<span class="badge-pill info">Rebar Data Req.</span>`;
      rateDisplay = '—';
    } else {
      const finalQty = Number(item.final_quantity ?? item.total_quantity ?? item.quantity ?? 0);
      const rate = Number(item.final_rate ?? item.rate ?? 0);
      const amt = Number(item.amount ?? (finalQty * rate));
      finalQtyDisplay = `<strong>${finalQty.toLocaleString('en-IN', {maximumFractionDigits: 2})}</strong>`;
      amtDisplay = `<strong>${formatCurrency(amt)}</strong>`;
      rateDisplay = formatCurrency(rate);
    }

    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${srNo}</td>
      <td><strong>${code}</strong></td>
      <td title="${item.calculation || item.calculation_basis || ''}">${desc}</td>
      <td>${unit}</td>
      <td>${isRebarRequired ? '—' : drawQty.toLocaleString('en-IN', {maximumFractionDigits: 2})}</td>
      <td>${isRebarRequired ? '—' : grossQty.toLocaleString('en-IN', {maximumFractionDigits: 2})}</td>
      <td style="color:${opDed > 0 ? '#b1432e' : 'inherit'}">${opDed > 0 ? '-' + opDed.toLocaleString('en-IN', {maximumFractionDigits: 2}) : '—'}</td>
      <td>${isRebarRequired ? '—' : netQty.toLocaleString('en-IN', {maximumFractionDigits: 2})}</td>
      <td>${wastage}%</td>
      <td>${finalQtyDisplay}</td>
      <td>${rateDisplay}</td>
      <td>${amtDisplay}</td>
      <td><button class="inspect-btn" data-boq-idx="${idx}">Inspect 🔍</button></td>
    `;
    boqBody.appendChild(row);
  });

  boqBody.querySelectorAll('.inspect-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.boqIdx);
      openTraceabilityModalForBOQ(items[idx]);
    });
  });
}

function renderMaterialRows(materials) {
  materialsBody.innerHTML = '';
  const mtoItems = materials.items || (Array.isArray(materials) ? materials : []);
  mtoItems.forEach((mat, idx) => {
    const srNo = mat.sr_no ?? (idx + 1);
    const code = mat.material_code ?? mat.material_id ?? '';
    const name = mat.material_name || mat.material || '';
    const cat = mat.category || 'General';
    const basis = mat.derived_from || mat.calculation_basis || '';
    const isRebarRequired = mat.status === 'STRUCTURAL_REBAR_DATA_REQUIRED' || mat.final_quantity === null || mat.total_quantity === null;

    const baseQty = Number(mat.base_quantity ?? mat.net_quantity ?? mat.quantity ?? 0);
    const baseUnit = mat.base_unit || mat.unit || '';
    const factor = mat.consumption_factor ?? 1.0;
    const wastage = Number(mat.wastage_percent ?? 0);
    const unit = mat.unit || '';
    const rate = Number(mat.unit_rate ?? mat.rate ?? 0);

    let finalQtyStr = '';
    let totalCostStr = '';
    let statusBadge = '';

    if (isRebarRequired) {
      finalQtyStr = `<span class="badge-pill warning">Schedule Required</span>`;
      totalCostStr = `—`;
      statusBadge = `<span class="badge-pill warning">Rebar Data Req.</span>`;
    } else {
      const finalQty = Number(mat.final_quantity ?? mat.total_quantity ?? mat.quantity ?? 0);
      const totalCost = Number(mat.total_cost ?? mat.amount ?? (finalQty * rate));
      finalQtyStr = `<strong>${finalQty.toLocaleString('en-IN', {maximumFractionDigits: 2})}</strong>`;
      totalCostStr = `<strong>${formatCurrency(totalCost)}</strong>`;
      statusBadge = `<span class="badge-pill success">Measured</span>`;
    }

    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${srNo}</td>
      <td><strong>${code}</strong></td>
      <td>${name}</td>
      <td><small>${cat}</small></td>
      <td><small title="${basis}">${basis}</small></td>
      <td>${isRebarRequired ? '—' : baseQty.toLocaleString('en-IN', {maximumFractionDigits: 2}) + ' ' + baseUnit}</td>
      <td>${factor}</td>
      <td>${wastage}%</td>
      <td>${finalQtyStr}</td>
      <td><strong>${unit}</strong></td>
      <td>${isRebarRequired ? '—' : formatCurrency(rate)}</td>
      <td>${totalCostStr}</td>
      <td>${statusBadge}</td>
    `;
    materialsBody.appendChild(row);
  });
}

function renderElementsRows(elements) {
  if (!elementsBody) return;
  elementsBody.innerHTML = '';
  (elements || []).forEach((el, idx) => {
    const elId = el.element_id || `EL-${idx + 1}`;
    const elType = el.element_type || 'UNKNOWN';
    const layer = el.layer || '0';
    const conf = Math.round((el.confidence_score || 0.95) * 100);
    const confClass = conf >= 90 ? 'success' : (conf >= 70 ? 'warning' : 'danger');

    let primaryQtyStr = '—';
    const q = el.quantities || {};
    if (q.volume) {
      primaryQtyStr = `${Number(q.volume).toFixed(2)} m³ (net)`;
    } else if (q.net_volume) {
      primaryQtyStr = `${Number(q.net_volume).toFixed(2)} m³`;
    } else if (q.net_area) {
      primaryQtyStr = `${Number(q.net_area).toFixed(2)} m²`;
    } else if (q.area) {
      primaryQtyStr = `${Number(q.area).toFixed(2)} m²`;
    } else if (q.centerline_length) {
      primaryQtyStr = `${Number(q.centerline_length).toFixed(2)} m (len)`;
    } else if (q.length) {
      primaryQtyStr = `${Number(q.length).toFixed(2)} m`;
    }

    const signalBadges = (el.signals || []).slice(0, 3).map(s => `<span class="signal-pill">${s}</span>`).join(' ');
    const handles = (el.source_entity_handles || []).slice(0, 4).map(h => `<span class="code-handle">${h}</span>`).join(' ');

    const assumptions = Object.entries(el.assumptions || {}).map(([k, v]) => `${k}: ${v}`).join('; ') || 'Standard';

    const row = document.createElement('tr');
    row.innerHTML = `
      <td><strong>${elId}</strong></td>
      <td><span class="badge-pill info">${elType}</span></td>
      <td><small>${layer}</small></td>
      <td><span class="badge-pill ${confClass}">${conf}%</span></td>
      <td><strong>${primaryQtyStr}</strong></td>
      <td>${signalBadges || '<small class="muted">—</small>'}</td>
      <td><small title="${assumptions}">${assumptions}</small></td>
      <td>${handles || '<small class="muted">—</small>'}</td>
      <td><button class="inspect-btn" data-el-idx="${idx}">Inspect 🔍</button></td>
    `;
    elementsBody.appendChild(row);
  });

  if (elementsSummaryBadge) {
    elementsSummaryBadge.textContent = `${(elements || []).length} construction elements classified deterministically`;
  }

  elementsBody.querySelectorAll('.inspect-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.elIdx);
      openTraceabilityModalForElement(elements[idx]);
    });
  });
}

function renderValidationReport(valReport, auditReport) {
  if (!valStatusTxt) return;
  const vr = valReport || {};
  const ar = auditReport || {};

  valStatusTxt.innerHTML = vr.is_valid_cad !== false
    ? `<span style="color:#23824c">✓ Valid CAD (${vr.file_format || 'CAD'})</span>`
    : `<span style="color:#b1432e">⚠ CAD Issues Detected</span>`;
  valVersionTxt.textContent = `AutoCAD Release: ${vr.acad_version || 'R2018 (AC1032)'}`;

  const u = vr.units || 'm';
  const scale = vr.unit_scale_to_meters || 1.0;
  valUnitsTxt.textContent = `${u.toUpperCase()} (Scale to m: ${scale})`;

  const bbox = vr.bounding_box || {};
  if (bbox.width && bbox.length) {
    valExtentsTxt.textContent = `Extents: ${bbox.width.toFixed(2)}m × ${bbox.length.toFixed(2)}m (Area: ${(bbox.width * bbox.length).toFixed(1)} m²)`;
  } else {
    valExtentsTxt.textContent = `3D: ${vr.is_3d ? 'Yes' : '2D Plan'}`;
  }

  valLayersBlocksTxt.textContent = `${vr.layers_count || ar.layers || 0} Layers · ${vr.blocks_count || ar.blocks || 0} Blocks`;
  valDimTextTxt.textContent = `${ar.dimensions || 0} Dimensions · ${ar.annotations || 0} Texts`;

  valEntitiesTxt.textContent = `${vr.total_entities || ar.entity_count || 0} Entities Parsed`;
  valHealthTxt.textContent = `${vr.corrupt_entities_count || 0} Corrupt (0 Discarded)`;

  if (valEntityBreakdown) {
    const counts = vr.entity_type_counts || ar.entities_by_type || {};
    valEntityBreakdown.innerHTML = Object.entries(counts).map(([type, cnt]) => `
      <div class="entity-box">
        <b>${type}</b>
        <span>${cnt}</span>
      </div>
    `).join('');
  }
}

function openTraceabilityModalForBOQ(item) {
  if (!traceModal) return;
  traceBoqItem.textContent = `${item.code || item.element_type || 'BOQ Item'} (#${item.sr_no || item.item_no})`;
  traceMaterial.textContent = item.material || item.description || 'Material';
  traceElement.textContent = (item.source_elements || ['—']).join(', ');
  traceHandle.textContent = (item.source_entities || ['—']).join(', ');
  traceCoords.textContent = item.layer || 'CAD Layer Extents';

  const rows = [
    ['Item Description', item.description || '—'],
    ['CSI / Specification Section', item.section || 'General'],
    ['Measurement Unit', item.unit || '—'],
    ['Gross Drawing Quantity', Number(item.gross_quantity || item.drawing_quantity || 0).toFixed(2)],
    ['Opening Deductions', item.opening_deduction > 0 ? `-${Number(item.opening_deduction).toFixed(2)}` : 'None'],
    ['Wastage Allowance', `${item.wastage_pct || item.wastage_percent || 0}% standard`],
    ['Final Payable Quantity', item.final_quantity !== null && item.final_quantity !== undefined ? Number(item.final_quantity).toFixed(2) : 'STRUCTURAL_REBAR_DATA_REQUIRED (Sec 23)'],
    ['Calculation Formula & Math Basis', item.calculation || item.calculation_basis || 'Deterministic formula'],
    ['Source Construction Elements', (item.source_elements || []).join(', ') || '—'],
    ['Source CAD Entity Handles', (item.source_entities || []).join(', ') || '—'],
    ['Audit Status & Confidence', `${item.status} (${Math.round((item.confidence || 0.95) * 100)}% confidence)`],
  ];

  traceDetailRows.innerHTML = rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');
  traceModal.classList.remove('hidden');
}

function openTraceabilityModalForElement(el) {
  if (!traceModal) return;
  traceBoqItem.textContent = el.element_type || 'Element';
  traceMaterial.textContent = (el.materials || ['Concrete / Masonry']).join(', ');
  traceElement.textContent = el.element_id || 'Element ID';
  traceHandle.textContent = (el.source_entity_handles || []).join(', ') || '—';
  traceCoords.textContent = `Layer: ${el.layer || '0'}`;

  const q = el.quantities || {};
  const assumptions = Object.entries(el.assumptions || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || 'Standard';

  const rows = [
    ['Element ID', el.element_id || '—'],
    ['Element Category', el.element_type || '—'],
    ['CAD Layer', el.layer || '0'],
    ['Confidence Score', `${Math.round((el.confidence_score || 0.95) * 100)}%`],
    ['Multi-Signal Detections', (el.signals || []).join(', ') || '—'],
    ['CAD Entity Handles', (el.source_entity_handles || []).join(', ') || 'AutoCAD DWG/DXF Entity'],
    ['Engineering Assumptions', assumptions],
    ['Formula & Mathematical Basis', q.formula || 'Geometric computation'],
    ['Geometric Dimensions', `L: ${q.length || q.centerline_length || '—'}m | W/Thick: ${q.thickness || '—'}m | H: ${q.height || '—'}m`],
    ['Computed Volume', q.volume ? `${Number(q.volume).toFixed(3)} m³` : '—'],
    ['Computed Area', q.area ? `${Number(q.area).toFixed(3)} m²` : '—'],
  ];

  traceDetailRows.innerHTML = rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');
  traceModal.classList.remove('hidden');
}

if (modalClose) {
  modalClose.addEventListener('click', () => {
    traceModal.classList.add('hidden');
  });
}
if (traceModal) {
  traceModal.addEventListener('click', (e) => {
    if (e.target === traceModal) {
      traceModal.classList.add('hidden');
    }
  });
}

function showDocument(result) {
  currentDocId = result.id;
  renderBOQRows(result.items);
  renderMaterialRows(result.materials || {});
  renderElementsRows(result.elements || result.parsed?.elements || []);
  renderValidationReport(result.validation_report || result.parsed?.validation_report, result.audit_report || result.parsed?.audit_report);

  itemCountEl.textContent = result.summary.item_count;
  materialCountEl.textContent = result.summary.materials_count || (result.materials?.items?.length || 0);
  grandTotalEl.textContent = formatCurrency(result.summary.grand_total);
  materialCostEl.textContent = formatCurrency(result.cost.material_cost);

  entityCountEl.textContent = result.parsed.entities?.length || '—';
  layerCountEl.textContent = result.parsed.layers?.length || '—';
  unitCountEl.innerHTML = `${result.parsed.units?.toUpperCase() || 'MM'}<br><small>scale: ${result.parsed.scale || '1:1'}</small>`;
  elementCountEl.textContent = (result.elements || result.parsed?.elements || []).length || Object.keys(result.parsed.classification || result.parsed.counts || {}).length;

  // Configure download links
  excelLink.href = `/api/download-excel/${currentDocId}`;
  excelLink.classList.remove('hidden');

  pdfLink.href = `/api/download-pdf/${currentDocId}`;
  pdfLink.classList.remove('hidden');

  materialExcelLink.href = `/api/download-materials-excel/${currentDocId}`;
  materialExcelLink.classList.remove('hidden');

  detailedBoqLink.href = `/api/download-excel/${currentDocId}`;
  detailedBoqLink.classList.remove('hidden');

  documentList.querySelectorAll('.document-choice').forEach((choice) => {
    choice.classList.toggle('active', choice.dataset.docId === result.id);
  });
}

function renderDocumentChoices(documents) {
  processedDocuments = documents;
  documentPanel.classList.toggle('hidden', documents.length === 0);
  documentCount.textContent = `${documents.length} file${documents.length === 1 ? '' : 's'} ready`;
  documentList.innerHTML = documents.map((doc) => `
    <button class="document-choice" data-doc-id="${doc.id}" type="button">
      <strong>${doc.filename}</strong>
      <small>${doc.summary.item_count} BOQ items · ${doc.summary.materials_count || 0} Materials · ${formatCurrency(doc.summary.grand_total)}</small>
    </button>`).join('');
  documentList.querySelectorAll('.document-choice').forEach((choice) => {
    choice.addEventListener('click', () => {
      const result = processedDocuments.find((doc) => doc.id === choice.dataset.docId);
      if (result) {
        showDocument(result);
        statusEl.textContent = `BOQ & Material Takeoff ready for ${result.filename}`;
      }
    });
  });
}

validateButton.addEventListener('click', async () => {
  if (!currentDocId || !referenceFileInput.files[0]) {
    validationStatus.textContent = 'Generate a BOQ and choose the matching reference Excel first.';
    return;
  }
  const validationForm = new FormData();
  validationForm.append('reference', referenceFileInput.files[0]);
  validationForm.append('doc_id', currentDocId);
  validationForm.append('tolerance_percent', '1');
  validationStatus.textContent = 'Comparing reference quantities with generated geometry...';
  const response = await fetch('/validate-boq', { method: 'POST', body: validationForm });
  const result = await response.json();
  if (!response.ok) {
    validationStatus.textContent = result.detail || 'Validation failed.';
    return;
  }
  validationBody.innerHTML = result.rows.map((row) => `
    <tr>
      <td>${row.item}</td><td>${row.reference_qty}</td><td>${row.generated_qty}</td>
      <td>${row.unit || ''}</td><td>${row.difference}</td><td>${row.difference_percent ?? '—'}%</td>
      <td class="${row.status === 'MATCH' ? 'match' : 'mismatch'}">${row.status}</td>
    </tr>`).join('');
  validationStatus.textContent = `${result.match_count} match(es), ${result.mismatch_count} mismatch(es).`;
});

generateBtn.addEventListener('click', async () => {
  const files = [...fileInput.files];
  if (!files.length) {
    statusEl.textContent = 'Please select a drawing file first.';
    return;
  }

  statusEl.textContent = 'Parsing DWG, computing geometry, materials & BOQ...';
  generateBtn.disabled = true;

  const formData = new FormData();
  if (files.length === 1) {
    formData.append('file', files[0]);
  } else {
    files.forEach((file) => formData.append('files', file));
  }
  const rates = {};
  rateGrid.querySelectorAll('input[data-rate-code]').forEach((input) => {
    rates[input.dataset.rateCode] = Number(input.value);
  });

  formData.append('rates', JSON.stringify(rates));

  try {
    const response = await fetch(files.length === 1 ? '/api/upload' : '/api/upload-batch', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const payload = await response.json();
    const documents = payload.documents || [payload];
    renderDocumentChoices(documents);
    showDocument(documents[0]);
    statusEl.textContent = `Success! ${documents.length} drawing${documents.length === 1 ? '' : 's'} parsed with exact material takeoff.`;
  } catch (error) {
    statusEl.textContent = error.message;
  } finally {
    generateBtn.disabled = false;
  }
});
