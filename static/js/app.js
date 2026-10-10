// State Management
let currentUser = null;
let currentRole = 'volunteer';
let currentView = 'login';
let html5QrCode = null;
let cameraActive = false;
let isProcessingScan = false;
let isScanCooldown = false;
let cooldownInterval = null;
const SCAN_COOLDOWN_MS = 4000;
let sessionStats = { scans: 0, admitted: 0, denied: 0 };
let searchDebounceTimer = null;
let adminPollInterval = null;

// ==================== AUDIO SYNTHESIZER ====================
class SoundManager {
    constructor() {
        this.ctx = null;
    }

    init() {
        if (!this.ctx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
        }
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    playGranted() {
        if (!document.getElementById('audioToggle')?.checked) return;
        this.init();
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);

        // Cheerful ascending chime
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.setValueAtTime(880.00, now + 0.08); // A5
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

        osc.start(now);
        osc.stop(now + 0.35);
    }

    playDenied() {
        if (!document.getElementById('audioToggle')?.checked) return;
        this.init();
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);

        // Harsh low double-buzz
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(150, now);
        osc.frequency.setValueAtTime(110, now + 0.12);
        gain.gain.setValueAtTime(0.4, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

        osc.start(now);
        osc.stop(now + 0.45);
    }

    playNotFound() {
        if (!document.getElementById('audioToggle')?.checked) return;
        this.init();
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(320, now);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

        osc.start(now);
        osc.stop(now + 0.25);
    }
}

const sounds = new SoundManager();

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    // Check saved session in sessionStorage
    const saved = sessionStorage.getItem('carnival_user');
    if (saved) {
        try {
            currentUser = JSON.parse(saved);
            updateUserNav();
            switchView(currentUser.role === 'admin' ? 'admin' : 'scanner');
        } catch (e) {
            sessionStorage.removeItem('carnival_user');
        }
    }

    // Global Escape key listener to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closePasswordModal();
            closeResetModal();
            closeVolunteerModal();
        }
    });

    // Barcode input enter listener
    const barcodeInput = document.getElementById('barcodeInput');
    if (barcodeInput) {
        barcodeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                processManualInput();
            }
        });
    }

    // Keep scanner input focused when in scanner view
    document.addEventListener('click', (e) => {
        if (currentView === 'scanner' && !cameraActive) {
            const isClickInsideInteractive = e.target.closest('button, a, input, select, textarea, .modal-card');
            if (!isClickInsideInteractive) {
                const inp = document.getElementById('barcodeInput');
                if (inp && !inp.disabled) inp.focus();
            }
        }
    });
});

function handleOverlayClick(e, modalId) {
    if (e.target && e.target.id === modalId) {
        if (modalId === 'passwordModal') closePasswordModal();
        else if (modalId === 'resetModal') closeResetModal();
        else if (modalId === 'volunteerModal') closeVolunteerModal();
    }
}

// ==================== AUTHENTICATION ====================
function setLoginRole(role) {
    const tabVol = document.getElementById('tabVolunteer');
    const tabAdm = document.getElementById('tabAdmin');
    const volFields = document.getElementById('volunteerFields');
    const admFields = document.getElementById('adminFields');
    const submitBtn = document.getElementById('loginSubmitBtn');

    if (role === 'volunteer') {
        tabVol.classList.add('active');
        tabAdm.classList.remove('active');
        volFields.classList.remove('hidden');
        admFields.classList.add('hidden');
        submitBtn.innerHTML = '<i class="fa-solid fa-barcode"></i> Launch Scanner Portal';
    } else {
        tabAdm.classList.add('active');
        tabVol.classList.remove('active');
        admFields.classList.remove('hidden');
        volFields.classList.add('hidden');
        submitBtn.innerHTML = '<i class="fa-solid fa-chart-line"></i> Access Admin Dashboard';
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const errorBox = document.getElementById('loginError');
    errorBox.classList.add('hidden');

    const isAdminTab = document.getElementById('tabAdmin').classList.contains('active');
    let payload = {};

    if (isAdminTab) {
        payload = {
            username: document.getElementById('adminUsername').value.trim(),
            password: document.getElementById('adminPassword').value.trim()
        };
    } else {
        const stationVal = document.getElementById('volunteerStation').value.trim() || 'Volunteer';
        payload = {
            username: stationVal,
            volunteer_name: stationVal,
            password: document.getElementById('volunteerPasscode').value.trim() || 'pass'
        };
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            currentUser = data;
            sessionStorage.setItem('carnival_user', JSON.stringify(currentUser));
            updateUserNav();
            showToast(`Welcome, ${currentUser.name}!`, 'success');
            switchView(currentUser.role === 'admin' ? 'admin' : 'scanner');
        } else {
            errorBox.textContent = data.message || 'Login failed';
            errorBox.classList.remove('hidden');
        }
    } catch (err) {
        errorBox.textContent = 'Server connection error. Please try again.';
        errorBox.classList.remove('hidden');
    }
}

