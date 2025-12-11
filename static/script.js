// script.js (HOI Dashboard Frontend Logic) - Final Version (VS Code ready)
// ========================================================================

// =======================================================
// 1. GLOBAL DOM REFERENCES (அனைத்து ஃபங்ஷன்களிலும் பயன்படுத்த)
// =======================================================
const mainContent = document.getElementById('mainContent');
const pageTitle = document.getElementById('pageTitle');
const modalOverlay = document.getElementById('approvalModalOverlay');
const modalTitle = document.getElementById('modalTitle');
const modalUser = document.getElementById('modalUser');
const remarksBox = document.getElementById('remarksBox');
const approveBtn = document.getElementById('approveBtn');
const rejectBtn = document.getElementById('rejectBtn');
const chatbotWindow = document.getElementById('chatbotWindow');
const chatbotMessages = document.getElementById('chatbotMessages');
const chatbotInput = document.getElementById('chatbotInput');
const chatbotBtn = document.getElementById('chatbotBtn');

// செயல்பாட்டில் உள்ள Record ID-ஐத் track செய்ய
let currentRecordId = null;

// =======================================================
// CORE NAVIGATION & SECTION RENDERING
// =======================================================

/**
 * URL Route-ஐ பயன்படுத்தி ஒரு API endpoint-லிருந்து JSON data ஏற்றும்.
 * @param {string} url - API URL.
 * @param {string} sectionName - புதிய தலைப்பு.
 */
