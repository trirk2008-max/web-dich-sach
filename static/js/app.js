document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const dropzoneEmpty = document.getElementById('dropzoneEmpty');
  const dropzoneSelected = document.getElementById('dropzoneSelected');
  const selectedFileName = document.getElementById('selectedFileName');
  const selectedFileSize = document.getElementById('selectedFileSize');
  const fileTypeIcon = document.getElementById('fileTypeIcon');
  const btnRemoveFile = document.getElementById('btnRemoveFile');
  const btnStartTranslate = document.getElementById('btnStartTranslate');

  const sourceLang = document.getElementById('sourceLang');
  const targetLang = document.getElementById('targetLang');
  const engineSelect = document.getElementById('engineSelect');
  const aiKeyGroup = document.getElementById('aiKeyGroup');
  const apiKeyLabel = document.getElementById('apiKeyLabel');
  const apiKeyHelpLink = document.getElementById('apiKeyHelpLink');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const btnTestKey = document.getElementById('btnTestKey');
  const apiKeyStatusText = document.getElementById('apiKeyStatusText');
  const saveKeyLocal = document.getElementById('saveKeyLocal');
  const bilingualToggle = document.getElementById('bilingualToggle');

  // Sections
  const uploadSection = document.getElementById('uploadSection');
  const progressSection = document.getElementById('progressSection');
  const completeSection = document.getElementById('completeSection');

  // Progress UI
  const progressFileTitle = document.getElementById('progressFileTitle');
  const progressSubTitle = document.getElementById('progressSubTitle');
  const progressBar = document.getElementById('progressBar');
  const progressPercentText = document.getElementById('progressPercentText');
  const statParagraphs = document.getElementById('statParagraphs');
  const statWords = document.getElementById('statWords');
  const statSpeed = document.getElementById('statSpeed');
  const statEta = document.getElementById('statEta');
  const liveLogsContainer = document.getElementById('liveLogsContainer');
  const btnStopTask = document.getElementById('btnStopTask');

  // Complete UI
  const completeStatsSummary = document.getElementById('completeStatsSummary');
  const downloadDocx = document.getElementById('downloadDocx');
  const downloadPdf = document.getElementById('downloadPdf');
  const downloadBilingual = document.getElementById('downloadBilingual');
  const downloadTxt = document.getElementById('downloadTxt');
  const btnTranslateAnother = document.getElementById('btnTranslateAnother');

  // Reader UI
  const readerContainer = document.getElementById('readerContainer');
  const btnViewVietnamese = document.getElementById('btnViewVietnamese');
  const btnViewSideBySide = document.getElementById('btnViewSideBySide');
  const btnCopyAll = document.getElementById('btnCopyAll');
  const copyBtnText = document.getElementById('copyBtnText');
  const docSearchInput = document.getElementById('docSearchInput');

  // History UI
  const btnOpenHistory = document.getElementById('btnOpenHistory');
  const btnCloseHistory = document.getElementById('btnCloseHistory');
  const historyModal = document.getElementById('historyModal');
  const historyListContainer = document.getElementById('historyListContainer');

  let selectedFile = null;
  let currentTaskId = null;
  let eventSource = null;
  let taskDocumentItems = [];
  let readerMode = 'vietnamese'; // 'vietnamese' or 'sidebyside'

  // Format bytes
  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Format seconds to mm:ss or hh:mm:ss
  function formatTime(seconds) {
    if (!seconds || seconds <= 0) return 'Vài giây...';
    if (seconds < 60) return `${seconds} giây`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m < 60) return `${m}p ${s}s`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}h ${remM}p`;
  }

  // Update File Selection
  function handleFileSelected(file) {
    if (!file) return;
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!['.docx', '.pdf', '.txt', '.md'].includes(ext)) {
      alert('Vui lòng chọn tệp Word (.docx), PDF (.pdf) hoặc Text (.txt)');
      return;
    }

    selectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);

    // Update icon & color
    if (ext === '.docx') {
      fileTypeIcon.className = 'w-12 h-12 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center text-2xl font-bold';
      fileTypeIcon.innerHTML = '<i class="ph-bold ph-file-doc"></i>';
    } else if (ext === '.pdf') {
      fileTypeIcon.className = 'w-12 h-12 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center text-2xl font-bold';
      fileTypeIcon.innerHTML = '<i class="ph-bold ph-file-pdf"></i>';
    } else {
      fileTypeIcon.className = 'w-12 h-12 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center text-2xl font-bold';
      fileTypeIcon.innerHTML = '<i class="ph-bold ph-file-text"></i>';
    }

    dropzoneEmpty.classList.add('hidden');
    dropzoneSelected.classList.remove('hidden');

    btnStartTranslate.disabled = false;
    btnStartTranslate.className = 'w-full py-4 px-6 rounded-xl font-bold text-base flex items-center justify-center space-x-2 transition-all shadow-xl bg-gradient-to-r from-brand-600 via-indigo-600 to-purple-600 hover:from-brand-500 hover:to-purple-500 text-white cursor-pointer shadow-brand-500/25 active:scale-[0.99]';
  }

  function clearSelectedFile() {
    selectedFile = null;
    fileInput.value = '';
    dropzoneSelected.classList.add('hidden');
    dropzoneEmpty.classList.remove('hidden');

    btnStartTranslate.disabled = true;
    btnStartTranslate.className = 'w-full py-4 px-6 rounded-xl font-bold text-base flex items-center justify-center space-x-2 transition-all shadow-xl bg-slate-800 text-slate-500 cursor-not-allowed';
  }

  // Dropzone Events
  dropzone.addEventListener('click', (e) => {
    if (e.target.closest('#btnRemoveFile')) return;
    fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  btnRemoveFile.addEventListener('click', (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  let serverHasGeminiKey = true;

  // Fetch server config
  fetch('/api/config')
    .then(r => r.json())
    .then(cfg => {
      serverHasGeminiKey = cfg.has_server_gemini_key;
      updateEngineUI();
    })
    .catch(() => {});

  // Restore stored API keys from localStorage
  const savedGeminiKey = localStorage.getItem('gemini_api_key') || '';
  const savedGroqKey = localStorage.getItem('groq_api_key') || '';
  if (apiKeyInput && savedGeminiKey) {
    apiKeyInput.value = savedGeminiKey;
  }

  // Engine change listener
  function updateEngineUI() {
    const engine = engineSelect.value;
    if (engine === 'gemini') {
      aiKeyGroup.classList.remove('hidden');
      apiKeyLabel.textContent = serverHasGeminiKey ? 'Google Gemini API Key (Máy chủ đã kích hoạt sẵn)' : 'Google Gemini API Key (Miễn phí 100%)';
      apiKeyHelpLink.href = 'https://aistudio.google.com/app/apikey';
      apiKeyHelpLink.innerHTML = '<span>Lấy thêm key tại Google AI Studio</span><i class="ph-bold ph-arrow-up-right ml-1"></i>';
      apiKeyInput.placeholder = serverHasGeminiKey ? '(Đã có sẵn key mặc định của bạn, có thể để trống hoặc dán key khác)' : 'Dán Gemini API Key vào đây...';
      apiKeyInput.value = localStorage.getItem('gemini_api_key') || '';
      apiKeyStatusText.className = 'text-[11px] text-emerald-400 font-semibold';
      apiKeyStatusText.innerHTML = serverHasGeminiKey 
        ? '✓ Máy chủ đã tích hợp sẵn Gemini AI Key bản quyền (Tốc độ tối đa ~300 trang/phút, dịch cả cuốn sách trong 20-30s)'
        : '💡 Gemini Flash dịch toàn bộ cuốn sách trong 20-30 giây với văn phong văn học xuất sắc.';
    } else if (engine === 'groq') {
      aiKeyGroup.classList.remove('hidden');
      apiKeyLabel.textContent = 'Groq LPU API Key (Miễn phí 100%)';
      apiKeyHelpLink.href = 'https://console.groq.com/keys';
      apiKeyHelpLink.innerHTML = '<span>Lấy key miễn phí tại Groq Console (750 tokens/s)</span><i class="ph-bold ph-arrow-up-right ml-1"></i>';
      apiKeyInput.placeholder = 'Dán Groq API Key vào đây (ví dụ: gsk_...)';
      apiKeyInput.value = localStorage.getItem('groq_api_key') || '';
      apiKeyStatusText.className = 'text-[11px] text-slate-400';
      apiKeyStatusText.textContent = '🚀 Groq LPU suy luận siêu tốc độ 750 tokens/giây, dịch cực nhanh trong nháy mắt.';
    } else {
      aiKeyGroup.classList.add('hidden');
    }
  }

  engineSelect.addEventListener('change', updateEngineUI);
  updateEngineUI();

  // Test Key Button
  btnTestKey.addEventListener('click', async () => {
    const key = apiKeyInput.value.trim();
    if (!key) {
      alert('Vui lòng dán API Key trước khi kiểm tra!');
      apiKeyInput.focus();
      return;
    }

    btnTestKey.disabled = true;
    btnTestKey.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-sm"></i><span>Đang kiểm tra...</span>';

    const testForm = new FormData();
    testForm.append('engine', engineSelect.value);
    testForm.append('api_key', key);

    try {
      const res = await fetch('/api/test-key', { method: 'POST', body: testForm });
      const data = await res.json();
      if (res.ok && data.valid) {
        apiKeyStatusText.className = 'text-[11px] text-emerald-400 font-semibold';
        apiKeyStatusText.innerHTML = `✓ ${data.message}`;
        if (saveKeyLocal.checked) {
          if (engineSelect.value === 'gemini') localStorage.setItem('gemini_api_key', key);
          if (engineSelect.value === 'groq') localStorage.setItem('groq_api_key', key);
        }
      } else {
        apiKeyStatusText.className = 'text-[11px] text-rose-400 font-semibold';
        apiKeyStatusText.innerHTML = `✗ ${data.message || 'Key không hợp lệ'}`;
      }
    } catch (err) {
      apiKeyStatusText.className = 'text-[11px] text-rose-400 font-semibold';
      apiKeyStatusText.innerHTML = `✗ Lỗi kiểm tra: ${err.message}`;
    } finally {
      btnTestKey.disabled = false;
      btnTestKey.innerHTML = '<i class="ph-bold ph-lightning text-amber-400"></i><span>Kiểm tra Key</span>';
    }
  });

  // Start Translation
  btnStartTranslate.addEventListener('click', async () => {
    if (!selectedFile) return;

    const currentEngine = engineSelect.value;
    const currentKey = apiKeyInput ? apiKeyInput.value.trim() : '';

    // Only prompt for key if server doesn't already have one
    if (currentEngine === 'gemini' && !currentKey && !serverHasGeminiKey) {
      const confirmProceed = confirm(
        'Bạn chưa nhập API Key cho mô hình Siêu Tốc.\n\n' +
        '• Bấm OK: Chuyển sang chế độ Đa Luồng Miễn Phí (không cần key).\n' +
        '• Bấm Cancel: Để nhập Key (nhận key miễn phí trong 10s tại aistudio.google.com).'
      );
      if (confirmProceed) {
        engineSelect.value = 'free';
        updateEngineUI();
      } else {
        apiKeyInput.focus();
        return;
      }
    } else if (currentEngine === 'groq' && !currentKey) {
      alert('Vui lòng nhập Groq API Key!');
      apiKeyInput.focus();
      return;
    }

    // Save key if requested
    if (currentKey && saveKeyLocal && saveKeyLocal.checked) {
      if (currentEngine === 'gemini') localStorage.setItem('gemini_api_key', currentKey);
      if (currentEngine === 'groq') localStorage.setItem('groq_api_key', currentKey);
    }

    // Switch views INSTANTLY (0.001s) - Never leave user waiting on the button!
    uploadSection.classList.add('hidden');
    completeSection.classList.add('hidden');
    progressSection.classList.remove('hidden');

    progressFileTitle.textContent = selectedFile.name;
    progressSubTitle.textContent = '⚡ Đang nạp tệp và phân tích các trang tài liệu...';
    progressBar.style.width = '10%';
    progressPercentText.textContent = 'Khởi tạo...';
    statParagraphs.textContent = 'Đang đọc...';
    statWords.textContent = 'Đang đọc...';
    statSpeed.textContent = 'Khởi động...';
    statEta.textContent = 'Vài giây...';

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('source_lang', sourceLang.value);
    formData.append('target_lang', targetLang.value);
    formData.append('engine', engineSelect.value);
    formData.append('api_key', apiKeyInput ? apiKeyInput.value.trim() : '');
    formData.append('bilingual', bilingualToggle.checked);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Không thể bắt đầu dịch!');
      }

      const task = await res.json();
      currentTaskId = task.task_id;

      // Start SSE progress tracking
      startTaskEventStream(task.task_id);

    } catch (err) {
      alert('Lỗi: ' + err.message);
      progressSection.classList.add('hidden');
      uploadSection.classList.remove('hidden');
      btnStartTranslate.disabled = false;
      btnStartTranslate.innerHTML = '<i class="ph-bold ph-translate text-xl"></i><span>Bắt Đầu Dịch Toàn Bộ Tệp</span>';
    }
  });

  // SSE Stream
  function startTaskEventStream(taskId) {
    if (eventSource) {
      eventSource.close();
    }

    eventSource = new EventSource(`/api/task/${taskId}/events`);

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.error) {
          alert('Lỗi tác vụ: ' + data.error);
          eventSource.close();
          return;
        }

        updateProgressUI(data);

        if (data.status === 'completed') {
          eventSource.close();
          onTranslationCompleted(taskId, data);
        } else if (data.status === 'error') {
          eventSource.close();
          alert('Có lỗi trong quá trình dịch: ' + (data.error_message || 'Không xác định'));
        } else if (data.status === 'stopped') {
          eventSource.close();
          alert('Tác vụ đã được dừng.');
        }
      } catch (err) {
        console.error('SSE Parse Error', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE Error / Reconnecting...', err);
    };
  }

  function updateProgressUI(data) {
    if (data.status === 'preparing') {
      progressSubTitle.textContent = '⚡ Đang nạp nhanh các trang tài liệu vào bộ nhớ...';
      statParagraphs.textContent = 'Đang nạp...';
      statWords.textContent = 'Đang nạp...';
      statSpeed.textContent = 'Khởi động...';
      statEta.textContent = 'Vài giây...';
      return;
    }

    if (data.total_paragraphs > 0) {
      progressSubTitle.textContent = `Tổng cộng khoảng ${data.total_paragraphs} đoạn văn (${(data.total_words || 0).toLocaleString()} từ ~ ${data.estimated_pages || 1} trang)`;
    }

    const percent = Math.min(100, Math.max(0, data.progress_percent || 0));
    progressBar.style.width = `${percent}%`;
    progressPercentText.textContent = `${percent.toFixed(1)}%`;

    statParagraphs.textContent = `${data.completed_paragraphs} / ${data.total_paragraphs}`;
    statWords.textContent = `${(data.completed_words || 0).toLocaleString()} / ${(data.total_words || 0).toLocaleString()}`;
    statSpeed.textContent = `${data.speed_wpm || 0} từ/phút`;
    statEta.textContent = formatTime(data.eta_seconds);

    // Update live log stream
    if (data.recent_logs && data.recent_logs.length > 0) {
      liveLogsContainer.innerHTML = '';
      data.recent_logs.forEach(log => {
        const item = document.createElement('div');
        item.className = 'border-b border-slate-900/80 pb-1.5 last:border-none';
        item.innerHTML = `
          <div class="text-[10px] text-slate-500 font-sans flex items-center justify-between">
            <span>[${log.time}] Đoạn dịch:</span>
            <span class="text-emerald-400">✓ Hoàn thành</span>
          </div>
          <div class="text-slate-200 mt-0.5 leading-snug">${escapeHtml(log.translated)}</div>
        `;
        liveLogsContainer.appendChild(item);
      });
      liveLogsContainer.scrollTop = liveLogsContainer.scrollHeight;
    }
  }

  // Stop button
  btnStopTask.addEventListener('click', async () => {
    if (!currentTaskId) return;
    if (confirm('Bạn có chắc chắn muốn dừng quá trình dịch? Các đoạn đã dịch sẽ được giữ lại.')) {
      await fetch(`/api/task/${currentTaskId}/stop`, { method: 'POST' });
    }
  });

  // Completed handler
  async function onTranslationCompleted(taskId, data) {
    progressSection.classList.add('hidden');
    completeSection.classList.remove('hidden');

    completeStatsSummary.textContent = `Đã dịch hoàn tất ${data.total_paragraphs} đoạn văn (${(data.total_words || 0).toLocaleString()} từ) trong ${formatTime(data.elapsed_seconds)}.`;

    // Download links
    downloadDocx.href = `/api/task/${taskId}/download/docx`;
    downloadPdf.href = `/api/task/${taskId}/download/pdf`;
    downloadBilingual.href = `/api/task/${taskId}/download/docx_bilingual`;
    downloadTxt.href = `/api/task/${taskId}/download/txt`;

    // Load translated document items for reader
    loadDocumentContent(taskId);
  }

  async function loadDocumentContent(taskId) {
    readerContainer.innerHTML = '<p class="text-center text-slate-500 py-6">Đang tải văn bản...</p>';
    try {
      const res = await fetch(`/api/task/${taskId}/content`);
      const data = await res.json();
      taskDocumentItems = data.items || [];
      renderReader();
    } catch (err) {
      readerContainer.innerHTML = '<p class="text-rose-400 text-center py-6">Không thể tải nội dung xem trước.</p>';
    }
  }

  function renderReader(filterQuery = '') {
    if (!taskDocumentItems || taskDocumentItems.length === 0) {
      readerContainer.innerHTML = '<p class="text-slate-500 text-center py-6">Tài liệu không có nội dung chữ.</p>';
      return;
    }

    const query = filterQuery.trim().toLowerCase();
    let html = '';

    taskDocumentItems.forEach(item => {
      const orig = item.original || '';
      const trans = item.translated || '';

      if (query && !trans.toLowerCase().includes(query) && !orig.toLowerCase().includes(query)) {
        return;
      }

      const isHeading = item.style && item.style.toLowerCase().includes('heading');

      if (readerMode === 'vietnamese') {
        let displayTrans = escapeHtml(trans);
        if (query) {
          displayTrans = highlightMatch(displayTrans, query);
        }
        if (isHeading) {
          html += `<div class="reader-heading">${displayTrans}</div>`;
        } else {
          html += `<div class="reader-para p-2 rounded-lg leading-relaxed">${displayTrans}</div>`;
        }
      } else {
        // Side-by-side comparison mode
        let displayOrig = escapeHtml(orig);
        let displayTrans = escapeHtml(trans);
        if (query) {
          displayOrig = highlightMatch(displayOrig, query);
          displayTrans = highlightMatch(displayTrans, query);
        }
        html += `
          <div class="reader-para grid grid-cols-1 md:grid-cols-2 gap-4 p-3 rounded-lg border border-slate-800/80 bg-slate-900/30">
            <div class="text-slate-400 text-xs sm:text-sm font-sans border-b md:border-b-0 md:border-r border-slate-800 pb-2 md:pb-0 md:pr-3">
              <span class="inline-block text-[10px] text-slate-500 uppercase font-bold mb-1">Bản gốc:</span>
              <p>${displayOrig}</p>
            </div>
            <div class="text-slate-200 text-xs sm:text-sm font-sans">
              <span class="inline-block text-[10px] text-brand-400 uppercase font-bold mb-1">Bản dịch tiếng Việt:</span>
              <p class="font-medium">${displayTrans}</p>
            </div>
          </div>
        `;
      }
    });

    readerContainer.innerHTML = html || '<p class="text-center text-slate-500 py-6">Không tìm thấy nội dung khớp với từ khóa.</p>';
  }

  // Reader Mode switches
  btnViewVietnamese.addEventListener('click', () => {
    readerMode = 'vietnamese';
    btnViewVietnamese.className = 'px-3 py-1.5 rounded-md bg-brand-600 text-white font-medium transition';
    btnViewSideBySide.className = 'px-3 py-1.5 rounded-md text-slate-300 hover:text-white font-medium transition';
    renderReader(docSearchInput.value);
  });

  btnViewSideBySide.addEventListener('click', () => {
    readerMode = 'sidebyside';
    btnViewSideBySide.className = 'px-3 py-1.5 rounded-md bg-brand-600 text-white font-medium transition';
    btnViewVietnamese.className = 'px-3 py-1.5 rounded-md text-slate-300 hover:text-white font-medium transition';
    renderReader(docSearchInput.value);
  });

  docSearchInput.addEventListener('input', () => {
    renderReader(docSearchInput.value);
  });

  // Copy full translated text
  btnCopyAll.addEventListener('click', () => {
    const fullText = taskDocumentItems.map(i => i.translated).join('\n\n');
    navigator.clipboard.writeText(fullText).then(() => {
      copyBtnText.textContent = 'Đã sao chép!';
      setTimeout(() => {
        copyBtnText.textContent = 'Sao chép';
      }, 2000);
    });
  });

  // Translate Another Document
  btnTranslateAnother.addEventListener('click', () => {
    completeSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    clearSelectedFile();
  });

  // History Drawer / Modal
  btnOpenHistory.addEventListener('click', async () => {
    historyModal.classList.remove('hidden');
    historyListContainer.innerHTML = '<p class="text-center text-slate-500 py-6">Đang tải lịch sử...</p>';

    try {
      const res = await fetch('/api/tasks');
      const tasks = await res.json();
      if (!tasks || tasks.length === 0) {
        historyListContainer.innerHTML = '<p class="text-center text-slate-500 py-6">Chưa có tài liệu nào trong lịch sử.</p>';
        return;
      }

      let html = '';
      tasks.forEach(t => {
        const isDone = t.status === 'completed';
        const statusBadge = isDone 
          ? '<span class="text-emerald-400 text-xs font-semibold">✓ Đã xong</span>'
          : '<span class="text-amber-400 text-xs font-semibold">Đang xử lý</span>';

        html += `
          <div class="flex items-center justify-between p-3.5 rounded-xl bg-slate-950/60 border border-slate-800">
            <div class="flex items-center space-x-3">
              <div class="w-9 h-9 rounded-lg bg-slate-800 text-brand-400 flex items-center justify-center text-lg">
                <i class="ph-bold ph-file-text"></i>
              </div>
              <div>
                <p class="text-sm font-semibold text-white truncate max-w-xs">${escapeHtml(t.filename)}</p>
                <div class="flex items-center space-x-2 text-xs text-slate-400">
                  <span>${(t.total_words || 0).toLocaleString()} từ</span>
                  <span>•</span>
                  ${statusBadge}
                </div>
              </div>
            </div>

            <div class="flex items-center space-x-2">
              ${isDone ? `
                <a href="/api/task/${t.id}/download/docx" target="_blank" class="px-2.5 py-1.5 rounded-lg bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 text-xs font-medium border border-blue-500/20">
                  Word
                </a>
                <a href="/api/task/${t.id}/download/pdf" target="_blank" class="px-2.5 py-1.5 rounded-lg bg-rose-600/20 text-rose-400 hover:bg-rose-600/30 text-xs font-medium border border-rose-500/20">
                  PDF
                </a>
              ` : ''}
              <button onclick="deleteHistoryTask('${t.id}')" class="p-1.5 text-slate-500 hover:text-rose-400 transition" title="Xóa">
                <i class="ph-bold ph-trash"></i>
              </button>
            </div>
          </div>
        `;
      });
      historyListContainer.innerHTML = html;
    } catch (err) {
      historyListContainer.innerHTML = '<p class="text-center text-rose-400 py-6">Lỗi tải lịch sử.</p>';
    }
  });

  btnCloseHistory.addEventListener('click', () => {
    historyModal.classList.add('hidden');
  });

  window.deleteHistoryTask = async function(taskId) {
    if (confirm('Xóa bản ghi này khỏi lịch sử?')) {
      await fetch(`/api/task/${taskId}`, { method: 'DELETE' });
      btnOpenHistory.click(); // Reload history
    }
  };

  // Utility helpers
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function highlightMatch(text, query) {
    if (!query) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }
});