function updateUserNav() {
    const userBadge = document.getElementById('userInfoBadge');
    const roleBadge = document.getElementById('userRoleBadge');
    const nameDisplay = document.getElementById('userNameDisplay');
    const navScanner = document.getElementById('navScannerBtn');
    const navAdmin = document.getElementById('navAdminBtn');
    const navLogout = document.getElementById('navLogoutBtn');

    if (currentUser) {
        userBadge.classList.remove('hidden');
        roleBadge.textContent = currentUser.role.toUpperCase();
        nameDisplay.textContent = currentUser.name;
        navScanner.classList.remove('hidden');
        navLogout.classList.remove('hidden');

        if (currentUser.role === 'admin') {
            navAdmin.classList.remove('hidden');
        } else {
            navAdmin.classList.add('hidden');
        }
    } else {
        userBadge.classList.add('hidden');
        navScanner.classList.add('hidden');
        navAdmin.classList.add('hidden');
        navLogout.classList.add('hidden');
    }
}

function logout() {
    if (cameraActive) {
        stopCameraScanner();
    }
    if (adminPollInterval) {
        clearInterval(adminPollInterval);
    }
    currentUser = null;
    sessionStorage.removeItem('carnival_user');
    updateUserNav();
    switchView('login');
    showToast('Logged out successfully', 'info');
}

// ==================== VIEW SWITCHING ====================
function switchView(viewName) {
    currentView = viewName;

    // View sections
    document.getElementById('loginView').classList.add('hidden');
    document.getElementById('scannerView').classList.add('hidden');
    document.getElementById('adminView').classList.add('hidden');

    // Nav active buttons
    document.getElementById('navScannerBtn')?.classList.remove('active');
    document.getElementById('navAdminBtn')?.classList.remove('active');

    if (viewName === 'login') {
        document.getElementById('loginView').classList.remove('hidden');
        if (adminPollInterval) clearInterval(adminPollInterval);
    } else if (viewName === 'scanner') {
        document.getElementById('scannerView').classList.remove('hidden');
        document.getElementById('navScannerBtn')?.classList.add('active');
        if (adminPollInterval) clearInterval(adminPollInterval);

        // Auto-focus barcode input
        setTimeout(() => {
            const inp = document.getElementById('barcodeInput');
            if (inp) inp.focus();
        }, 150);
    } else if (viewName === 'admin') {
        document.getElementById('adminView').classList.remove('hidden');
        document.getElementById('navAdminBtn')?.classList.add('active');
        if (cameraActive) stopCameraScanner();

        // Load admin data and start polling
        fetchAdminStats();
        fetchStudentsTable();
        if (adminPollInterval) clearInterval(adminPollInterval);
        adminPollInterval = setInterval(fetchAdminStats, 4000);
    }
}

