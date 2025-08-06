from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from werkzeug.utils import secure_filename
from webdriver_manager.chrome import ChromeDriverManager
import threading
import time
import os

app = Flask(__name__)
app.secret_key = 'secret'
log_lines = []
automation_running = False
success_count = 0
total_runs = 0
current_progress = 0
total_accounts = 0
proxies_count = 0
comments_count = 0

UPLOAD_FOLDER = 'uploads'
ACCOUNTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'accounts')
PROXIES_FOLDER = os.path.join(UPLOAD_FOLDER, 'proxies')
COMMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'comments')

os.makedirs(ACCOUNTS_FOLDER, exist_ok=True)
os.makedirs(PROXIES_FOLDER, exist_ok=True)
os.makedirs(COMMENTS_FOLDER, exist_ok=True)

PLATFORM_URLS = {
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "tiktok": "https://tiktok.com"
}

def log(msg):
    log_lines.append(msg)
    print(msg)

def parse_account_file_to_table(filepath):
    data = {
        'no': 0,
        'username': '',
        'privatekey': '',
        'cookies': '',
        'email': '',
        'passmail': '',
        'phone': '',
        'recoverymail': ''
    }
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
            for line in lines:
                if line.startswith('username:'):
                    data['username'] = line.split(':', 1)[1].strip()
                elif line.startswith('privatekey:'):
                    data['privatekey'] = line.split(':', 1)[1].strip()
                elif line.startswith('cookies:'):
                    data['cookies'] = line.split(':', 1)[1].strip()
                elif line.startswith('email:'):
                    data['email'] = line.split(':', 1)[1].strip()
                elif line.startswith('mailpass:'):
                    data['passmail'] = line.split(':', 1)[1].strip()
                elif line.startswith('phone:'):
                    data['phone'] = line.split(':', 1)[1].strip()
                elif line.startswith('recoverymail:'):
                    data['recoverymail'] = line.split(':', 1)[1].strip()
        return data
    except Exception:
        return data

