function clearFile(inputId, displayId, iconId) {
    document.getElementById(inputId).value = '';
    document.getElementById(displayId).value = '';
    if (iconId) document.getElementById(iconId).style.display = 'none';
}

function showFileName(inputId, displayId, iconId) {
    const input = document.getElementById(inputId);
    const display = document.getElementById(displayId);
    const icon = document.getElementById(iconId);
    if (input.files.length > 0) {
        let name = input.files[0].webkitRelativePath || input.files[0].name;
        // For folder upload, show folder name
        if (input.files[0].webkitRelativePath) {
            name = input.files[0].webkitRelativePath.split('/')[0];
        }
        display.value = name;
        if (icon) icon.style.display = 'inline-block';
    }
}
// Frontend automation control for Flask backend

function getSettings() {
    const headless = document.querySelector('input[name="headless"]').checked;
    const threads = parseInt(document.querySelector('input[name="threads"]').value) || 1;
    const strategy = document.querySelector('select[name="strategy"]').value;
    const mention = document.querySelector('input[name="mention"]').value;
    const platform = document.querySelector('select[name="platform"]').value;
    return {
        headless,
        threads,
        strategy,
        mention,
        platform,
        use_proxies: true // Always true if proxy section is present
    };
}

window.startAutomation = function() {
    // Check if account folder is selected
    const accountInput = document.getElementById('account_file_input');
    if (!accountInput.files || accountInput.files.length === 0) {
        showFlashMessage('You must upload an account folder before performing this action.', 'warning');
        return;
    }
    const settings = getSettings();
    showFlashMessage('Automation starting...', 'info');
    fetch('/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    })
    .then(res => res.json())
    .then(data => {
        updateLog(data.logs);
        showFlashMessage(`Started automating ${settings.platform.charAt(0).toUpperCase() + settings.platform.slice(1)}!`, 'success');
    })
    .catch(err => {
        updateLog([`Error starting automation: ${err}`]);
        showFlashMessage('Failed to start automation.', 'danger');
    });
}

window.stopAutomation = function() {
    fetch('/stop', {
        method: 'POST'
    })
    .then(() => {
        updateLog(''); // Clear the runlog
        showFlashMessage('Stopped automating! Log cleared.', 'warning');
    })
    .catch(err => {
        updateLog([`Error stopping automation: ${err}`]);
        showFlashMessage('Failed to stop automation.', 'danger');
    });
}

function showFlashMessage(message, category) {
    const flashDiv = document.createElement('div');
    flashDiv.className = `flash ${category}`;
    flashDiv.textContent = message;
    document.body.prepend(flashDiv);
    setTimeout(() => flashDiv.remove(), 4000);
}

function updateLog(logs) {
    const logOutput = document.getElementById('log-output');
    logOutput.value = Array.isArray(logs) ? logs.join('\n') : logs;
}

function fetchLog() {
    fetch('/log')
    .then(res => res.json())
    .then(data => {
        updateLog(data.logs);
        if (document.getElementById('progress-card')) {
            document.getElementById('progress-card').textContent = `${data.current_progress} / ${data.total_accounts}`;
        }
        if (document.getElementById('success-rate-card')) {
            document.getElementById('success-rate-card').textContent = `${data.success_rate}%`;
        }
        if (document.getElementById('runtime-status-info')) {
            document.getElementById('runtime-status-info').textContent = `Status: ${data.status}`;
        }
        if (document.getElementById('total-accounts-card')) {
            document.getElementById('total-accounts-card').textContent = data.total_accounts;
        }
        if (document.getElementById('proxy-card')) {
            document.getElementById('proxy-card').textContent = data.proxies;
        }
        if (document.getElementById('comment-card')) {
            document.getElementById('comment-card').textContent = data.comments;
        }
    });
}

function saveLog() {
    const logOutput = document.getElementById('log-output');
    fetch('/save_log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log: logOutput.value })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'saved') {
            showFlashMessage('Log saved!', 'success');
        } else {
            showFlashMessage('Error saving log.', 'danger');
        }
    })
    .catch(() => showFlashMessage('Error saving log.', 'danger'));
}

function clearLog() {
    updateLog('');
    // Prevent log from showing again until new logs are generated
    setTimeout(() => {
        const logOutput = document.getElementById('log-output');
        logOutput.value = '';
    }, 100);
}

setInterval(fetchLog, 2000);