// ==================== 4-SECOND COOLDOWN & SCANNER LOGIC ====================
function startScanCooldown(durationMs = 4000) {
    if (cooldownInterval) clearInterval(cooldownInterval);
    isScanCooldown = true;

    // Pause camera scanning if active to prevent continuous frame hits
    if (html5QrCode && cameraActive) {
        try { html5QrCode.pause(); } catch(e) {}
    }

    const banner = document.getElementById('scanCooldownBanner');
    const timerText = document.getElementById('cooldownTimerText');
    const bar = document.getElementById('cooldownProgressBar');
    const input = document.getElementById('barcodeInput');
    const checkBtn = document.querySelector('.btn-scan');

    if (banner) banner.classList.remove('hidden');
    if (input) {
        input.disabled = true;
        input.placeholder = '🔒 4s cooldown active: Waiting before next scan...';
    }
    if (checkBtn) {
        checkBtn.classList.add('btn-cooldown');
        checkBtn.title = '4-second cooldown active';
    }

    const startTime = Date.now();
    const endTime = startTime + durationMs;

    cooldownInterval = setInterval(() => {
        const remaining = Math.max(0, endTime - Date.now());
        const seconds = (remaining / 1000).toFixed(1);

        if (timerText) timerText.textContent = `${seconds}s`;
        if (bar) {
            const pct = (remaining / durationMs) * 100;
            bar.style.width = `${pct}%`;
        }

        if (remaining <= 0) {
            clearInterval(cooldownInterval);
            cooldownInterval = null;
            isScanCooldown = false;

            if (banner) banner.classList.add('hidden');
            if (input) {
                input.disabled = false;
                input.value = '';
                input.placeholder = 'Scan Barcode with Gun OR Type ID (e.g. 26413, A11101)...';
                input.focus();
            }
            if (checkBtn) {
                checkBtn.classList.remove('btn-cooldown');
                checkBtn.title = 'Check Barcode';
            }

            // Resume camera scanning if enabled
            if (html5QrCode && cameraActive) {
                try { html5QrCode.resume(); } catch(e) {}
            }
        }
    }, 50);
}

function processManualInput() {
    if (isScanCooldown) {
        showToast('⏳ Anti-duplicate shield: Please wait for the 4s cooldown before checking another pass.', 'info');
        return;
    }
    const input = document.getElementById('barcodeInput');
    const val = input ? input.value.trim() : '';
    if (!val) {
        showToast('Please enter or scan a barcode pass ID first.', 'info');
        if (input && !input.disabled) input.focus();
        return;
    }
    executeScan(val);
    input.value = '';
}

async function executeScan(barcode) {
    if (isScanCooldown) {
        showToast('⏳ Cooldown active: Please wait 4s between student passes.', 'info');
        return;
    }
    if (isProcessingScan) return;
    isProcessingScan = true;

    try {
        const payload = {
            barcode: barcode,
            volunteer: currentUser ? currentUser.name : 'Gate Volunteer'
        };

        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (res.status === 429 || data.status === 'COOLDOWN_ACTIVE') {
            showToast(data.message || 'Please wait before scanning again.', 'info');
            const waitMs = data.cooldown_remaining ? Math.round(data.cooldown_remaining * 1000) : 4000;
            startScanCooldown(waitMs);
            return;
        }

        handleScanResult(data, barcode);

        // Enforce 4-second delay before scanning next pass
        startScanCooldown(4000);
    } catch (err) {
        showToast('Error communicating with verification server', 'error');
    } finally {
        isProcessingScan = false;
    }
}