@app.route('/')
def index():
    global total_accounts, proxies_count, comments_count
    def is_valid_account_file(filepath):
        try:
            with open(os.path.join(ACCOUNTS_FOLDER, filepath), 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                has_user = any(line.startswith('username:') and line.strip() != 'username:' for line in lines)
                has_pass = any(line.startswith('password:') and line.strip() != 'password:' for line in lines)
                return has_user and has_pass
        except Exception:
            return False

    account_files = os.listdir(ACCOUNTS_FOLDER)
    total_accounts = sum(1 for f in account_files if is_valid_account_file(f))
    proxies_count = len(os.listdir(PROXIES_FOLDER))
    comments_count = len(os.listdir(COMMENTS_FOLDER))
    # If no valid account folder, set cards to N/A or 0
    if total_accounts == 0:
        stats = {
            'accounts': 0,
            'proxies': 0,
            'comments': 0,
            'success_rate': 'N/A',
            'progress': 'N/A',
            'status': 'Idle',
            'total_accounts': 0,
            'proxies_count': 0,
            'comments_count': 0
        }
    else:
        stats = {
            'accounts': total_accounts,
            'proxies': proxies_count,
            'comments': comments_count,
            'success_rate': calculate_success_rate(),
            'progress': f"{current_progress} / {total_accounts}",
            'status': 'Running' if automation_running else 'Idle',
            'total_accounts': total_accounts,
            'proxies_count': proxies_count,
            'comments_count': comments_count
        }

    account_files = os.listdir(ACCOUNTS_FOLDER)
    accounts_table = []
    count = 1
    for filename in account_files:
        full_path = os.path.join(ACCOUNTS_FOLDER, filename)
        parsed = parse_account_file_to_table(full_path)
        parsed['no'] = count
        accounts_table.append(parsed)
        count += 1

    return render_template('index.html', stats=stats, log_content='\n'.join(log_lines), accounts_table=accounts_table)

@app.route('/upload', methods=['POST'])
def upload():
    folder_map = {
        'account_folder': ACCOUNTS_FOLDER,
        'proxies_file': PROXIES_FOLDER,
        'comments_file': COMMENTS_FOLDER
    }
    for field, folder in folder_map.items():
        file = request.files.get(field)
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(folder, filename))
    
    account_files = os.listdir(ACCOUNTS_FOLDER)
    table_data = []
    count = 1

    for filename in account_files:
        filepath = os.path.join(ACCOUNTS_FOLDER, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')  # Adjust delimiter if needed
                if len(parts) >= 7:
                    table_data.append({
                        'no': count,
                        'username': parts[0],
                        'privatekey': parts[1],
                        'cookies': parts[2],
                        'email': parts[3],
                        'passmail': parts[4],
                        'phone': parts[5],
                        'recoverymail': parts[6],
                    })
                    count += 1
    session['accounts_table'] = table_data
    flash('Files uploaded!', 'success')
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start():
    global automation_running, current_progress, success_count, total_runs
    if automation_running:
        return jsonify({'status': 'already running', 'logs': log_lines})
    # Count valid accounts before starting
    def is_valid_account_file(filepath):
        try:
            with open(os.path.join(ACCOUNTS_FOLDER, filepath), 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                has_user = any(line.startswith('username:') and line.strip() != 'username:' for line in lines)
                has_pass = any(line.startswith('password:') and line.strip() != 'password:' for line in lines)
                return has_user and has_pass
        except Exception:
            return False

    account_files = os.listdir(ACCOUNTS_FOLDER)
    valid_accounts = [f for f in account_files if is_valid_account_file(f)]
    if not valid_accounts:
        flash("Account folder not selected. Please choose an account folder before starting automation.", "warning")
        log("Account folder not selected. Automation not started.")
        return jsonify({'status': 'no_accounts', 'logs': log_lines})

    automation_running = True
    success_count = 0
    total_runs = 0
    current_progress = 0
    settings = request.get_json()
    flash("Automation started", "info")
    thread = threading.Thread(target=run_automation, args=(settings,))
    thread.start()
    return jsonify({'status': 'started', 'logs': log_lines})

@app.route('/stop', methods=['POST'])
def stop():
    global automation_running
    automation_running = False
    flash("Automation stopped", "warning")
    log("Automation manually stopped.")
    return ('', 204)

@app.route('/log')
def get_log():
    global total_accounts, proxies_count, comments_count
    total_accounts = len(os.listdir(ACCOUNTS_FOLDER))
    proxies_count = len(os.listdir(PROXIES_FOLDER))
    comments_count = len(os.listdir(COMMENTS_FOLDER))
    return jsonify({
        'logs': log_lines,
        'success_rate': calculate_success_rate(),
        'status': 'Running' if automation_running else 'Idle',
        'current_progress': current_progress,
        'total_accounts': total_accounts,
        'proxies': proxies_count,
        'comments': comments_count
    })

def calculate_success_rate():
    if total_runs == 0:
        return 0
    return int((success_count / total_runs) * 100)

def run_automation(settings):
    global automation_running, current_progress, total_runs, success_count, total_accounts
    platform = settings.get('platform', 'facebook')
    headless = settings.get('headless', True)
    use_proxies = settings.get('use_proxies', False)
    mention = settings.get('mention', '').strip()
    accounts = os.listdir(ACCOUNTS_FOLDER)
    total_accounts = len(accounts) if accounts else 1
    if not accounts:
        accounts = ['dummy']
    try:
        for idx, account in enumerate(accounts, 1):
            if not automation_running:
                log("Automation stopped by user.")
                break

            log(f"Starting automation for platform: {platform} (Account: {account})")
            if mention:
                log(f"Mention field: {mention}")

            # Read credentials from file
            account_path = os.path.join(ACCOUNTS_FOLDER, account)
            username = ''
            password = ''
            cookies_raw = ''

            try:
                with open(account_path, 'r', encoding='utf-8') as f:
                    lines = f.read().splitlines()
                    for line in lines:
                        if line.startswith('username:'):
                            username = line.split(':', 1)[1].strip()
                        elif line.startswith('password:'):
                            password = line.split(':', 1)[1].strip()
                        elif line.startswith('cookies:'):
                            cookies_raw = line.split(':', 1)[1].strip()

                if not username or not password:
                    log(f"Invalid account file format: {account}")
                    total_runs += 1
                    current_progress = idx
                    continue
            except Exception as e:
                log(f"Failed to read account file {account}: {e}")
                total_runs += 1
                current_progress = idx
                continue

            # Set up Chrome
            options = Options()
            if headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

            url = PLATFORM_URLS.get(platform, "https://facebook.com")
            driver.get(url)
            log(f"{platform.capitalize()} automation started for account: {account}")

            # --- Attempt Cookie Login if cookies are provided ---
            cookie_login_success = False
            if cookies_raw:
                try:
                    import json
                    cookies = json.loads(cookies_raw)
                    for cookie in cookies:
                        driver.add_cookie(cookie)
                    driver.get(url)
                    time.sleep(5)
                    if platform == "facebook" and "login" not in driver.current_url:
                        cookie_login_success = True
                    elif platform == "instagram" and "accounts" not in driver.current_url:
                        cookie_login_success = True
                    elif platform == "tiktok" and "login" not in driver.current_url:
                        cookie_login_success = True

                    if cookie_login_success:
                        log(f"Cookie login succeeded for {username}")
                        success_count += 1
                except Exception as e:
                    log(f"Cookie login failed for {username}: {e}")

            # --- Actual login automation (fallback to username/password) ---
            try:
                from selenium.webdriver.common.by import By
                if not cookie_login_success:
                    if platform == "facebook":
                        log("Logging in to Facebook...")
                        driver.get("https://www.facebook.com/login")
                        time.sleep(3)
                        email_input = driver.find_element(By.ID, "email")
                        pass_input = driver.find_element(By.ID, "pass")
                        email_input.send_keys(username)
                        pass_input.send_keys(password)
                        pass_input.submit()
                        time.sleep(5)
                        if "login" in driver.current_url:
                            log(f"Login failed for {username}")
                        else:
                            log(f"Login succeeded for {username}")
                            success_count += 1

                    elif platform == "instagram":
                        log("Logging in to Instagram...")
                        driver.get("https://www.instagram.com/accounts/login/")
                        time.sleep(3)
                        username_input = driver.find_element(By.NAME, "username")
                        password_input = driver.find_element(By.NAME, "password")
                        username_input.send_keys(username)
                        password_input.send_keys(password)
                        password_input.submit()
                        time.sleep(5)
                        if "login" in driver.current_url or "challenge" in driver.current_url:
                            log(f"Login failed for {username}")
                        else:
                            log(f"Login succeeded for {username}")
                            success_count += 1

                    elif platform == "tiktok":
                        log("Logging in to TikTok...")
                        driver.get("https://www.tiktok.com/login/phone-or-email/email")
                        time.sleep(5)
                        try:
                            email_input = driver.find_element(By.NAME, "email")
                            pass_input = driver.find_element(By.NAME, "password")
                            email_input.send_keys(username)
                            pass_input.send_keys(password)
                            pass_input.submit()
                            time.sleep(5)
                            if "login" in driver.current_url or "verify" in driver.current_url:
                                log(f"Login failed or needs verification for {username}")
                            else:
                                log(f"Login succeeded for {username}")
                                success_count += 1
                        except Exception as e:
                            log(f"Error during TikTok login: {e}")
                    else:
                        log("Unknown platform. Skipping actions.")
            except Exception as e:
                log(f"Error during automation steps: {e}")

            driver.quit()
            log(f"{platform.capitalize()} automation complete for account: {account}")
            current_progress = idx
            total_runs += 1
            log(f"Success rate: {calculate_success_rate()}%")

        automation_running = False
        log("Automation finished.")
    except Exception as e:
        log(f"Error: {e}")
        automation_running = False


@app.route('/save_log', methods=['POST'])
def save_log():
    try:
        with open('log.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
        return jsonify({'status': 'saved'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ ==  "__main__":
    app.run(debug=True)