async function loadContent(url, sectionName) {
  mainContent.innerHTML = `<div class="p-4 text-center text-gray-500 flex items-center justify-center text-lg"><span class="material-icons mr-2 animate-spin">autorenew</span> Loading ${sectionName}...</div>`;
  pageTitle.textContent = sectionName;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      let errorData = {};
      if (response.headers.get('content-type')?.includes('application/json')) {
        errorData = await response.json();
      }
      if (errorData.message?.includes("Login session expired") || response.status === 401) {
        alert("Your session has expired. Please log in again.");
        window.location.href = '/login';
        return;
      }
      throw new Error(errorData.message || `HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    // Data received: Call appropriate render function
    if (sectionName.includes('Activity')) {
      renderActivity(data.data || []);
    } else if (sectionName.includes('Approvals')) {
      renderApprovals(data.data || []);
    } else if (sectionName.includes('Alerts')) {
      renderAlerts(data.data || []);
    } else {
      renderDashboardOverview();
    }
  } catch (error) {
    mainContent.innerHTML = `<div class="p-4 bg-red-100 text-red-700 rounded shadow flex items-center"><span class="material-icons mr-2">error_outline</span>Error loading data: ${error.message}</div>`;
    console.error('Fetch error:', error);
  }
}

/**
 * Dashboard பிரிவுகளை மாற்றுகிறது.
 * @param {string} section - overview | activity | approvals | alerts | forms_list
 */
function switchSection(section) {
  // Nav links-ஐ highlight செய்ய (assumes nav buttons have ids like nav-overview)
  document.querySelectorAll('aside nav button').forEach(el => el.classList.remove('bg-blue-800'));
  const currentNav = document.getElementById(`nav-${section}`);
  if (currentNav) currentNav.classList.add('bg-blue-800');

  switch (section) {
    case 'overview':
      pageTitle.textContent = 'Dashboard Overview 📊';
      renderDashboardOverview();
      break;
    case 'activity':
      loadContent('/api/today_activities', "Today's Activity 📝");
      break;
    case 'approvals':
      loadContent('/api/pending_approvals', 'Pending Approvals ⏳');
      break;
    case 'alerts':
      loadContent('/api/alerts', 'Active Alerts 🔔');
      break;
    case 'forms_list':
      pageTitle.textContent = 'Action Tables List 📋';
      renderFormsList();
      break;
    default:
      renderDashboardOverview();
  }
}

// =======================================================
// 2. VIEW RENDERERS (பிரிவுகளை ஏற்றுகிறது)
// =======================================================

function renderDashboardOverview() {
  mainContent.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div onclick="switchSection('approvals')" class="bg-white p-6 rounded-lg shadow-lg text-center border-l-4 border-yellow-600 hover:shadow-xl transition duration-150 cursor-pointer">
        <p class="text-4xl font-bold text-yellow-600" id="totalPending">...</p>
        <p class="text-gray-500 mt-2">Pending Approvals</p>
      </div>
      <div onclick="switchSection('activity')" class="bg-white p-6 rounded-lg shadow-lg text-center border-l-4 border-green-600 hover:shadow-xl transition duration-150 cursor-pointer">
        <p class="text-4xl font-bold text-green-600" id="totalApproved">...</p>
        <p class="text-gray-500 mt-2">Today Approved</p>
      </div>
      <div onclick="switchSection('alerts')" class="bg-white p-6 rounded-lg shadow-lg text-center border-l-4 border-red-600 hover:shadow-xl transition duration-150 cursor-pointer">
        <p class="text-4xl font-bold text-red-600" id="totalAlerts">...</p>
        <p class="text-gray-500 mt-2">Active Alerts</p>
      </div>
    </div>
    <div class="mt-6 p-4 bg-white rounded-lg shadow-lg">
      <h3 class="text-xl font-semibold mb-4 text-gray-800">Quick Links</h3>
      <div class="flex space-x-4">
        <button onclick="switchSection('activity')" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition duration-150">View Today Activity</button>
        <button onclick="switchSection('approvals')" class="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition duration-150">Review Approvals</button>
      </div>
    </div>
  `;
  // Overview metrics-ஐ ஏற்றுகிறது
  fetchDashboardMetrics();
}

/**
 * Today Activity-க்கான டேபிளை ரெண்டர் செய்கிறது.
 */
function renderActivity(activities) {
  mainContent.innerHTML = `
    <div class="bg-white p-4 rounded-lg shadow overflow-x-auto">
      <h3 class="text-xl font-semibold mb-4 text-gray-800">Today Activity Status (${activities.length} Entries)</h3>
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Form Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Saved By</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          ${activities.map(act => `
            <tr class="${act.is_alert ? 'bg-red-50' : ''} hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${escapeHtml(act.form_name || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${escapeHtml(act.saved_by || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatDateShortTime(act.saved_at)}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${act.status === 'approved' ? 'bg-green-100 text-green-800' : act.status === 'disapproved' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}">
                  ${escapeHtml(act.status || '')}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                <button onclick="viewFormDetails(${Number(act.id)})" class="text-blue-600 hover:text-blue-900">View</button>
                <button onclick="toggleAlert(${Number(act.id)}, ${act.is_alert ? 1 : 0})" class="${act.is_alert ? 'text-orange-600 hover:text-orange-800 font-bold' : 'text-gray-400 hover:text-gray-600'}">
                  <span class="material-icons text-base align-middle">${act.is_alert ? 'warning' : 'flag'}</span> ${act.is_alert ? 'Alert ON' : 'Set Alert'}
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${activities.length === 0 ? '<p class="p-4 text-center text-gray-500">No activities recorded today.</p>' : ''}
    </div>
  `;
}

/**
 * Pending Approvals-க்கான டேபிளை ரெண்டர் செய்கிறது.
 */
function renderApprovals(approvals) {
  mainContent.innerHTML = `
    <div class="bg-white p-4 rounded-lg shadow overflow-x-auto">
      <h3 class="text-xl font-semibold mb-4 text-yellow-700">Pending Submissions for Approval (${approvals.length} Entries)</h3>
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Form Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Institute</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Submitted By</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Submitted At</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          ${approvals.map(app => `
            <tr class="hover:bg-yellow-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${escapeHtml(app.form_name || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${escapeHtml(app.institute || 'N/A')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${escapeHtml(app.saved_by || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatDateShort(app.saved_at)}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                <button onclick="openApprovalModal(${Number(app.id)}, '${escapeForJs(app.form_name || '')}', '${escapeForJs(app.saved_by || '')}')" class="px-3 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600">Approve/Action</button>
                <button onclick="viewFormDetails(${Number(app.id)})" class="text-blue-600 hover:text-blue-900 text-xs">View Details</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${approvals.length === 0 ? '<p class="p-4 text-center text-gray-500">No pending approvals.</p>' : ''}
    </div>
  `;
}

/**
 * Alerts-க்கான டேபிளை ரெண்டர் செய்கிறது.
 */
function renderAlerts(alerts) {
  mainContent.innerHTML = `
    <div class="bg-white p-4 rounded-lg shadow overflow-x-auto">
      <h3 class="text-xl font-semibold mb-4 text-red-700">Active High Priority Alerts 🚨 (${alerts.length} Alerts)</h3>
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Form Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Institute</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Submitted By</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          ${alerts.map(alert => `
            <tr class="bg-red-50 hover:bg-red-100">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-red-900">${escapeHtml(alert.form_name || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-red-700">${escapeHtml(alert.institute || 'N/A')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-red-700">${escapeHtml(alert.saved_by || '')}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-red-700">${formatDateShort(alert.saved_at)}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                <button onclick="viewFormDetails(${Number(alert.id)})" class="text-blue-600 hover:text-blue-900">View</button>
                <button onclick="toggleAlert(${Number(alert.id)}, ${alert.is_alert ? 1 : 0})" class="px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs hover:bg-gray-300">Clear Alert</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${alerts.length === 0 ? '<p class="p-4 text-center text-gray-500">No active alerts.</p>' : ''}
    </div>
  `;
}

/**
 * Forms List-ஐ ரெண்டர் செய்கிறது.
 */
function renderFormsList() {
  const formNames = [
    "academics.html", "accounts.html", "accreditation.html", "admission.html", "affiliations.html", "ahs.html",
    "boys_hostel.html", "budget.html", "engineering.html", "event_management.html", "girls_hostel.html",
    "guestservice.html", "Hr.html", "incubation.html", "infra_operation.html", "It_Infra.html",
    "mess_management.html", "new_institution.html", "nursing.html", "pharmacy.html", "placement.html",
    "purchase.html", "research.html", "safety.html", "security.html", "transport.html", "branding_marketing.html"
  ];

  const formsHtml = formNames.map(name => {
    const display_name = name.replace('.html', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    return `
      <a href="/api/load_form_template/${name}" target="_blank" class="block">
        <div class="p-4 bg-white border border-gray-200 rounded-lg hover:bg-blue-50 cursor-pointer transition duration-150 transform hover:shadow-lg">
          <p class="font-bold text-blue-700">${escapeHtml(display_name)}</p>
          <p class="text-xs text-gray-500">Template: ${escapeHtml(name)}</p>
        </div>
      </a>
    `;
  }).join('');

  mainContent.innerHTML = `
    <div class="bg-white p-6 rounded-lg shadow-xl">
      <h3 class="text-xl font-semibold mb-4 text-gray-800">List of ${formNames.length} Action Tables (Forms)</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        ${formsHtml}
      </div>
    </div>
    <div id="formTemplateContainer" class="mt-6">
      <p class="p-4 text-center text-gray-500 bg-white rounded-lg shadow">Click on a form name to open it in a new tab for data entry.</p>
    </div>
  `;
}

/**
 * Form-ன் முழுமையான JSON content-ஐப் பெறுகிறது மற்றும் அதை Modal-இல் காண்பிக்கிறது.
 * @param {number} id - Record ID.
 */
async function viewFormDetails(id) {
  try {
    const response = await fetch(`/api/get_form_content/${id}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch record details for ID ${id}.`);
    }
    const record = await response.json();
    const prettyJson = JSON.stringify(record, null, 2);
    // Show in a simple modal-like alert (replace with custom modal if needed)
    const details = `Record Details (ID: ${id})
Form Name: ${record.form_name || 'N/A'}
Status: ${record.status || 'N/A'}

--- Full JSON Content ---
${prettyJson}`;
    // Use a window.open to show long text in new tab for better readability
    const w = window.open("", `_form_${id}`, "width=800,height=600,scrollbars=yes");
    if (w) {
      w.document.write(`<pre style="white-space:pre-wrap;word-wrap:break-word;font-family:monospace;padding:16px;">${escapeHtml(details)}</pre>`);
      w.document.title = `Record ${id}`;
    } else {
      alert(details);
    }
  } catch (error) {
    console.error('Error fetching form details:', error);
    alert(`Error: Could not load details for ID ${id}. ${error.message}`);
  }
}

// =======================================================
// 3. MODAL & ACTION HANDLERS (Approve/Disapprove/Alert)
// =======================================================

/**
 * @param {number} id 
 * @param {string} formName 
 * @param {string} savedBy 
 */
function openApprovalModal(id, formName, savedBy) {
  currentRecordId = id;
  if (modalTitle) modalTitle.textContent = `Action for: ${formName}`;
  if (modalUser) modalUser.textContent = `Submitted by: ${savedBy}`;
  if (remarksBox) remarksBox.value = '';
  if (modalOverlay) modalOverlay.classList.remove('hidden');
}

/**
 */
function closeModal() {
  if (modalOverlay) modalOverlay.classList.add('hidden');
  currentRecordId = null;
}

/**
 * @param {string} action - 'approve' or 'disapprove'.
 */
async function processSubmission(action) {
  if (!currentRecordId) return;
  const remarks = (remarksBox && remarksBox.value) ? remarksBox.value.trim() : '';
  if (action === 'disapprove' && !remarks) {
    alert("Remarks are required for Disapproval.");
    return;
  }
  closeModal();

  const url = action === 'approve' ? '/api/approve_submission' : '/api/disapprove_submission';
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: currentRecordId, remarks: remarks })
    });
    const result = await response.json();
    if (response.ok && result.status === 'ok') {
      alert(`✅ ${action.toUpperCase()} successful. Message: ${result.message}`);
      // Refresh approvals view and dashboard metrics
      switchSection('approvals');
      fetchDashboardMetrics();
    } else {
      alert(`❌ Error during ${action}: ${result.message || ('Server processing failed. Status Code: ' + response.status)}`);
    }
  } catch (error) {
    console.error(`Error processing ${action}:`, error);
    alert(`Network or internal error during ${action}: ${error.message}`);
  }
}

/**
 * @param {number} id
 * @param {number} isCurrentlyAlert
 */
async function toggleAlert(id, isCurrentlyAlert) {
  const newStatus = isCurrentlyAlert === 1 ? 0 : 1;
  const actionText = newStatus === 1 ? 'setting Alert' : 'clearing Alert';
  if (!confirm(`Confirm ${actionText} for Record ID: ${id}?`)) return;
  try {
    const response = await fetch('/api/set_alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id, set: newStatus })
    });
    const result = await response.json();
    if (response.ok && result.status === 'ok') {
      alert(result.message);
      switchSection('alerts');
      fetchDashboardMetrics();
    } else {
      alert(`Error updating Alert status: ${result.message || 'Server processing failed.'}`);
    }
  } catch (error) {
    console.error('Error toggling alert:', error);
    alert(`Network or internal error during alert update: ${error.message}`);
  }
}

/**
 */
async function fetchDashboardMetrics() {
  try {
    const [pendingRes, alertsRes, activityRes] = await Promise.all([
      fetch('/api/pending_approvals'),
      fetch('/api/alerts'),
      fetch('/api/today_activities')
    ]);
    if (!pendingRes.ok || !alertsRes.ok || !activityRes.ok) {
      throw new Error("One or more metric APIs failed.");
    }
    const [pendingData, alertsData, activityData] = await Promise.all([
      pendingRes.json(),
      alertsRes.json(),
      activityRes.json()
    ]);
    const pendingCount = (pendingData && pendingData.data) ? pendingData.data.length : 0;
    const alertsCount = (alertsData && alertsData.data) ? alertsData.data.length : 0;
    const approvedToday = (activityData && activityData.data) ? activityData.data.filter(a => a.status === 'approved').length : 0;

    const totalPendingEl = document.getElementById('totalPending');
    const totalAlertsEl = document.getElementById('totalAlerts');
    const totalApprovedEl = document.getElementById('totalApproved');

    if (totalPendingEl) totalPendingEl.textContent = pendingCount;
    if (totalAlertsEl) totalAlertsEl.textContent = alertsCount;
    if (totalApprovedEl) totalApprovedEl.textContent = approvedToday;
  } catch (e) {
    console.error("Failed to fetch dashboard metrics:", e);
    ['totalPending', 'totalApproved', 'totalAlerts'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'N/A';
    });
  }
}

// =======================================================
// 4. CHATBOT LOGIC (Enhanced for Markdown)
// =======================================================

function toggleChatbot() {
  const isHidden = chatbotWindow.classList.toggle('hidden');
  if (isHidden) {
    chatbotBtn.innerHTML = '<span class="material-icons text-2xl">chat</span>';
  } else {
    chatbotBtn.innerHTML = '<span class="material-icons text-2xl">close</span>';
    if (chatbotInput) chatbotInput.focus();
    if (chatbotMessages.children.length === 0) {
      addMessage("Hi there! I'm your HOI Assistant. 🤖 I can give you live data or general info. Try asking for:\n- **'stats'** or **'summary'** (for form counts)\n- **'pending'** or **'alerts'** (for status)", 'bot');
    }
  }
}

async function sendMessage() {
  const message = chatbotInput.value.trim();
  if (message === "") return;
  addMessage(message, 'user');
  chatbotInput.value = '';
  const typingIndicator = addMessage('Assistant is typing...', 'bot', true);
  try {
    const response = await fetch('/chatbot_reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message })
    });
    const result = await response.json();
    if (typingIndicator && chatbotMessages.contains(typingIndicator)) {
      chatbotMessages.removeChild(typingIndicator);
    }
    if (response.ok && result.status === 'ok') {
      addMessage(result.reply || 'No reply provided.', 'bot');
    } else {
      addMessage(`⚠️ **Error:** ${result.reply || result.message || 'Undefined response from server.'}`, 'bot');
    }
  } catch (error) {
    console.error('Chatbot API error:', error);
    const indicators = chatbotMessages.querySelectorAll('#typingIndicator');
    indicators.forEach(indicator => {
      if (chatbotMessages.contains(indicator)) chatbotMessages.removeChild(indicator);
    });
    addMessage(`Sorry, the server is not responding to chatbot queries. Network Error: ${error.message}`, 'bot');
  }
}

/**
 * @param {string} text 
 * @param {string} sender
 * @param {boolean} isTypingIndicator 
 * @returns {HTMLElement}
 */
function addMessage(text, sender = 'bot', isTypingIndicator = false) {
  const messageDiv = document.createElement('div');
  const isUser = sender === 'user';
  messageDiv.className = `flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`;

  const contentDiv = document.createElement('div');
  contentDiv.className = `max-w-[80%] px-3 py-2 rounded-lg text-sm shadow-md ${isUser ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-200 text-gray-800 rounded-bl-none'}`;

  if (isTypingIndicator) {
    contentDiv.id = 'typingIndicator';
    contentDiv.innerHTML = '<div class="dot-flashing w-6 h-6"></div>';
  } else {
    // Basic Markdown support: **bold** -> <strong>, lines -> <br>, lists starting with "- "
    let formattedHtml = escapeHtml(String(text));
    // Convert **bold** (we escaped, so replace escaped ** markers)
    formattedHtml = formattedHtml.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // handle lines and lists
    const lines = formattedHtml.split('\n');
    let listHtml = '';
    let inList = false;
    for (const line of lines) {
      if (line.trim().startsWith('- ')) {
        if (!inList) { listHtml += '<ul class="list-disc list-inside mt-1 space-y-0.5">'; inList = true; }
        listHtml += `<li>${line.trim().substring(2)}</li>`;
      } else {
        if (inList) { listHtml += '</ul>'; inList = false; }
        listHtml += line + '<br>';
      }
    }
    if (inList) listHtml += '</ul>';
    formattedHtml = listHtml.replace(/<br>$/g, '').replace(/<br><br>/g, '<br>');
    contentDiv.innerHTML = formattedHtml;
  }

  messageDiv.appendChild(contentDiv);
  chatbotMessages.appendChild(messageDiv);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
  return messageDiv;
}

// =======================================================
// 5. INITIALIZATION (நிகழ்வு கேட்பவர்கள்)
// =======================================================

document.addEventListener('DOMContentLoaded', () => {
  // Chatbot Input-ஐ Enter key அழுத்துவதன் மூலம் அனுப்பும் வசதி
  if (chatbotInput) {
    chatbotInput.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // Modal-ஐ escape key மூலம் மூடும் வசதி
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalOverlay && !modalOverlay.classList.contains('hidden')) {
      closeModal();
    }
  });

  // Default view: Dashboard Overview
  switchSection('overview');
});

// Make functions available globally for inline onclick handlers
window.switchSection = switchSection;
window.renderFormsList = renderFormsList;
window.viewFormDetails = viewFormDetails;
window.openApprovalModal = openApprovalModal;
window.closeModal = closeModal;
window.processSubmission = processSubmission;
window.toggleAlert = toggleAlert;
window.fetchDashboardMetrics = fetchDashboardMetrics;
window.toggleChatbot = toggleChatbot;
window.sendMessage = sendMessage;
window.addMessage = addMessage;

// Simple form submit helper for accounts.html (example)
function submitFormData(form_data) {
  form_data['form_name'] = 'Accounts & Finance';
  fetch('/submit_form_data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form_data)
  })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'ok') {
        alert(data.message);
        window.location.href = '/dashboard';
      } else {
        alert("Submission failed: " + data.message);
      }
    })
    .catch(error => {
      console.error('Error:', error);
      alert('An error occurred during submission.');
    });
}
window.submitFormData = submitFormData;

// =======================================================
// Utility helpers
// =======================================================

/** Escape HTML to avoid XSS in inserted content */
function escapeHtml(unsafe) {
  return String(unsafe)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

/** Escape string for safe insertion inside single-quoted JS attribute in templates */
function escapeForJs(str) {
  if (!str && str !== 0) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').replace(/\r/g, '');
}

/** Format date to locale short date + short time */
function formatDateShortTime(dateInput) {
  try {
    const d = new Date(dateInput);
    if (isNaN(d)) return escapeHtml(String(dateInput || ''));
    return d.toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return escapeHtml(String(dateInput || ''));
  }
}

/** Format date to short date only */
function formatDateShort(dateInput) {
  try {
    const d = new Date(dateInput);
    if (isNaN(d)) return escapeHtml(String(dateInput || ''));
    return d.toLocaleString('en-IN', { dateStyle: 'short' });
  } catch {
    return escapeHtml(String(dateInput || ''));
  }
}