function handleScanResult(res, rawBarcode) {
    sessionStats.scans++;
    document.getElementById('sessionScanCount').textContent = sessionStats.scans;

    const hero = document.getElementById('scanResultHero');
    const heroIcon = document.getElementById('heroIcon');
    const heroTitle = document.getElementById('heroTitle');
    const heroSubtitle = document.getElementById('heroSubtitle');

    const detailCard = document.getElementById('studentDetailCard');
    const dupBox = document.getElementById('duplicateAlertBox');

    hero.className = 'scan-hero'; // reset classes

    if (res.status === 'GRANTED') {
        // ========== 1. SUCCESS / GRANTED ==========
        sounds.playGranted();
        sessionStats.admitted++;
        document.getElementById('sessionAdmittedCount').textContent = sessionStats.admitted;

        hero.classList.add('granted');
        heroIcon.className = 'fa-solid fa-circle-check';
        heroTitle.textContent = 'ACCESS GRANTED';
        heroSubtitle.textContent = `Valid pass verified! Welcome ${res.student.name}`;

        // Populate detail card
        detailCard.classList.remove('hidden');
        dupBox.classList.add('hidden');

        document.getElementById('cardStudentName').textContent = res.student.name;
        document.getElementById('cardCollegeBadge').textContent = res.student.college;
        document.getElementById('cardDivisionBadge').textContent = `DIV: ${res.student.division || '-'}`;
        document.getElementById('cardBarcodeBadge').textContent = `BARCODE: ${res.student.barcode}`;

        const statusPill = document.getElementById('cardStatusPill');
        statusPill.className = 'status-pill status-granted';
        statusPill.innerHTML = '<i class="fa-solid fa-circle-check"></i> ADMITTED';

        document.getElementById('cardEntryTimestamp').textContent = `${res.student.entry_date} • ${res.student.entry_time}`;
        document.getElementById('cardVolunteer').textContent = res.student.volunteer;
        document.getElementById('cardPermission').textContent = 'Valid (First Check-in)';
        document.getElementById('cardPermission').className = 'meta-value text-success';

        addRecentScanItem(res.student.name, res.student.college, res.student.barcode, 'GRANTED', res.student.entry_time);

    } else if (res.status === 'DUPLICATE_DENIED') {
        // ========== 2. SECOND ENTRY DENIED ==========
        sounds.playDenied();
        sessionStats.denied++;
        document.getElementById('sessionDeniedCount').textContent = sessionStats.denied;

        hero.classList.add('duplicate');
        heroIcon.className = 'fa-solid fa-ban';
        heroTitle.textContent = 'SECOND ENTRY DENIED';
        heroSubtitle.textContent = 'This pass has already been checked in. Do not admit student!';

        // Populate detail card with warning
        detailCard.classList.remove('hidden');
        dupBox.classList.remove('hidden');

        document.getElementById('cardStudentName').textContent = res.student.name;
        document.getElementById('cardCollegeBadge').textContent = res.student.college;
        document.getElementById('cardDivisionBadge').textContent = `DIV: ${res.student.division || '-'}`;
        document.getElementById('cardBarcodeBadge').textContent = `BARCODE: ${res.student.barcode}`;

        const statusPill = document.getElementById('cardStatusPill');
        statusPill.className = 'status-pill status-denied';
        statusPill.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> ENTRY REJECTED';

        document.getElementById('cardEntryTimestamp').textContent = `${res.first_entry.date} • ${res.first_entry.time}`;
        document.getElementById('cardVolunteer').textContent = res.first_entry.volunteer;
        document.getElementById('cardPermission').textContent = 'DENIED (Duplicate Entry Attempt)';
        document.getElementById('cardPermission').className = 'meta-value text-danger';

        document.getElementById('dupFirstTime').textContent = `First Admitted: ${res.first_entry.date} at ${res.first_entry.time}`;
        document.getElementById('dupFirstVol').textContent = `Processed At: ${res.first_entry.volunteer}`;

        addRecentScanItem(res.student.name, res.student.college, res.student.barcode, 'DUPLICATE', 'Blocked');

    } else {
        // ========== 3. NOT FOUND ==========
        sounds.playNotFound();
        sessionStats.denied++;
        document.getElementById('sessionDeniedCount').textContent = sessionStats.denied;

        hero.classList.add('notfound');
        heroIcon.className = 'fa-solid fa-triangle-exclamation';
        heroTitle.textContent = 'BARCODE NOT FOUND';
        heroSubtitle.textContent = `Barcode [${rawBarcode}] is not registered in the database`;

        detailCard.classList.add('hidden');
        addRecentScanItem('Unknown Barcode', 'N/A', rawBarcode, 'NOT_FOUND', 'Failed');
    }
}

function addRecentScanItem(name, college, barcode, status, time) {
    const list = document.getElementById('recentScansList');
    const empty = list.querySelector('.empty-state');
    if (empty) empty.remove();

    const item = document.createElement('div');
    const statusClass = status === 'GRANTED' ? 'granted' : (status === 'DUPLICATE' ? 'duplicate' : 'notfound');
    item.className = `recent-item ${statusClass}`;

    item.innerHTML = `
        <div class="recent-main">
            <strong>${name}</strong>
            <span>${college} • ${barcode}</span>
        </div>
        <div class="recent-time">
            ${status === 'GRANTED' ? '<i class="fa-solid fa-check text-success"></i>' : '<i class="fa-solid fa-xmark text-danger"></i>'} ${time}
        </div>
    `;

    list.insertBefore(item, list.firstChild);

    // Keep max 25 items
    while (list.children.length > 25) {
        list.removeChild(list.lastChild);
    }

    document.getElementById('liveFeedCount').textContent = list.children.length;
}

// ==================== CAMERA SCANNER ====================
function toggleCameraScanner() {
    if (cameraActive) {
        stopCameraScanner();
    } else {
        startCameraScanner();
    }
}

