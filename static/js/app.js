// State Management
let currentUser = null;
let currentRole = 'volunteer';
let currentView = 'login';
let html5QrCode = null;
let cameraActive = false;
let isProcessingScan = false;
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
            const isClickInsideInteractive = e.target.closest('button, a, input, select, textarea');
            if (!isClickInsideInteractive) {
                const inp = document.getElementById('barcodeInput');
                if (inp) inp.focus();
            }
        }
    });
});

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
        payload = {
            volunteer_name: document.getElementById('volunteerStation').value.trim() || 'Volunteer',
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

// ==================== SCANNER LOGIC ====================
function processManualInput() {
    const input = document.getElementById('barcodeInput');
    const val = input.value.trim();
    if (!val) return;
    executeScan(val);
    input.value = '';
    input.focus();
}

async function executeScan(barcode) {
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

        handleScanResult(data, barcode);
    } catch (err) {
        showToast('Error communicating with verification server', 'error');
    } finally {
        isProcessingScan = false;
        // Refocus input bar
        const inp = document.getElementById('barcodeInput');
        if (inp) inp.focus();
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
            // Success scan
            if (!isProcessingScan) {
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

// ==================== CHANGE PASSWORD MODAL ====================
function openPasswordModal() {
    const modal = document.getElementById('passwordModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    document.getElementById('pwdTargetUser').value = 'admin';
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
