/* ==========================================================================
   SERVER GURU (TEACHER PORTAL) - MAIN JAVASCRIPT LOGIC
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initFileUploads();
  initTeacherSelector();
});

/**
 * Handles Drag & Drop file input UI feedback and filename display
 */
function initFileUploads() {
  const uploadZones = document.querySelectorAll('.upload-zone');

  uploadZones.forEach(zone => {
    const input = zone.querySelector('.file-input-hidden');
    const info = zone.querySelector('.file-selected-info');
    const filenameSpan = zone.querySelector('.filename-text');

    if (!input) return;

    ['dragenter', 'dragover'].forEach(eventName => {
      zone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add('dragover');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      zone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('dragover');
      }, false);
    });

    input.addEventListener('change', () => {
      if (input.files && input.files[0]) {
        const file = input.files[0];
        if (filenameSpan) filenameSpan.textContent = file.name;
        if (info) info.style.display = 'inline-flex';
        showToast(`File terpilih: ${file.name}`, 'info');
      }
    });
  });
}

/**
 * Handles teacher card selection on Login page
 */
function initTeacherSelector() {
  const cards = document.querySelectorAll('.teacher-select-card');
  const namaInput = document.getElementById('namaGuruInput');

  cards.forEach(card => {
    card.addEventListener('click', () => {
      cards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      const teacherName = card.getAttribute('data-teacher');
      if (namaInput) {
        namaInput.value = teacherName;
      }
    });
  });
}

/**
 * Toast Notification System
 */
function showToast(message, type = 'info') {
  let toast = document.getElementById('globalToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'globalToast';
    toast.className = 'toast-notification';
    document.body.appendChild(toast);
  }

  const iconClass = type === 'success' ? 'ph-check-circle' : type === 'error' ? 'ph-warning-circle' : 'ph-info';
  const color = type === 'success' ? '#10b981' : type === 'error' ? '#f43f5e' : '#06b6d4';

  toast.innerHTML = `<i class="ph ${iconClass}" style="font-size: 1.4rem; color: ${color};"></i> <span>${message}</span>`;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 3500);
}