function startCameraScanner() {
    const cameraBox = document.getElementById('cameraBox');
    const btnText = document.getElementById('cameraBtnText');
    cameraBox.classList.remove('hidden');

    if (typeof Html5Qrcode === 'undefined') {
        showToast('Camera barcode library loading, please wait...', 'info');
        return;
    }

    html5QrCode = new Html5Qrcode("reader");
    const config = {
        fps: 15,
        qrbox: { width: 300, height: 180 },
        aspectRatio: 1.777778
    };

    html5QrCode.start(
        { facingMode: "environment" },
        config,
        (decodedText) => {
            // Success scan - strictly check both processing flag and 4-second cooldown
            if (!isProcessingScan && !isScanCooldown) {
                executeScan(decodedText);
            }
        },
        (errorMessage) => {
            // Ignore frame parse errors
        }
    ).then(() => {
        cameraActive = true;
        btnText.textContent = 'Disable Camera Scanner';
        document.getElementById('cameraToggleBtn').classList.add('btn-primary');
    }).catch((err) => {
        cameraBox.classList.add('hidden');
        showToast('Unable to start camera: ' + err, 'error');
    });
}

function stopCameraScanner() {
    if (html5QrCode && cameraActive) {
        html5QrCode.stop().then(() => {
            html5QrCode.clear();
            document.getElementById('cameraBox').classList.add('hidden');
            document.getElementById('cameraBtnText').textContent = 'Enable Camera Scanner';
            document.getElementById('cameraToggleBtn').classList.remove('btn-primary');
            cameraActive = false;
        }).catch(err => console.error(err));
    }
}

// ==================== ADMIN PANEL ====================
async function fetchAdminStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        // Metrics
        document.getElementById('adminTotalRegistered').textContent = data.total;
        document.getElementById('adminTotalEntered').textContent = data.entered;
        document.getElementById('adminTotalPending').textContent = data.pending;
        document.getElementById('adminAttendanceRate').textContent = `${data.percentage}% Checked In`;
        document.getElementById('adminProgressBar').style.width = `${data.percentage}%`;

        // Colleges
        const imed = data.colleges.DYPIMED || {};
        document.getElementById('dypimedEntered').textContent = imed.entered || 0;
        document.getElementById('dypimedPending').textContent = imed.pending || 0;
        document.getElementById('dypimedPct').textContent = `${imed.percentage || 0}%`;

        const coei = data.colleges.DYPCOEI || {};
        document.getElementById('dypcoeiEntered').textContent = coei.entered || 0;
        document.getElementById('dypcoeiPending').textContent = coei.pending || 0;
        document.getElementById('dypcoeiPct').textContent = `${coei.percentage || 0}%`;

        const tc = data.colleges.DYPTC || {};
        document.getElementById('dyptcEntered').textContent = tc.entered || 0;
        document.getElementById('dyptcPending').textContent = tc.pending || 0;
        document.getElementById('dyptcPct').textContent = `${tc.percentage || 0}%`;

        const soa = data.colleges.DYPSOA || {};
        const soaEnt = document.getElementById('dypsoaEntered');
        const soaPend = document.getElementById('dypsoaPending');
        const soaPct = document.getElementById('dypsoaPct');
        if (soaEnt) soaEnt.textContent = soa.entered || 0;
        if (soaPend) soaPend.textContent = soa.pending || 0;
        if (soaPct) soaPct.textContent = `${soa.percentage || 0}%`;

    } catch (err) {
        console.error('Failed to fetch admin stats:', err);
    }
}


function debounceSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(fetchStudentsTable, 300);
}

async function fetchStudentsTable() {
    const college = document.getElementById('filterCollege').value;
    const status = document.getElementById('filterStatus').value;
    const search = document.getElementById('adminSearchInput').value.trim();

    const tbody = document.getElementById('studentsTableBody');

    try {
        const params = new URLSearchParams({ college, status, search });
        const res = await fetch(`/api/students?${params.toString()}`);
        const data = await res.json();

        document.getElementById('tableRecordCount').textContent = `Showing ${data.students.length} of ${data.count} matches`;

        if (!data.students || data.students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No student records match the filters</td></tr>';
            return;
        }

        tbody.innerHTML = data.students.map(s => {
            const isEntered = s.status === 'ENTERED';
            const statusBadge = isEntered
                ? '<span class="badge-table badge-entered"><i class="fa-solid fa-check"></i> ENTERED</span>'
                : '<span class="badge-table badge-pending">PENDING</span>';

            const actionBtn = isEntered
                ? `<button class="btn btn-ghost btn-xs text-danger" onclick="undoCheckin('${s.barcode}')" title="Reset this student to Pending"><i class="fa-solid fa-rotate-left"></i> Undo</button>`
                : `<button class="btn btn-primary btn-xs" onclick="manualCheckin('${s.barcode}')" title="Manually check-in"><i class="fa-solid fa-user-check"></i> Check-in</button>`;

            return `
                <tr>
                    <td><code>${s.barcode}</code></td>
                    <td><strong>${s.name}</strong></td>
                    <td><span class="badge badge-college">${s.college}</span></td>
                    <td>${s.division || '-'} / ${s.roll_no || '-'}</td>
                    <td>${statusBadge}</td>
                    <td>${isEntered ? `${s.entry_date} ${s.entry_time}` : '-'}</td>
                    <td>${s.volunteer || '-'}</td>
                    <td>${actionBtn}</td>
                </tr>
            `;
        }).join('');

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Failed to load student records</td></tr>';
    }
}

async function manualCheckin(barcode) {
    if (!confirm(`Confirm manual entry validation for barcode: ${barcode}?`)) return;

    try {
        const res = await fetch('/api/manual-checkin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ barcode, volunteer: currentUser ? currentUser.name : 'Admin Override' })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            fetchStudentsTable();
            fetchAdminStats();
        } else {
            showToast(data.message, 'error');
        }
    } catch (err) {
        showToast('Error executing check-in', 'error');
    }
}

async function undoCheckin(barcode) {
    if (!confirm(`Are you sure you want to reset entry status for barcode ${barcode} back to PENDING?`)) return;

    try {
        const res = await fetch('/api/undo-checkin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ barcode })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'info');
            fetchStudentsTable();
            fetchAdminStats();
        } else {
            showToast(data.message, 'error');
        }
    } catch (err) {
        showToast('Error undoing check-in', 'error');
    }
}

// ==================== INTERACTIVE QUICK FILTERS ====================
function filterByCollege(college) {
    const select = document.getElementById('filterCollege');
    if (select) {
        select.value = college;
        fetchStudentsTable();
        showToast(`Filtered by ${college}`, 'info');
        const tableCard = document.querySelector('.table-card');
        if (tableCard) {
            tableCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

function filterByStatus(status) {
    const select = document.getElementById('filterStatus');
    if (select) {
        select.value = status;
        if (status === 'ALL') {
            const colSelect = document.getElementById('filterCollege');
            if (colSelect) colSelect.value = 'ALL';
        }
        fetchStudentsTable();
        const label = status === 'ALL' ? 'All Registered' : (status === 'ENTERED' ? 'Entered Students' : 'Pending Arrival');
        showToast(`Filtered by ${label}`, 'info');
        const tableCard = document.querySelector('.table-card');
        if (tableCard) {
            tableCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
}

// ==================== VOLUNTEER MANAGEMENT ====================
async function openVolunteerModal() {
    const modal = document.getElementById('volunteerModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.getElementById('volNewUsername').value = '';
    document.getElementById('volNewName').value = '';
    document.getElementById('volNewPassword').value = '';
    const alertBox = document.getElementById('volunteerAddAlert');
    if (alertBox) alertBox.classList.add('hidden');
    fetchVolunteersList();
}

function closeVolunteerModal() {
    const modal = document.getElementById('volunteerModal');
    if (modal) modal.classList.add('hidden');
}

async function fetchVolunteersList() {
    const container = document.getElementById('volunteersListContainer');
    const badge = document.getElementById('volunteerCountBadge');
    if (!container) return;

    try {
        const res = await fetch('/api/admin/volunteers');
        const data = await res.json();

        if (!data.success || !data.volunteers) {
            container.innerHTML = '<div class="text-center py-3 text-danger">Failed to load volunteers</div>';
            return;
        }

        const vols = data.volunteers;
        if (badge) badge.textContent = `${vols.length} Accounts`;

        if (vols.length === 0) {
            container.innerHTML = '<div class="text-center py-3 text-muted">No volunteer accounts registered.</div>';
            return;
        }

        container.innerHTML = vols.map(v => {
            const isAdmin = v.username === 'admin';
            const rolePill = isAdmin 
                ? '<span class="role-pill-admin"><i class="fa-solid fa-shield"></i> Admin</span>'
                : '<span class="role-pill-vol"><i class="fa-solid fa-user-check"></i> Volunteer</span>';

            const deleteAction = isAdmin 
                ? '<span class="system-tag"><i class="fa-solid fa-lock"></i> Protected</span>'
                : `<button type="button" class="btn btn-danger btn-xs" onclick="deleteVolunteer('${v.username}')" title="Remove Volunteer Account"><i class="fa-solid fa-trash-can"></i> Remove</button>`;

            return `
                <div class="volunteer-row-card">
                    <div class="vol-info-group">
                        <div class="vol-icon ${isAdmin ? 'admin-theme' : 'vol-theme'}">
                            <i class="fa-solid ${isAdmin ? 'fa-user-shield' : 'fa-id-badge'}"></i>
                        </div>
                        <div class="vol-names">
                            <strong>${v.name || v.username}</strong>
                            <span class="vol-uname"><i class="fa-solid fa-at"></i>${v.username}</span>
                        </div>
                    </div>
                    <div class="vol-role-group">
                        ${rolePill}
                    </div>
                    <div class="vol-actions-group">
                        <button type="button" class="btn btn-secondary btn-xs" onclick="quickUpdateVolunteerPassword('${v.username}')" title="Reset this volunteer's password">
                            <i class="fa-solid fa-key"></i> Reset Pass
                        </button>
                        ${deleteAction}
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        container.innerHTML = '<div class="text-center py-3 text-danger">Error loading volunteers</div>';
    }
}

async function executeAddVolunteer(e) {
    e.preventDefault();
    const username = document.getElementById('volNewUsername').value.trim();
    const name = document.getElementById('volNewName').value.trim();
    const password = document.getElementById('volNewPassword').value.trim();
    const alertBox = document.getElementById('volunteerAddAlert');
    const submitBtn = document.getElementById('addVolunteerBtn');

    if (alertBox) alertBox.classList.add('hidden');

    if (!username || !password) {
        if (alertBox) {
            alertBox.textContent = 'Username and password are required.';
            alertBox.classList.remove('hidden');
        }
        return;
    }

    if (password.length < 4) {
        if (alertBox) {
            alertBox.textContent = 'Password must be at least 4 characters long.';
            alertBox.classList.remove('hidden');
        }
        return;
    }

    const origHtml = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';

    try {
        const res = await fetch('/api/admin/volunteers/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, name, password })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            document.getElementById('volNewUsername').value = '';
            document.getElementById('volNewName').value = '';
            document.getElementById('volNewPassword').value = '';
            fetchVolunteersList();
        } else {
            if (alertBox) {
                alertBox.textContent = data.message || 'Error adding volunteer';
                alertBox.classList.remove('hidden');
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.textContent = 'Server error while adding volunteer';
            alertBox.classList.remove('hidden');
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = origHtml;
    }
}

async function deleteVolunteer(username) {
    if (!confirm(`Are you sure you want to remove volunteer account '@${username}'?`)) return;

    try {
        const res = await fetch('/api/admin/volunteers/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'info');
            fetchVolunteersList();
        } else {
            showToast(data.message || 'Failed to remove volunteer', 'error');
        }
    } catch (err) {
        showToast('Error removing volunteer', 'error');
    }
}

async function quickUpdateVolunteerPassword(username) {
    const newPass = prompt(`Set new password for volunteer '@${username}' (minimum 4 characters):`);
    if (newPass === null) return;
    const cleanPass = newPass.trim();
    if (!cleanPass || cleanPass.length < 4) {
        showToast('Password must be at least 4 characters long', 'error');
        return;
    }

    try {
        const res = await fetch('/api/admin/volunteers/update-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, new_password: cleanPass })
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            fetchVolunteersList();
        } else {
            showToast(data.message || 'Failed to update password', 'error');
        }
    } catch (err) {
        showToast('Error updating password', 'error');
    }
}

async function populatePasswordTargetUsers() {
    try {
        const res = await fetch('/api/admin/volunteers');
        const data = await res.json();
        if (data.success && data.volunteers) {
            const select = document.getElementById('pwdTargetUser');
            if (select) {
                const prev = select.value || 'admin';
                select.innerHTML = data.volunteers.map(v => 
                    `<option value="${v.username}">${v.name || v.username} (${v.username})</option>`
                ).join('');
                if (data.volunteers.some(v => v.username === prev)) {
                    select.value = prev;
                }
            }
        }
    } catch (e) {}
}

// ==================== CHANGE PASSWORD MODAL ====================
function openPasswordModal() {
    const modal = document.getElementById('passwordModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    populatePasswordTargetUsers();
    document.getElementById('pwdCurrentAdmin').value = '';
    document.getElementById('pwdNewPassword').value = '';
    document.getElementById('pwdConfirmPassword').value = '';
    document.getElementById('passwordModalAlert').classList.add('hidden');

    ['pwdCurrentAdmin', 'pwdNewPassword', 'pwdConfirmPassword'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.type = 'password';
    });
    ['eyeCurrentAdmin', 'eyeNewPassword', 'eyeConfirmPassword'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.className = 'fa-solid fa-eye';
    });
}

function closePasswordModal() {
    const modal = document.getElementById('passwordModal');
    if (modal) modal.classList.add('hidden');
}

function togglePasswordVisibility(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    if (!input || !icon) return;

    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fa-solid fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fa-solid fa-eye';
    }
}

async function executeChangePassword() {
    const targetUser = document.getElementById('pwdTargetUser').value;
    const currentPassword = document.getElementById('pwdCurrentAdmin').value.trim();
    const newPassword = document.getElementById('pwdNewPassword').value.trim();
    const confirmPassword = document.getElementById('pwdConfirmPassword').value.trim();
    const alertBox = document.getElementById('passwordModalAlert');
    const submitBtn = document.getElementById('submitPasswordChangeBtn');

    alertBox.classList.add('hidden');

    if (!currentPassword) {
        alertBox.textContent = 'Please enter current Administrator password.';
        alertBox.classList.remove('hidden');
        return;
    }

    if (!newPassword) {
        alertBox.textContent = 'Please enter a new password.';
        alertBox.classList.remove('hidden');
        return;
    }

    if (newPassword.length < 4) {
        alertBox.textContent = 'New password must be at least 4 characters long.';
        alertBox.classList.remove('hidden');
        return;
    }

    if (newPassword !== confirmPassword) {
        alertBox.textContent = 'New password and confirmation do not match.';
        alertBox.classList.remove('hidden');
        return;
    }

    const originalBtnHtml = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';

    try {
        const res = await fetch('/api/admin/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_user: targetUser,
                current_password: currentPassword,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });

        const data = await res.json();

        if (data.success) {
            closePasswordModal();
            showToast(data.message, 'success');
        } else {
            alertBox.textContent = data.message || 'Failed to update password.';
            alertBox.classList.remove('hidden');
        }
    } catch (err) {
        alertBox.textContent = 'Network or server error while updating password.';
        alertBox.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHtml;
    }
}

// ==================== RESET ENTRIES MODAL ====================
function openResetModal() {
    document.getElementById('resetModal').classList.remove('hidden');
    document.getElementById('resetAdminPassword').value = '';
    document.getElementById('resetModalAlert').classList.add('hidden');
}

function closeResetModal() {
    document.getElementById('resetModal').classList.add('hidden');
}

async function executeResetEntries() {
    const scope = document.getElementById('resetScopeSelect').value;
    const password = document.getElementById('resetAdminPassword').value.trim();
    const alertBox = document.getElementById('resetModalAlert');
    alertBox.classList.add('hidden');

    if (!password) {
        alertBox.textContent = 'Please enter admin password';
        alertBox.classList.remove('hidden');
        return;
    }

    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ college: scope, admin_password: password })
        });
        const data = await res.json();

        if (data.success) {
            closeResetModal();
            showToast(data.message, 'success');
            fetchAdminStats();
            fetchStudentsTable();
        } else {
            alertBox.textContent = data.message;
            alertBox.classList.remove('hidden');
        }
    } catch (err) {
        alertBox.textContent = 'Error connecting to server';
        alertBox.classList.remove('hidden');
    }
}

// ==================== TOAST NOTIFICATIONS ====================
function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? 'fa-circle-check' : (type === 'error' ? 'fa-triangle-exclamation' : 'fa-info-circle');
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${msg}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
