# Dev by: jyavaz
# GitHub: https://github.com/jyavaz68/

import os
import subprocess
import datetime
import shutil
import sys
import time
import urllib.request
import urllib.error
import uuid
import threading
import itertools
import shlex
import zipfile
import json
import re
import socket
import tempfile
import fcntl

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class Spinner:
    def __init__(self, message="Processing..."):
        self.spinner_cycle = itertools.cycle(['-', '\\', '|', '/'])
        self.stop_running = threading.Event()
        self.message = message
        self.thread = threading.Thread(target=self.spin)

    def spin(self):
        while not self.stop_running.is_set():
            sys.stdout.write(f"\r{Colors.YELLOW}⏳ {next(self.spinner_cycle)} {self.message}{Colors.RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * (len(self.message) + 15) + '\r')
        sys.stdout.flush()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop_running.set()
        self.thread.join()

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  [INFO]{Colors.RESET} {msg}")

def print_success(msg):
    print(f"{Colors.GREEN}✅ [SUCCESS]{Colors.RESET} {msg}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  [WARNING]{Colors.RESET} {msg}")

def print_error(msg):
    print(f"{Colors.RED}❌ [ERROR]{Colors.RESET} {msg}")

def print_header(title):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=================================================={Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}        {title}        {Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}=================================================={Colors.RESET}\n")

def pause_and_return():
    input(f"\n{Colors.YELLOW}Press [ENTER] to return to the main menu...{Colors.RESET}")

try:
    import paramiko
except ImportError:
    print(f"{Colors.YELLOW}⏳ Required libraries not found. Starting background installation...{Colors.RESET}")
    with Spinner("Installing required packages (Paramiko, unzip)... Please wait"):
        try:
            subprocess.check_call(["apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.check_call(["apt-get", "install", "-y", "python3-paramiko", "python3-pip", "unzip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import paramiko
    print(f"{Colors.GREEN}✅ Libraries installed successfully!{Colors.RESET}\n")

def run_command(command, output_file=None, cwd=None, quiet=True):
    try:
        if output_file:
            with open(output_file, "w") as f:
                subprocess.run(command, shell=True, check=True, stdout=f, stderr=subprocess.PIPE, cwd=cwd)
        else:
            stdout_target = subprocess.DEVNULL if quiet else None
            subprocess.run(command, shell=True, check=True, stdout=stdout_target, stderr=subprocess.PIPE, cwd=cwd)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {command}")
        if e.stderr:
            print_error(f"Details: {e.stderr.decode('utf-8').strip()}")
        return False

def _read_env_var(env_path, var_name):
    if not os.path.isfile(env_path):
        return None
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key == var_name:
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                        value = value[1:-1]
                    return value
    except Exception:
        pass
    return None

def _update_env_var_local(env_path, var_name, new_value):
    try:
        lines = []
        found = False
        if os.path.isfile(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key == var_name:
                    lines[i] = f'{var_name}="{new_value}"\n'
                    found = True
                    break
        if not found:
            lines.append(f'{var_name}="{new_value}"\n')
        with open(env_path, "w") as f:
            f.writelines(lines)
        return True
    except Exception:
        return False

def _update_env_var_ssh(ssh, env_path, var_name, new_value):
    escaped = new_value.replace('"', '\\"')
    cmd = (
        f"grep -q '^{var_name}=' {env_path} 2>/dev/null && "
        f"sed -i 's|^{var_name}=.*|{var_name}=\"{escaped}\"|' {env_path} || "
        f"echo '{var_name}=\"{escaped}\"' >> {env_path}"
    )
    exit_code, _, _ = ssh_shell(ssh, cmd)
    return exit_code == 0

def _test_mysql_password_local(compose_dir, password):
    if password is None:
        return False
    cmd = "docker compose exec -T mysql sh -c " + shlex.quote(f'mysql -uroot -p{password} -e "SELECT 1;"')
    ok, _, _ = local_shell(cmd, cwd=compose_dir)
    return ok

def _test_mysql_password_ssh(ssh, compose_dir, password):
    if password is None:
        return False
    cmd = f"cd {compose_dir} && docker compose exec -T mysql sh -c " + shlex.quote(f'mysql -uroot -p{password} -e "SELECT 1;"')
    exit_code, _, _ = ssh_shell(ssh, cmd)
    return exit_code == 0

def capture_current_mysql_password_local(compose_dir):
    env_path = os.path.join(compose_dir, ".env")
    current_password = _read_env_var(env_path, "MYSQL_ROOT_PASSWORD")
    if not current_password:
        return None
    running = _running_compose_ids_local(compose_dir)
    if running and _test_mysql_password_local(compose_dir, current_password):
        print_info("Verified the current install's MySQL root password before wiping anything — keeping it as a fallback.")
    return current_password

def capture_current_mysql_password_ssh(ssh, compose_dir):
    env_path = f"{compose_dir}/.env"
    exit_code, current_password, _ = ssh_shell(
        ssh,
        f"grep '^MYSQL_ROOT_PASSWORD=' {env_path} 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\"'"
    )
    current_password = current_password.strip() if exit_code == 0 else None
    if not current_password:
        return None
    running = _running_compose_ids_ssh(ssh, compose_dir)
    if running and _test_mysql_password_ssh(ssh, compose_dir, current_password):
        print_info("Verified the current install's MySQL root password before wiping anything — keeping it as a fallback.")
    return current_password

def resolve_mysql_root_password_local(compose_dir, extra_candidates=None):
    env_path = os.path.join(compose_dir, ".env")
    candidates = []
    env_password = _read_env_var(env_path, "MYSQL_ROOT_PASSWORD")
    if env_password:
        candidates.append(env_password)
    for c in (extra_candidates or []):
        if c and c not in candidates:
            candidates.append(c)

    for pw in candidates:
        if _test_mysql_password_local(compose_dir, pw):
            if pw != env_password:
                if _update_env_var_local(env_path, "MYSQL_ROOT_PASSWORD", pw):
                    print_success(f"Found a working MySQL root password and synced it into .env.")
                else:
                    print_warning("Found a working password but couldn't auto-update .env — update it manually.")
            return pw

    print_warning("None of the known passwords (.env, pre-restore password) matched the restored database.")
    print_warning("(This happens because MYSQL_ROOT_PASSWORD only applies the first time MySQL initializes — not on every start.)")
    for attempt in range(3):
        manual_pw = input(f"{Colors.CYAN}🔑 Enter the correct MySQL root password: {Colors.RESET}").strip()
        if _test_mysql_password_local(compose_dir, manual_pw):
            print_success("Password accepted.")
            if _update_env_var_local(env_path, "MYSQL_ROOT_PASSWORD", manual_pw):
                print_success(".env updated so future runs use this password automatically.")
            else:
                print_warning("Could not update .env automatically — update it manually.")
            return manual_pw
        print_error("That password didn't work either.")
    return None

def resolve_mysql_root_password_ssh(ssh, compose_dir, extra_candidates=None):
    env_path = f"{compose_dir}/.env"
    exit_code, env_password, _ = ssh_shell(
        ssh,
        f"grep '^MYSQL_ROOT_PASSWORD=' {env_path} 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\"'"
    )
    env_password = env_password.strip() if exit_code == 0 else None
    candidates = []
    if env_password:
        candidates.append(env_password)
    for c in (extra_candidates or []):
        if c and c not in candidates:
            candidates.append(c)

    for pw in candidates:
        if _test_mysql_password_ssh(ssh, compose_dir, pw):
            if pw != env_password:
                if _update_env_var_ssh(ssh, env_path, "MYSQL_ROOT_PASSWORD", pw):
                    print_success("Found a working MySQL root password and synced it into .env.")
                else:
                    print_warning("Found a working password but couldn't auto-update .env — update it manually.")
            return pw

    print_warning("None of the known passwords (.env, pre-restore password) matched the restored database.")
    print_warning("(This happens because MYSQL_ROOT_PASSWORD only applies the first time MySQL initializes — not on every start.)")
    for attempt in range(3):
        manual_pw = input(f"{Colors.CYAN}🔑 Enter the correct MySQL root password: {Colors.RESET}").strip()
        if _test_mysql_password_ssh(ssh, compose_dir, manual_pw):
            print_success("Password accepted.")
            if _update_env_var_ssh(ssh, env_path, "MYSQL_ROOT_PASSWORD", manual_pw):
                print_success(".env updated so future runs use this password automatically.")
            else:
                print_warning("Could not update .env automatically — update it manually.")
            return manual_pw
        print_error("That password didn't work either.")
    return None

def _escape_mysql_literal(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")

def sync_app_db_credentials_local(compose_dir, mysql_root_password):
    env_path = os.path.join(compose_dir, ".env")
    db_user = _read_env_var(env_path, "DB_USER") or "pasarguard"
    db_password = _read_env_var(env_path, "DB_PASSWORD")
    db_name = _read_env_var(env_path, "DB_NAME") or "pasarguard"

    if not db_password:
        print_warning("DB_PASSWORD not found in .env — skipping application DB user sync.")
        return False

    print_info(f"Syncing application DB user '{db_user}' password with .env...")
    sql = (
        f"CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{safe_pw}'; "
        f"ALTER USER '{db_user}'@'%' IDENTIFIED BY '{safe_pw}'; "
        f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'%'; "
        f"FLUSH PRIVILEGES;"
    )
    mysql_cmd = shlex.join(["mysql", "-uroot", f"-p{mysql_root_password}", "-e", sql])
    cmd = "docker compose exec -T mysql sh -c " + shlex.quote(mysql_cmd)
    ok, _, err = local_shell(cmd, cwd=compose_dir)
    if not ok:
        print_error(f"Failed to sync application DB user '{db_user}'.")
        if err:
            print_error(err)
        return False

    verify_mysql_cmd = shlex.join(["mysql", f"-u{db_user}", f"-p{db_password}", "-e", f"USE {db_name}; SELECT 1;"])
    verify_cmd = "docker compose exec -T mysql sh -c " + shlex.quote(verify_mysql_cmd)
    if not local_shell(verify_cmd, cwd=compose_dir)[0]:
        print_error(f"Synced '{db_user}' but the new credentials still don't authenticate — aborting.")
        return False

    print_success(f"Application DB user '{db_user}' is synced with .env and verified working.")
    return True

def sync_app_db_credentials_ssh(ssh, compose_dir, mysql_root_password):
    env_path = f"{compose_dir}/.env"
    exit_code, db_user, _ = ssh_shell(
        ssh, f"grep '^DB_USER=' {env_path} 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\"'"
    )
    db_user = db_user.strip() if exit_code == 0 and db_user.strip() else "pasarguard"

    exit_code, db_password, _ = ssh_shell(
        ssh, f"grep '^DB_PASSWORD=' {env_path} 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\"'"
    )
    db_password = db_password.strip() if exit_code == 0 else None

    exit_code, db_name, _ = ssh_shell(
        ssh, f"grep '^DB_NAME=' {env_path} 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\"'"
    )
    db_name = db_name.strip() if exit_code == 0 and db_name.strip() else "pasarguard"

    if not db_password:
        print_warning("DB_PASSWORD not found in .env — skipping application DB user sync.")
        return False

    print_info(f"Syncing application DB user '{db_user}' password with .env...")
    safe_pw = _escape_mysql_literal(db_password)
    sql = (
        f"CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{safe_pw}'; "
        f"ALTER USER '{db_user}'@'%' IDENTIFIED BY '{safe_pw}'; "
        f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'%'; "
        f"FLUSH PRIVILEGES;"
    )
    mysql_cmd = shlex.join(["mysql", "-uroot", f"-p{mysql_root_password}", "-e", sql])
    cmd = f"cd {compose_dir} && docker compose exec -T mysql sh -c " + shlex.quote(mysql_cmd)
    exit_code, _, err = ssh_shell(ssh, cmd)
    if exit_code != 0:
        print_error(f"Failed to sync application DB user '{db_user}'.")
        if err:
            print_error(err)
        return False

    verify_mysql_cmd = shlex.join(["mysql", f"-u{db_user}", f"-p{db_password}", "-e", f"USE {db_name}; SELECT 1;"])
    verify_cmd = f"cd {compose_dir} && docker compose exec -T mysql sh -c " + shlex.quote(verify_mysql_cmd)
    verify_code, _, _ = ssh_shell(ssh, verify_cmd)
    if verify_code != 0:
        print_error(f"Synced '{db_user}' but the new credentials still don't authenticate — aborting.")
        return False

    print_success(f"Application DB user '{db_user}' is synced with .env and verified working.")
    return True

PASARGUARD_DIR = "/opt/pasarguard"
PG_NODE_DIR = "/opt/pg-node"
PASARGUARD_DATA_DIR = "/var/lib/pasarguard"
PG_NODE_DATA_DIR = "/var/lib/pg-node"

COMPOSE_DOWN_TIMEOUT = 30
POSTGRES_READY_MAX_WAIT = 120
POSTGRES_READY_INTERVAL = 2
COMPOSE_UP_MAX_WAIT = 120
COMPOSE_UP_INTERVAL = 3
COMPOSE_STOP_RETRIES = 3

def local_shell(command, cwd=None):
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def ssh_shell(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    return exit_status, stdout.read().decode().strip(), stderr.read().decode().strip()

def _running_compose_ids_local(compose_dir):
    _, out, _ = local_shell("docker compose ps -q --status running", cwd=compose_dir)
    return [line for line in out.splitlines() if line.strip()]

def _running_compose_ids_ssh(ssh, compose_dir):
    _, out, _ = ssh_shell(
        ssh, f"cd {compose_dir} && docker compose ps -q --status running 2>/dev/null || true"
    )
    return [line for line in out.splitlines() if line.strip()]

def _expected_running_count_local(compose_dir, services):
    if services:
        return len(services)
    ok, out, _ = local_shell("docker compose config --services", cwd=compose_dir)
    if not ok:
        return 0
    return len([line for line in out.splitlines() if line.strip()])

def _expected_running_count_ssh(ssh, compose_dir, services):
    if services:
        return len(services)
    exit_code, out, _ = ssh_shell(ssh, f"cd {compose_dir} && docker compose config --services 2>/dev/null")
    if exit_code != 0:
        return 0
    return len([line for line in out.splitlines() if line.strip()])

def stop_compose_stack_local(compose_dir, label):
    if not os.path.isdir(compose_dir):
        print_warning(f"{label}: {compose_dir} not found — nothing to stop.")
        return True
    if not os.path.isfile(os.path.join(compose_dir, "docker-compose.yml")):
        print_warning(f"{label}: no docker-compose.yml — skipping stop.")
        return True

    print_info(f"Stopping {label} containers in {compose_dir}...")
    for attempt in range(1, COMPOSE_STOP_RETRIES + 1):
        run_command(
            f"docker compose down --remove-orphans -t {COMPOSE_DOWN_TIMEOUT}",
            cwd=compose_dir, quiet=True
        )
        run_command("docker compose stop -t 10 2>/dev/null || true", cwd=compose_dir, quiet=True)
        run_command("docker compose rm -f 2>/dev/null || true", cwd=compose_dir, quiet=True)

        running = _running_compose_ids_local(compose_dir)
        if not running:
            print_success(f"{label}: all containers stopped.")
            return True

        print_warning(f"{label}: {len(running)} container(s) still running (attempt {attempt}/{COMPOSE_STOP_RETRIES})...")
        time.sleep(2)

    _, status, _ = local_shell("docker compose ps", cwd=compose_dir)
    print_error(f"{label}: could not stop all containers.")
    if status:
        print_error(status)
    return False

def stop_compose_stack_ssh(ssh, compose_dir, label):
    exit_code, _, _ = ssh_shell(ssh, f"test -d {compose_dir} && test -f {compose_dir}/docker-compose.yml")
    if exit_code != 0:
        print_warning(f"{label}: {compose_dir} not found or missing docker-compose.yml — skipping stop.")
        return True

    print_info(f"Stopping {label} containers in {compose_dir}...")
    for attempt in range(1, COMPOSE_STOP_RETRIES + 1):
        ssh_shell(ssh, f"cd {compose_dir} && docker compose down --remove-orphans -t {COMPOSE_DOWN_TIMEOUT}")
        ssh_shell(ssh, f"cd {compose_dir} && docker compose stop -t 10 2>/dev/null || true")
        ssh_shell(ssh, f"cd {compose_dir} && docker compose rm -f 2>/dev/null || true")

        running = _running_compose_ids_ssh(ssh, compose_dir)
        if not running:
            print_success(f"{label}: all containers stopped.")
            return True

        print_warning(f"{label}: {len(running)} container(s) still running (attempt {attempt}/{COMPOSE_STOP_RETRIES})...")
        time.sleep(2)

    _, status, _ = ssh_shell(ssh, f"cd {compose_dir} && docker compose ps")
    print_error(f"{label}: could not stop all containers.")
    if status:
        print_error(status)
    return False

def clean_restore_directories_local():
    targets = [
        (PASARGUARD_DIR, "Pasarguard config (/opt/pasarguard)"),
        (PG_NODE_DIR, "PG-Node config (/opt/pg-node)"),
        (PASARGUARD_DATA_DIR, "Pasarguard data (/var/lib/pasarguard)"),
        (PG_NODE_DATA_DIR, "PG-Node data (/var/lib/pg-node)"),
    ]
    print_info("Cleaning target directories...")
    for path, desc in targets:
        if not run_command(f"rm -rf {path} && mkdir -p {path}", quiet=True):
            print_error(f"Failed to clean {desc}")
            return False
        if not os.path.isdir(path):
            print_error(f"Directory missing after cleanup: {path}")
            return False
    print_success("All target directories cleaned and recreated.")
    return True

def clean_restore_directories_ssh(ssh):
    targets = [
        (PASARGUARD_DIR, "Pasarguard config (/opt/pasarguard)"),
        (PG_NODE_DIR, "PG-Node config (/opt/pg-node)"),
        (PASARGUARD_DATA_DIR, "Pasarguard data (/var/lib/pasarguard)"),
        (PG_NODE_DATA_DIR, "PG-Node data (/var/lib/pg-node)"),
    ]
    print_info("Cleaning target directories...")
    for path, desc in targets:
        exit_code, _, err = ssh_shell(ssh, f"rm -rf {path} && mkdir -p {path}")
        if exit_code != 0:
            print_error(f"Failed to clean {desc}")
            if err:
                print_error(err)
            return False
        verify_code, _, _ = ssh_shell(ssh, f"test -d {path}")
        if verify_code != 0:
            print_error(f"Directory missing after cleanup: {path}")
            return False
    print_success("All target directories cleaned and recreated.")
    return True

def wait_for_postgres_ready_local():
    print_info("Waiting for timescaledb to become ready...")
    deadline = time.time() + POSTGRES_READY_MAX_WAIT
    while time.time() < deadline:
        ok, _, _ = local_shell(
            "docker compose exec -T timescaledb pg_isready -U pasarguard -d postgres",
            cwd=PASARGUARD_DIR,
        )
        if ok:
            print_success("Database is ready for restore operations.")
            return True
        time.sleep(POSTGRES_READY_INTERVAL)
    print_error("Database did not become ready in time.")
    return False

def wait_for_postgres_ready_ssh(ssh):
    print_info("Waiting for timescaledb to become ready...")
    deadline = time.time() + POSTGRES_READY_MAX_WAIT
    while time.time() < deadline:
        exit_code, _, _ = ssh_shell(
            ssh,
            f"cd {PASARGUARD_DIR} && docker compose exec -T timescaledb pg_isready -U pasarguard -d postgres",
        )
        if exit_code == 0:
            print_success("Database is ready for restore operations.")
            return True
        time.sleep(POSTGRES_READY_INTERVAL)
    print_error("Database did not become ready in time.")
    return False

def wait_for_mysql_ready_local():
    print_info("Waiting for mysql to become ready...")
    deadline = time.time() + POSTGRES_READY_MAX_WAIT
    while time.time() < deadline:
        ok, _, _ = local_shell(
            "docker compose exec -T mysql sh -c 'mysqladmin ping -uroot -p\"$MYSQL_ROOT_PASSWORD\" --silent'",
            cwd=PASARGUARD_DIR,
        )
        if ok:
            print_success("MySQL is ready for restore operations.")
            return True
        time.sleep(POSTGRES_READY_INTERVAL)
    print_error("MySQL did not become ready in time.")
    return False

def wait_for_mysql_ready_ssh(ssh):
    print_info("Waiting for mysql to become ready...")
    deadline = time.time() + POSTGRES_READY_MAX_WAIT
    while time.time() < deadline:
        exit_code, _, _ = ssh_shell(
            ssh,
            f"cd {PASARGUARD_DIR} && docker compose exec -T mysql sh -c 'mysqladmin ping -uroot -p\"$MYSQL_ROOT_PASSWORD\" --silent'",
        )
        if exit_code == 0:
            print_success("MySQL is ready for restore operations.")
            return True
        time.sleep(POSTGRES_READY_INTERVAL)
    print_error("MySQL did not become ready in time.")
    return False

def start_compose_stack_local(compose_dir, label, services=None, wait_postgres=False, wait_mysql=False):
    if not os.path.isdir(compose_dir) or not os.path.isfile(os.path.join(compose_dir, "docker-compose.yml")):
        print_error(f"{label}: compose project not found at {compose_dir}")
        return False

    svc_part = " ".join(services) if services else ""
    print_info(f"Starting {label} containers{f' ({svc_part})' if svc_part else ''}...")
    if not run_command(f"docker compose up -d {svc_part}".strip(), cwd=compose_dir):
        print_error(f"{label}: docker compose up failed.")
        return False

    if wait_postgres and not wait_for_postgres_ready_local():
        return False
    if wait_mysql and not wait_for_mysql_ready_local():
        return False

    expected = _expected_running_count_local(compose_dir, services)
    if expected == 0 and not wait_postgres:
        print_warning(f"{label}: could not read service list; assuming startup succeeded.")
        return True

    print_info(f"Verifying {label} containers are running...")
    deadline = time.time() + COMPOSE_UP_MAX_WAIT
    while time.time() < deadline:
        running = _running_compose_ids_local(compose_dir)
        if len(running) >= expected:
            print_success(f"{label}: {len(running)} container(s) running.")
            return True
        time.sleep(COMPOSE_UP_INTERVAL)

    _, status, _ = local_shell("docker compose ps", cwd=compose_dir)
    print_error(f"{label}: startup verification failed.")
    if status:
        print_error(status)
    return False

def start_compose_stack_ssh(ssh, compose_dir, label, services=None, wait_postgres=False, wait_mysql=False):
    exit_code, _, _ = ssh_shell(ssh, f"test -d {compose_dir} && test -f {compose_dir}/docker-compose.yml")
    if exit_code != 0:
        print_error(f"{label}: compose project not found at {compose_dir}")
        return False

    svc_part = " ".join(services) if services else ""
    print_info(f"Starting {label} containers{f' ({svc_part})' if svc_part else ''}...")
    exit_code, _, err = ssh_shell(ssh, f"cd {compose_dir} && docker compose up -d {svc_part}".strip())
    if exit_code != 0:
        print_error(f"{label}: docker compose up failed.")
        if err:
            print_error(err)
        return False

    if wait_postgres and not wait_for_postgres_ready_ssh(ssh):
        return False
    if wait_mysql and not wait_for_mysql_ready_ssh(ssh):
        return False

    expected = _expected_running_count_ssh(ssh, compose_dir, services)
    if expected == 0 and not wait_postgres:
        print_warning(f"{label}: could not read service list; assuming startup succeeded.")
        return True

    print_info(f"Verifying {label} containers are running...")
    deadline = time.time() + COMPOSE_UP_MAX_WAIT
    while time.time() < deadline:
        running = _running_compose_ids_ssh(ssh, compose_dir)
        if len(running) >= expected:
            print_success(f"{label}: {len(running)} container(s) running.")
            return True
        time.sleep(COMPOSE_UP_INTERVAL)

    _, status, _ = ssh_shell(ssh, f"cd {compose_dir} && docker compose ps")
    print_error(f"{label}: startup verification failed.")
    if status:
        print_error(status)
    return False

def send_telegram_file(token, chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    
    if not os.path.exists(file_path):
        return False, "File not found"

    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except Exception as e:
        return False, f"Read error: {e}"

    file_name = os.path.basename(file_path)
    parts = []
    
    parts.append(f"--{boundary}".encode('utf-8'))
    parts.append(f'Content-Disposition: form-data; name="chat_id"'.encode('utf-8'))
    parts.append(b'')
    parts.append(str(chat_id).encode('utf-8'))
    
    if caption:
        parts.append(f"--{boundary}".encode('utf-8'))
        parts.append(f'Content-Disposition: form-data; name="caption"'.encode('utf-8'))
        parts.append(b'')
        parts.append(caption.encode('utf-8'))
        
    parts.append(f"--{boundary}".encode('utf-8'))
    parts.append(f'Content-Disposition: form-data; name="document"; filename="{file_name}"'.encode('utf-8'))
    parts.append(b'Content-Type: application/zip')
    parts.append(b'')
    parts.append(file_content)
    
    parts.append(f"--{boundary}--".encode('utf-8'))
    parts.append(b'')
    
    body = b'\r\n'.join(parts)
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('Content-Length', str(len(body)))
    
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            res_body = response.read().decode('utf-8')
            return True, res_body
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        return False, f"HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return False, f"Connection error: {str(e).replace(token, '***')}"

def _file_not_empty(path):
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False

def detect_db_type_local():
    """Detect the database used by the local Pasarguard installation
    by reading the services defined in /opt/pasarguard/docker-compose.yml."""
    compose_file = os.path.join(PASARGUARD_DIR, "docker-compose.yml")
    if not os.path.isfile(compose_file):
        print_error(f"Cannot find {compose_file}. Is Pasarguard installed on this server?")
        return None

    ok, out, err = local_shell("docker compose config --services", cwd=PASARGUARD_DIR)
    if not ok:
        print_error("Could not read the docker compose services.")
        if err:
            print_error(f"Details: {err}")
        return None

    services = [line.strip() for line in out.splitlines() if line.strip()]

    if "timescaledb" in services:
        print_success("Detected database: TimescaleDB (PostgreSQL)")
        return "timescaledb"
    if "mysql" in services:
        print_success("Detected database: MySQL")
        return "mysql"

    db_url = _read_env_var(os.path.join(PASARGUARD_DIR, ".env"), "SQLALCHEMY_DATABASE_URL") or ""
    scheme = db_url.split("://", 1)[0] if "://" in db_url else "unknown"
    print_error("Unsupported or undetected database.")
    print_error(f"Compose services: {', '.join(services) if services else 'none'} | DB driver in .env: {scheme}")
    print_error("This tool supports only TimescaleDB and MySQL (running as docker compose services).")
    return None

def detect_db_type_from_zip(zip_path):
    """Detect the database type from the content of a backup ZIP."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
    except Exception as e:
        print_error(f"Cannot read the ZIP file: {e}")
        return None

    if "pg_dump/db-001.sql" in names:
        print_success("Backup database type: TimescaleDB (PostgreSQL)")
        return "timescaledb"
    if "pg_dump/db_backup.sql" in names:
        print_success("Backup database type: MySQL")
        return "mysql"

    print_error("This ZIP does not look like a valid backup (no database dump found).")
    return None

def _create_backup_core(db_type="timescaledb", out_dir=None):
    print_info("Starting Backup Generation...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"backup_{timestamp}"

    current_dir = out_dir or os.getcwd()
    tmp_dir = os.path.join("/tmp", backup_name)
    final_zip_base = os.path.join(current_dir, backup_name)
    expected_zip_file = f"{final_zip_base}.zip"

    opt_dir = "/opt/pasarguard"
    data_dir = "/var/lib/pasarguard"

    pg_node_opt_dir_src = "/opt/pg-node"
    pg_node_data_dir_src = "/var/lib/pg-node"

    pg_dump_dir = os.path.join(tmp_dir, "pg_dump")
    pasarguard_data_dir = os.path.join(tmp_dir, "pasarguard_data")
    pg_node_opt_dir_dest = os.path.join(tmp_dir, "pg_node_opt")
    pg_node_data_dir_dest = os.path.join(tmp_dir, "pg_node_data")

    try:
        print_info("Creating temporary directories...")
        os.makedirs(pg_dump_dir, exist_ok=True)

        print_info("Copying Pasarguard configuration files...")
        if os.path.exists(os.path.join(opt_dir, "docker-compose.yml")):
            shutil.copy(os.path.join(opt_dir, "docker-compose.yml"), tmp_dir)
        if os.path.exists(os.path.join(opt_dir, ".env")):
            shutil.copy(os.path.join(opt_dir, ".env"), tmp_dir)

        if db_type == "timescaledb":
            print_info("Exporting PostgreSQL globals... (This may take a moment)")
            cmd_globals = "docker compose exec -T timescaledb pg_dumpall -U pasarguard --globals-only"
            globals_path = os.path.join(pg_dump_dir, "globals.sql")
            if not run_command(cmd_globals, output_file=globals_path, cwd=opt_dir) or not _file_not_empty(globals_path):
                raise Exception("Database globals export failed (is the timescaledb container running?)")

            print_info("Exporting Pasarguard database... (Please wait, this might take a while for large databases)")
            cmd_db = "docker compose exec -T timescaledb pg_dump -U pasarguard -d pasarguard"
            dump_path = os.path.join(pg_dump_dir, "db-001.sql")
            if not run_command(cmd_db, output_file=dump_path, cwd=opt_dir) or not _file_not_empty(dump_path):
                raise Exception("Database export failed or produced an empty file. Backup aborted.")

            print_info("Creating manifest file...")
            with open(os.path.join(pg_dump_dir, "manifest.tsv"), "w") as f:
                f.write("pasarguard\tpasarguard\t1\tdb-001.sql\t2.28.1\n")
        else:
            print_info("Exporting MySQL database... (Please wait, this might take a while for large databases)")
            cmd_db = 'docker compose exec -T mysql sh -c \'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" pasarguard\''
            dump_path = os.path.join(pg_dump_dir, "db_backup.sql")
            if not run_command(cmd_db, output_file=dump_path, cwd=opt_dir) or not _file_not_empty(dump_path):
                raise Exception("Database export failed or produced an empty file. Backup aborted.")

        print_info("Copying Pasarguard data directory...")
        if os.path.exists(data_dir):
            shutil.copytree(data_dir, pasarguard_data_dir)
        else:
            print_warning(f"Data directory {data_dir} not found. Skipping...")

        print_info("Copying PG-Node configuration directory (/opt/pg-node)...")
        if os.path.exists(pg_node_opt_dir_src):
            shutil.copytree(pg_node_opt_dir_src, pg_node_opt_dir_dest)
        else:
            print_warning(f"Directory {pg_node_opt_dir_src} not found. Skipping...")

        print_info("Copying PG-Node data directory (/var/lib/pg-node)...")
        if os.path.exists(pg_node_data_dir_src):
            shutil.copytree(pg_node_data_dir_src, pg_node_data_dir_dest)
        else:
            print_warning(f"Directory {pg_node_data_dir_src} not found. Skipping...")

        print_info("Compressing all files into a ZIP archive... (Please wait)")
        shutil.make_archive(final_zip_base, 'zip', tmp_dir)

        print_info("Cleaning up temporary files...")
        shutil.rmtree(tmp_dir)

        print_success(f"Backup created successfully: {expected_zip_file}")
        return expected_zip_file

    except Exception as e:
        print_error(f"Unexpected error during backup: {e}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

def freeze_services_local(db_type):
    """Stop PG-Node and the Pasarguard app containers, but keep the database
    container running so that the dump can still be taken (consistent data)."""
    db_service = "timescaledb" if db_type == "timescaledb" else "mysql"
    ok = True

    if os.path.isfile(os.path.join(PG_NODE_DIR, "docker-compose.yml")):
        print_info("Stopping PG-Node containers...")
        if not run_command(f"docker compose stop -t {COMPOSE_DOWN_TIMEOUT}", cwd=PG_NODE_DIR):
            ok = False
    else:
        print_warning("PG-Node compose project not found. Skipping.")

    if os.path.isfile(os.path.join(PASARGUARD_DIR, "docker-compose.yml")):
        success, out, _ = local_shell("docker compose config --services", cwd=PASARGUARD_DIR)
        services = [s.strip() for s in out.splitlines() if s.strip() and s.strip() != db_service] if success else []
        if services:
            print_info(f"Stopping Pasarguard app containers ({', '.join(services)}); database stays up...")
            if not run_command(f"docker compose stop -t {COMPOSE_DOWN_TIMEOUT} {' '.join(services)}", cwd=PASARGUARD_DIR):
                ok = False
        # make sure the database container is up for the dump
        if not run_command(f"docker compose up -d {db_service}", cwd=PASARGUARD_DIR):
            ok = False
        else:
            if db_type == "timescaledb":
                ok = wait_for_postgres_ready_local() and ok
            else:
                ok = wait_for_mysql_ready_local() and ok
    else:
        print_warning("Pasarguard compose project not found. Skipping.")

    return ok

def resume_services_local():
    """Start everything again after a backup."""
    ok = True
    if os.path.isfile(os.path.join(PASARGUARD_DIR, "docker-compose.yml")):
        if not start_compose_stack_local(PASARGUARD_DIR, "Pasarguard"):
            ok = False
    if os.path.isfile(os.path.join(PG_NODE_DIR, "docker-compose.yml")):
        if not start_compose_stack_local(PG_NODE_DIR, "PG-Node"):
            ok = False
    return ok

def ask_yes_no(prompt, default=None):
    while True:
        ans = input(f"{Colors.CYAN}{prompt}{Colors.RESET}").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans == "" and default is not None:
            return default
        print_warning("Please answer with y or n.")

def create_backup(db_type="timescaledb", ask_freeze=False):
    """Create a backup. When ask_freeze=True the user is asked whether the
    services should be stopped during the backup (final migration) or left
    running (test run)."""
    freeze = False
    keep_stopped = False

    if ask_freeze:
        print("")
        print(f"{Colors.BOLD}--- Backup Mode ---{Colors.RESET}")
        print_info("TEST run  : services keep running (no downtime, data may change during backup).")
        print_info("FINAL run : app + node are stopped so NO data changes during backup (downtime).")
        freeze = ask_yes_no("🛑 Stop Pasarguard & PG-Node during backup? (y = final / n = test): ")
        if freeze:
            keep_stopped = ask_yes_no(
                "⏸️  Keep them STOPPED after backup finishes? (y = keep stopped for migration / n = start again) [n]: ",
                default=False,
            )
            print_warning("Pasarguard and PG-Node will be stopped now. Users will be disconnected!")
            if not ask_yes_no("Continue? (y/n): "):
                print_warning("Backup aborted by user.")
                return None

    if freeze:
        if not freeze_services_local(db_type):
            print_error("Could not prepare services for a clean backup. Restarting services and aborting...")
            resume_services_local()
            return None

    zip_path = None
    try:
        zip_path = _create_backup_core(db_type)
    finally:
        if freeze:
            if zip_path and keep_stopped:
                print_warning("Pasarguard & PG-Node are still STOPPED on this server (as requested).")
                print_warning("To start them again later run:")
                print_warning("  cd /opt/pasarguard && docker compose up -d && cd /opt/pg-node && docker compose up -d")
            else:
                if not zip_path:
                    print_warning("Backup failed. Starting services again for safety...")
                else:
                    print_info("Starting services again...")
                resume_services_local()

    return zip_path

def execute_ssh_command(ssh, command, description, required=True):
    print(f"{Colors.CYAN}🌐 [SSH]{Colors.RESET} {description}...")
    exit_status, out, err = ssh_shell(ssh, command)

    if exit_status == 0:
        print_success("Done.")
    else:
        print_error("Command failed!")
        if err:
            print_error(f"Details: {err}")
        elif out:
            print_error(f"Details: {out}")
    return exit_status == 0 if required else True

def workflow_auto_backup_restore(db_type="timescaledb"):
    print_header("Auto Backup & Transfer to New Server")
    
    zip_file_path = create_backup(db_type, ask_freeze=True)
    if not zip_file_path or not os.path.exists(zip_file_path):
        print_error("Aborting process due to backup failure.")
        return

    print("")
    send_to_tg = input(f"{Colors.CYAN}🤖 Do you want to send this backup to a Telegram Bot first? (y/n): {Colors.RESET}").strip().lower()
    if send_to_tg == 'y':
        bot_token = input(f"{Colors.CYAN}🔑 Enter Telegram Bot Token: {Colors.RESET}").strip()
        admin_id = input(f"{Colors.CYAN}👤 Enter Admin Numeric Chat ID: {Colors.RESET}").strip()
        
        print_info("Uploading backup to Telegram (Please wait)...")
        caption = f"📦 Pasarguard & PG-Node Manual Transfer Backup\nDate: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        success, details = send_telegram_file(bot_token, admin_id, zip_file_path, caption=caption)
        if success:
            print_success("Backup sent to Telegram successfully!")
        else:
            print_error(f"Telegram upload failed: {details}")

    print(f"\n{Colors.BOLD}--- New Server Information ---{Colors.RESET}")
    new_server_ip = input(f"{Colors.CYAN}🖥️  Enter New Server IP: {Colors.RESET}").strip()
    ssh_port_input = input(f"{Colors.CYAN}🔌 Enter SSH Port (Default 22): {Colors.RESET}").strip()
    ssh_port = int(ssh_port_input) if ssh_port_input.isdigit() else 22
    
    is_root = input(f"{Colors.CYAN}⚠️  User MUST be root. Do you confirm? (y/n): {Colors.RESET}").strip().lower()
    if is_root != 'y':
        print_error("Root access is required. Aborting...")
        return
        
    new_server_pass = input(f"{Colors.CYAN}🔑 Enter Root Password: {Colors.RESET}").strip()

    print_info(f"Connecting to {new_server_ip}:{ssh_port}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(hostname=new_server_ip, port=ssh_port, username='root', password=new_server_pass, timeout=30)
        print_success("Connected to the new server!")
        print("")
        
        execute_ssh_command(ssh, "apt-get update >/dev/null 2>&1 && apt-get install -y unzip >/dev/null 2>&1", "Installing 'unzip' package silently")

        pre_restore_mysql_password = None
        if db_type == "mysql":
            pre_restore_mysql_password = capture_current_mysql_password_ssh(ssh, PASARGUARD_DIR)

        if not stop_compose_stack_ssh(ssh, PG_NODE_DIR, "PG-Node"):
            print_error("Aborting: PG-Node containers could not be stopped cleanly.")
            return
        if not stop_compose_stack_ssh(ssh, PASARGUARD_DIR, "Pasarguard"):
            print_error("Aborting: Pasarguard containers could not be stopped cleanly.")
            return

        if not clean_restore_directories_ssh(ssh):
            print_error("Aborting: directory cleanup failed.")
            return

        print(f"{Colors.CYAN}🌐 [SSH]{Colors.RESET} Uploading backup file (This depends on your internet speed)...")
        sftp = ssh.open_sftp()
        zip_filename = os.path.basename(zip_file_path)
        remote_zip_path = f"/opt/pasarguard/{zip_filename}"
        sftp.put(zip_file_path, remote_zip_path)
        sftp.close()
        print_success("Upload completed.")

        execute_ssh_command(ssh, f"cd /opt/pasarguard && unzip -q -o {zip_filename}", "Extracting files (This may take a moment)")
        
        if not execute_ssh_command(ssh, "cp -a /opt/pasarguard/pasarguard_data/. /var/lib/pasarguard/ 2>/dev/null || true && rm -rf /opt/pasarguard/pasarguard_data", "Restoring Pasarguard data"):
            print_error("Aborting: failed to restore Pasarguard data.")
            return
        if not execute_ssh_command(ssh, "cp -a /opt/pasarguard/pg_node_opt/. /opt/pg-node/ 2>/dev/null || true && rm -rf /opt/pasarguard/pg_node_opt", "Restoring PG-Node configuration"):
            print_error("Aborting: failed to restore PG-Node configuration.")
            return
        if not execute_ssh_command(ssh, "cp -a /opt/pasarguard/pg_node_data/. /var/lib/pg-node/ 2>/dev/null || true && rm -rf /opt/pasarguard/pg_node_data", "Restoring PG-Node data"):
            print_error("Aborting: failed to restore PG-Node data.")
            return

        if db_type == "timescaledb":
            if not start_compose_stack_ssh(ssh, PASARGUARD_DIR, "Pasarguard DB", services=["timescaledb"], wait_postgres=True):
                print_error("Aborting: timescaledb did not start correctly.")
                return

            if not execute_ssh_command(ssh, 'cd /opt/pasarguard && docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "DROP DATABASE IF EXISTS pasarguard WITH (FORCE);"', "Dropping old database to prevent conflicts"):
                print_error("Aborting: failed to drop old database.")
                return
            if not execute_ssh_command(ssh, 'cd /opt/pasarguard && docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "CREATE DATABASE pasarguard;"', "Creating a fresh, clean database"):
                print_error("Aborting: failed to create database.")
                return

            if not execute_ssh_command(ssh, "cd /opt/pasarguard && cat pg_dump/globals.sql | docker compose exec -T timescaledb psql -U pasarguard", "Restoring globals.sql"):
                print_error("Aborting: failed to restore globals.sql.")
                return
            if not execute_ssh_command(ssh, "cd /opt/pasarguard && cat pg_dump/db-001.sql | docker compose exec -T timescaledb psql -U pasarguard -d pasarguard", "Restoring db-001.sql (Please wait, this might take a while for large databases)"):
                print_error("Aborting: failed to restore db-001.sql.")
                return
        else:
            if not start_compose_stack_ssh(ssh, PASARGUARD_DIR, "Pasarguard DB", services=["mysql"], wait_mysql=True):
                print_error("Aborting: mysql did not start correctly.")
                return

            mysql_pw = resolve_mysql_root_password_ssh(
                ssh, PASARGUARD_DIR, extra_candidates=[pre_restore_mysql_password]
            )
            if not mysql_pw:
                print_error("Aborting: could not authenticate to MySQL with any provided password.")
                return

            drop_create_cmd = "cd /opt/pasarguard && docker compose exec -T mysql sh -c " + shlex.quote(
                f'mysql -uroot -p{mysql_pw} -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
            )
            if not execute_ssh_command(ssh, drop_create_cmd, "Dropping old database and creating a fresh one"):
                print_error("Aborting: failed to drop/create mysql database.")
                return
            restore_cmd = "cd /opt/pasarguard && cat pg_dump/db_backup.sql | docker compose exec -T mysql sh -c " + shlex.quote(
                f'mysql -uroot -p{mysql_pw} pasarguard'
            )
            if not execute_ssh_command(ssh, restore_cmd, "Restoring db_backup.sql (Please wait)"):
                print_error("Aborting: failed to restore db_backup.sql.")
                return

            if not sync_app_db_credentials_ssh(ssh, PASARGUARD_DIR, mysql_pw):
                print_error("Aborting: failed to sync application DB user credentials with .env.")
                return

        if not start_compose_stack_ssh(ssh, PASARGUARD_DIR, "Pasarguard"):
            print_error("Aborting: Pasarguard containers did not start correctly.")
            return
        if not start_compose_stack_ssh(ssh, PG_NODE_DIR, "PG-Node"):
            print_error("Aborting: PG-Node containers did not start correctly.")
            return

        print_header("Transfer & Restore Completed Successfully! 🎉")
        print_success("Verified: Pasarguard and PG-Node Docker stacks are running on the new server.")

    except paramiko.AuthenticationException:
        print_error("Incorrect server password!")
    except Exception as e:
        print_error(f"Server connection error: {e}")
    finally:
        ssh.close()
        try:
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)
        except:
            pass

def workflow_backup_bot(db_type="timescaledb"):
    print_header("Auto Backup to Telegram Bot (Scheduled)")
    
    bot_token = input(f"{Colors.CYAN}🔑 Enter Telegram Bot Token: {Colors.RESET}").strip()
    while not bot_token:
        bot_token = input(f"{Colors.RED}Token cannot be empty!{Colors.RESET} {Colors.CYAN}Enter Bot Token:{Colors.RESET} ").strip()

    admin_id = input(f"{Colors.CYAN}👤 Enter Admin Numeric Chat ID: {Colors.RESET}").strip()
    while not admin_id or not admin_id.lstrip('-').isdigit():
        admin_id = input(f"{Colors.RED}Invalid ID!{Colors.RESET} {Colors.CYAN}Enter Admin Numeric Chat ID:{Colors.RESET} ").strip()

    try:
        interval_input = input(f"{Colors.CYAN}⏱️  Enter interval in hours (e.g., 0.5 for 30 mins, 1 for 1 hour): {Colors.RESET}").strip()
        interval_hours = float(interval_input)
    except ValueError:
        print_warning("Invalid number. Defaulting to 1.0 hour.")
        interval_hours = 1.0

    interval_seconds = int(interval_hours * 3600)
    print_info(f"Scheduler started! Backups will run every {interval_hours} hours.")
    print_warning("Press Ctrl+C at any time to stop this utility.")
    print("-" * 50)

    try:
        while True:
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n{Colors.BOLD}⏳ Starting scheduled task at {current_time_str}...{Colors.RESET}")
            
            zip_file_path = create_backup(db_type)
            
            if zip_file_path and os.path.exists(zip_file_path):
                print_info("Uploading to Telegram...")
                caption = f"🤖 Pasarguard & PG-Node Auto Backup\nDate: {current_time_str}\nInterval: {interval_hours} hrs"
                success, details = send_telegram_file(bot_token, admin_id, zip_file_path, caption=caption)
                
                if success:
                    print_success("Backup sent to Telegram!")
                else:
                    print_error(f"Failed to send to Telegram: {details}")
                
                try:
                    os.remove(zip_file_path)
                    print_info("Local ZIP file removed to save disk space.")
                except Exception:
                    pass
            else:
                print_error("Backup failed. Skipping Telegram upload.")

            print_info(f"Sleeping for {interval_hours} hours... (Zzz)")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🚪 Backup scheduler stopped by user.{Colors.RESET}")

def workflow_manual_backup(db_type="timescaledb"):
    print_header("Manual Backup (Local)")
    print_info("This will create a backup and save it in the current directory.")
    
    zip_file_path = create_backup(db_type, ask_freeze=True)
    
    if zip_file_path and os.path.exists(zip_file_path):
        print_success(f"Manual backup completed! Your file is safe at: {zip_file_path}")
    else:
        print_error("Manual backup failed!")

def workflow_manual_restore():
    print_header("Manual Restore (Local)")
    print_info("This process will wipe the current Pasarguard & PG-Node setup and restore from a ZIP file.")
    
    zip_name = input(f"{Colors.CYAN}📦 Enter the exact Backup ZIP file name (e.g. backup_2026.zip): {Colors.RESET}").strip()
    
    if not os.path.exists(zip_name):
        print_error(f"Cannot find the file '{zip_name}' in the current directory!")
        return

    db_type = detect_db_type_from_zip(zip_name)
    if not db_type:
        return

    confirm = input(f"{Colors.RED}⚠️  WARNING: This will overwrite your current configuration and database. Continue? (y/n): {Colors.RESET}").strip().lower()
    if confirm != 'y':
        print_warning("Restore process aborted by user.")
        return

    pre_restore_mysql_password = None
    if db_type == "mysql":
        pre_restore_mysql_password = capture_current_mysql_password_local(PASARGUARD_DIR)

    try:
        if not stop_compose_stack_local(PG_NODE_DIR, "PG-Node"):
            print_error("Aborting: PG-Node containers could not be stopped cleanly.")
            return
        if not stop_compose_stack_local(PASARGUARD_DIR, "Pasarguard"):
            print_error("Aborting: Pasarguard containers could not be stopped cleanly.")
            return

        if not clean_restore_directories_local():
            print_error("Aborting: directory cleanup failed.")
            return
        
        print_info("Extracting backup files (This may take a moment)...")
        if not run_command(f"unzip -q -o {zip_name} -d /opt/pasarguard"):
            print_error("Failed to extract backup archive.")
            return
        
        print_info("Restoring PG-Node and Pasarguard files...")
        run_command("cp -a /opt/pasarguard/pasarguard_data/. /var/lib/pasarguard/ 2>/dev/null || true")
        run_command("cp -a /opt/pasarguard/pg_node_opt/. /opt/pg-node/ 2>/dev/null || true")
        run_command("cp -a /opt/pasarguard/pg_node_data/. /var/lib/pg-node/ 2>/dev/null || true")
        run_command("rm -rf /opt/pasarguard/pg_node_opt /opt/pasarguard/pg_node_data /opt/pasarguard/pasarguard_data")
        
        if db_type == "timescaledb":
            if not start_compose_stack_local(PASARGUARD_DIR, "Pasarguard DB", services=["timescaledb"], wait_postgres=True):
                raise Exception("timescaledb did not start correctly")
            
            print_info("Dropping old database to prevent conflicts...")
            if not run_command('cd /opt/pasarguard && docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "DROP DATABASE IF EXISTS pasarguard WITH (FORCE);"'):
                raise Exception("Failed to drop old database")
            
            print_info("Creating a fresh, clean database...")
            if not run_command('cd /opt/pasarguard && docker compose exec -T timescaledb psql -U pasarguard -d postgres -c "CREATE DATABASE pasarguard;"'):
                raise Exception("Failed to create database")

            print_info("Restoring PostgreSQL globals...")
            if not run_command("cd /opt/pasarguard && cat pg_dump/globals.sql | docker compose exec -T timescaledb psql -U pasarguard"):
                raise Exception("Failed to restore globals.sql")
                
            print_info("Restoring Pasarguard database... (Please wait, this might take a while for large databases)")
            if not run_command("cd /opt/pasarguard && cat pg_dump/db-001.sql | docker compose exec -T timescaledb psql -U pasarguard -d pasarguard"):
                raise Exception("Failed to restore db-001.sql")
        else:
            if not start_compose_stack_local(PASARGUARD_DIR, "Pasarguard DB", services=["mysql"], wait_mysql=True):
                raise Exception("mysql did not start correctly")

            mysql_pw = resolve_mysql_root_password_local(
                PASARGUARD_DIR, extra_candidates=[pre_restore_mysql_password]
            )
            if not mysql_pw:
                raise Exception("Could not authenticate to MySQL with any provided password")

            print_info("Dropping old database and creating a fresh one...")
            drop_create_cmd = "cd /opt/pasarguard && docker compose exec -T mysql sh -c " + shlex.quote(
                f'mysql -uroot -p{mysql_pw} -e "DROP DATABASE IF EXISTS pasarguard; CREATE DATABASE pasarguard;"'
            )
            if not run_command(drop_create_cmd):
                raise Exception("Failed to drop/create mysql database")

            print_info("Restoring MySQL database... (Please wait)")
            restore_cmd = "cd /opt/pasarguard && cat pg_dump/db_backup.sql | docker compose exec -T mysql sh -c " + shlex.quote(
                f'mysql -uroot -p{mysql_pw} pasarguard'
            )
            if not run_command(restore_cmd):
                raise Exception("Failed to restore db_backup.sql")

            if not sync_app_db_credentials_local(PASARGUARD_DIR, mysql_pw):
                raise Exception("Failed to sync application DB user credentials with .env")
            
        if not start_compose_stack_local(PASARGUARD_DIR, "Pasarguard"):
            raise Exception("Pasarguard containers did not start correctly")
        if not start_compose_stack_local(PG_NODE_DIR, "PG-Node"):
            raise Exception("PG-Node containers did not start correctly")
        
        print_header("Local Restore Completed Successfully! 🎉")
        print_success("Verified: Pasarguard and PG-Node Docker stacks are running.")

    except Exception as e:
        print_error(f"An error occurred during restoration: {e}")
        print_warning("Your system might be in a partially restored state.")

# ============================================================================
#  Telegram Bot + Daily Cron Scheduler
# ============================================================================
CONFIG_DIR = "/opt/teperbk"
INSTALL_PATH = os.path.join(CONFIG_DIR, "teperbk.py")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
LOCK_FILE = os.path.join(CONFIG_DIR, "backup.lock")
CRON_FILE = "/etc/cron.d/teperbk"
SERVICE_NAME = "teperbk-bot"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}.service"
LOGROTATE_FILE = "/etc/logrotate.d/teperbk"
LOG_FILE = "/var/log/teperbk.log"

TG_MAX_BYTES = 49 * 1024 * 1024    # Bot API upload limit is 50 MB
TG_PART_BYTES = 45 * 1024 * 1024   # size of each part when a backup is bigger

SCHEDULE_PRESETS = {
    "1": ["03:00"],
    "2": ["03:00", "15:00"],
    "3": ["02:00", "10:00", "18:00"],
    "4": ["00:00", "06:00", "12:00", "18:00"],
}

DEFAULT_CONFIG = {
    "bot_token": "",
    "admin_chat_id": "",
    "times": ["03:00"],
    "lang": "fa",
    "last_backup": None,
}

BOT_AWAITING = {}   # chat_id -> "times" while the bot waits for custom times

BOT_STR = {
    "en": {
        "menu": "🤖 teperbk - PasarGuard backup\nChoose an option:",
        "b_backup": "📦 Backup now",
        "b_status": "📊 Status",
        "b_sched": "⏰ Schedule",
        "b_lang": "🌐 Language / زبان",
        "b_custom": "✏️ Custom times",
        "b_back": "⬅️ Back",
        "sched_title": "⏰ How many backups per day?\nPick a preset or send your own times.",
        "ask_times": "Send the daily backup times in 24h format, separated by comma or space.\nExample: 03:00, 15:30\nOne time = once a day, three times = three backups a day.\nSend /cancel to cancel.",
        "times_ok": "✅ Schedule saved.\n⏰ Times: {times}\n🕒 Server time zone: {tz}\nThe cron job on the server was updated automatically.",
        "times_bad": "❌ Invalid input: {err}\nExample: 03:00, 15:30",
        "cron_fail": "⚠️ Schedule saved but the cron job could not be written: {err}",
        "backup_start": "⏳ Backup started... this can take a few minutes.",
        "backup_busy": "⏳ Another backup is already running. Try again later.",
        "backup_fail": "❌ Backup failed. Check the server log: {log}",
        "detect_fail": "❌ Could not detect the panel database (only TimescaleDB and MySQL are supported). Log: {log}",
        "upload_fail": "⚠️ The backup was created on the server but sending it to Telegram failed:\n{err}",
        "caption": "📦 PasarGuard backup\n🖥 Server: {host}\n🗄 Database: {db}\n📏 Size: {size}\n🕒 Time: {time}",
        "part_note": "🧩 Part {i} of {n}\nJoin on the server: cat {name}.part* > {name}",
        "status": "📊 Status\n🖥 Server: {host}\n⏰ Daily times: {times}\n🕒 Time zone: {tz}\n🗂 Last backup: {last}\n💾 Kept on server: {file}\n🔁 Cron job: {cron}",
        "last_none": "no backup yet",
        "file_none": "none",
        "on": "active ✅",
        "off": "missing ❌",
        "cancelled": "Cancelled.",
        "lang_set": "✅ Language set to English.",
    },
    "fa": {
        "menu": "🤖 teperbk - بکاپ پاسارگاد\nیکی از گزینه‌ها را انتخاب کن:",
        "b_backup": "📦 بکاپ همین الان",
        "b_status": "📊 وضعیت",
        "b_sched": "⏰ زمان‌بندی",
        "b_lang": "🌐 Language / زبان",
        "b_custom": "✏️ زمان دلخواه",
        "b_back": "⬅️ بازگشت",
        "sched_title": "⏰ روزی چند بار بکاپ بفرستم؟\nیکی از گزینه‌ها را بزن یا ساعت‌های دلخواهت را بفرست.",
        "ask_times": "ساعت‌های بکاپ روزانه را با فرمت ۲۴ ساعته بفرست (با کاما یا فاصله جدا کن).\nمثال: 03:00, 15:30\nیک ساعت = روزی یک بار، سه ساعت = روزی سه بار.\nبرای لغو: /cancel",
        "times_ok": "✅ زمان‌بندی ذخیره شد.\n⏰ ساعت‌ها: {times}\n🕒 منطقه زمانی سرور: {tz}\nکرون‌جاب روی سرور خودکار به‌روز شد.",
        "times_bad": "❌ ورودی نامعتبر: {err}\nمثال: 03:00, 15:30",
        "cron_fail": "⚠️ زمان‌بندی ذخیره شد ولی کرون‌جاب ساخته نشد: {err}",
        "backup_start": "⏳ بکاپ شروع شد... چند دقیقه طول می‌کشد.",
        "backup_busy": "⏳ یک بکاپ دیگر در حال انجام است. بعداً دوباره امتحان کن.",
        "backup_fail": "❌ بکاپ ناموفق بود. لاگ سرور را چک کن: {log}",
        "detect_fail": "❌ دیتابیس پنل تشخیص داده نشد (فقط TimescaleDB و MySQL پشتیبانی می‌شود). لاگ: {log}",
        "upload_fail": "⚠️ بکاپ روی سرور ساخته شد ولی ارسال به تلگرام ناموفق بود:\n{err}",
        "caption": "📦 بکاپ پاسارگاد\n🖥 سرور: {host}\n🗄 دیتابیس: {db}\n📏 حجم: {size}\n🕒 زمان: {time}",
        "part_note": "🧩 بخش {i} از {n}\nبرای ادغام روی سرور: cat {name}.part* > {name}",
        "status": "📊 وضعیت\n🖥 سرور: {host}\n⏰ ساعت‌های بکاپ: {times}\n🕒 منطقه زمانی: {tz}\n🗂 آخرین بکاپ: {last}\n💾 فایل روی سرور: {file}\n🔁 کرون‌جاب: {cron}",
        "last_none": "هنوز بکاپی گرفته نشده",
        "file_none": "ندارد",
        "on": "فعال ✅",
        "off": "وجود ندارد ❌",
        "cancelled": "لغو شد.",
        "lang_set": "✅ زبان روی فارسی تنظیم شد.",
    },
}

def bot_t(lang, key, **kw):
    table = BOT_STR.get(lang) or BOT_STR["en"]
    text = table.get(key) or BOT_STR["en"][key]
    return text.format(**kw) if kw else text

# ---------------------------------------------------------------- config ----
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg

def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)

def is_configured(cfg):
    return bool(cfg.get("bot_token") and str(cfg.get("admin_chat_id")).strip())

def human_size(num):
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0

def server_timezone():
    return datetime.datetime.now().astimezone().strftime("%Z (UTC%z)")

# ------------------------------------------------------------- telegram ----
def tg_api(token, method, params=None, timeout=30):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "description": str(e).replace(token, "***")}

def tg_send(cfg, text, keyboard=None):
    params = {"chat_id": cfg["admin_chat_id"], "text": text}
    if keyboard:
        params["reply_markup"] = {"inline_keyboard": keyboard}
    return tg_api(cfg["bot_token"], "sendMessage", params)

# ----------------------------------------------------- times & cron job ----
def parse_times(text):
    """'03:00, 15:30' -> (['03:00','15:30'], None). Returns (None, bad_token) on error."""
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    text = (text or "").translate(trans).replace("،", ",").replace("؛", ",")
    tokens = [t for t in re.split(r"[,\s;]+", text.strip()) if t]
    if not tokens:
        return None, "empty"
    found = set()
    for tok in tokens:
        m = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?", tok)
        if not m:
            return None, tok
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if hour > 23 or minute > 59:
            return None, tok
        found.add(f"{hour:02d}:{minute:02d}")
    if len(found) > 24:
        return None, "max 24 times"
    return sorted(found), None

def build_cron_text(times):
    py = shutil.which("python3") or sys.executable
    lines = [
        "# Managed by teperbk. Change it from the teperbk menu or the Telegram bot.",
        "SHELL=/bin/bash",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    ]
    for t in times:
        hour, minute = t.split(":")
        lines.append(f"{int(minute)} {int(hour)} * * * root {shlex.quote(py)} {shlex.quote(INSTALL_PATH)} --cron-backup >> {LOG_FILE} 2>&1")
    return "\n".join(lines) + "\n"

def write_cron(times):
    try:
        if not times:
            if os.path.exists(CRON_FILE):
                os.remove(CRON_FILE)
            return True, None
        os.makedirs(os.path.dirname(CRON_FILE), exist_ok=True)
        with open(CRON_FILE, "w") as f:
            f.write(build_cron_text(times))
        os.chmod(CRON_FILE, 0o644)
        return True, None
    except OSError as e:
        return False, str(e)

def apply_schedule(times):
    """Save the times and rewrite the cron job. Returns (ok, error)."""
    cfg = load_config()
    cfg["times"] = times
    save_config(cfg)
    return write_cron(times)

def ensure_cron_installed():
    if shutil.which("cron") or shutil.which("crond"):
        return True
    print_info("Installing cron...")
    run_command("apt-get install -y cron")
    run_command("systemctl enable --now cron")
    return bool(shutil.which("cron") or shutil.which("crond"))

def ensure_installed_copy():
    """cron and the bot service need a stable script path."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    here = os.path.abspath(__file__)
    if os.path.abspath(INSTALL_PATH) != here:
        shutil.copy2(here, INSTALL_PATH)
    os.chmod(INSTALL_PATH, 0o755)
    return INSTALL_PATH

def install_logrotate():
    try:
        with open(LOGROTATE_FILE, "w") as f:
            f.write(f"{LOG_FILE} {{\n    weekly\n    rotate 4\n    compress\n    missingok\n    notifempty\n}}\n")
    except OSError:
        pass

def install_bot_service():
    if not shutil.which("systemctl"):
        print_warning("systemd not found. The cron job works, but the Telegram bot control service cannot run.")
        return False
    py = shutil.which("python3") or sys.executable
    unit = (
        "[Unit]\n"
        "Description=teperbk Telegram bot (PasarGuard backup)\n"
        "After=network-online.target docker.service\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "WorkingDirectory=/root\n"
        f"ExecStart={py} {INSTALL_PATH} --bot\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    with open(SERVICE_FILE, "w") as f:
        f.write(unit)
    ok = run_command("systemctl daemon-reload")
    ok = run_command(f"systemctl enable {SERVICE_NAME}") and ok
    ok = run_command(f"systemctl restart {SERVICE_NAME}") and ok
    return ok

def bot_service_state():
    if not shutil.which("systemctl"):
        return "unavailable"
    r = subprocess.run(["systemctl", "is-active", SERVICE_NAME], capture_output=True, text=True)
    return (r.stdout or "").strip() or "inactive"

def activate_schedule(cfg):
    """Copy script to a stable path, write the cron job, start the bot service."""
    ensure_installed_copy()
    ensure_cron_installed()
    save_config(cfg)
    ok_cron, err = write_cron(cfg["times"])
    install_logrotate()
    ok_service = install_bot_service()
    return ok_cron, err, ok_service

# --------------------------------------------------- backup for schedule ----
def acquire_backup_lock():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None

def backup_is_running():
    fh = acquire_backup_lock()
    if fh is None:
        return True
    fcntl.flock(fh, fcntl.LOCK_UN)
    fh.close()
    return False

def prune_old_backups(keep_path):
    """Keep only the newest backup ZIP in BACKUP_DIR."""
    removed = 0
    keep = os.path.abspath(keep_path)
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if (name.startswith("backup_") and name.endswith(".zip")
                and os.path.isfile(path) and os.path.abspath(path) != keep):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed

def split_file(path, part_bytes=None):
    part_bytes = part_bytes or TG_PART_BYTES
    parts_dir = tempfile.mkdtemp(prefix="teperbk_parts_")
    base = os.path.basename(path)
    parts = []
    with open(path, "rb") as src:
        index = 1
        while True:
            chunk = src.read(part_bytes)
            if not chunk:
                break
            part_path = os.path.join(parts_dir, f"{base}.part{index:03d}")
            with open(part_path, "wb") as out:
                out.write(chunk)
            parts.append(part_path)
            index += 1
    return parts_dir, parts

def _send_with_retry(token, chat_id, path, caption, attempts=3):
    details = ""
    for attempt in range(1, attempts + 1):
        ok, details = send_telegram_file(token, chat_id, path, caption=caption)
        if ok:
            return True, details
        print_warning(f"Telegram upload failed (attempt {attempt}/{attempts}): {details}")
        if attempt < attempts:
            time.sleep(15)
    return False, details

def send_backup_to_telegram(cfg, zip_path, db_type):
    token, chat_id, lang = cfg["bot_token"], cfg["admin_chat_id"], cfg.get("lang", "fa")
    size = os.path.getsize(zip_path)
    caption = bot_t(lang, "caption", host=socket.gethostname(), db=db_type, size=human_size(size),
                    time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if size <= TG_MAX_BYTES:
        return _send_with_retry(token, chat_id, zip_path, caption)

    print_info(f"Backup is {human_size(size)} (> Telegram 50 MB limit). Sending in parts...")
    parts_dir, parts = split_file(zip_path)
    try:
        name = os.path.basename(zip_path)
        for i, part in enumerate(parts, 1):
            cap = caption + "\n" + bot_t(lang, "part_note", i=i, n=len(parts), name=name)
            ok, details = _send_with_retry(token, chat_id, part, cap)
            if not ok:
                return False, details
        return True, "sent in parts"
    finally:
        shutil.rmtree(parts_dir, ignore_errors=True)

def record_last_backup(ok, zip_path=None):
    cfg = load_config()   # reload: the schedule may have changed while we were working
    cfg["last_backup"] = {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ok": bool(ok),
        "file": os.path.basename(zip_path) if zip_path else "",
        "size": os.path.getsize(zip_path) if zip_path and os.path.exists(zip_path) else 0,
    }
    save_config(cfg)

def run_scheduled_backup(trigger="cron"):
    """Backup (no downtime) -> keep only the newest ZIP on the server -> send to Telegram."""
    cfg = load_config()
    print(f"\n===== teperbk {trigger} backup @ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    if not is_configured(cfg):
        print_error("Telegram bot is not configured. Run 'teperbk' and use the Telegram menu first.")
        return False
    lang = cfg.get("lang", "fa")

    lock = acquire_backup_lock()
    if lock is None:
        print_warning("Another backup is already running. Skipping this run.")
        return False

    try:
        db_type = detect_db_type_local()
        if not db_type:
            tg_send(cfg, bot_t(lang, "detect_fail", log=LOG_FILE))
            return False

        os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
        zip_path = _create_backup_core(db_type, out_dir=BACKUP_DIR)
        if not zip_path or not os.path.exists(zip_path):
            record_last_backup(False)
            tg_send(cfg, bot_t(lang, "backup_fail", log=LOG_FILE))
            return False

        os.chmod(zip_path, 0o600)
        removed = prune_old_backups(zip_path)
        if removed:
            print_info(f"Removed {removed} old backup file(s). Only the latest is kept.")

        ok, details = send_backup_to_telegram(cfg, zip_path, db_type)
        record_last_backup(ok, zip_path)
        if ok:
            print_success("Backup sent to Telegram.")
        else:
            print_error(f"Sending to Telegram failed: {details}")
            tg_send(cfg, bot_t(lang, "upload_fail", err=str(details)[:500]))
        return ok
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()

# ------------------------------------------------------------ bot daemon ----
def bot_menu_keyboard(lang):
    return [
        [{"text": bot_t(lang, "b_backup"), "callback_data": "backup"}],
        [{"text": bot_t(lang, "b_status"), "callback_data": "status"},
         {"text": bot_t(lang, "b_sched"), "callback_data": "sched"}],
        [{"text": bot_t(lang, "b_lang"), "callback_data": "lang"}],
    ]

def bot_sched_keyboard(lang):
    rows = []
    for key, times in SCHEDULE_PRESETS.items():
        rows.append([{"text": f"🕒 {key}x/day  ({', '.join(times)})", "callback_data": f"preset:{key}"}])
    rows.append([{"text": bot_t(lang, "b_custom"), "callback_data": "custom"}])
    rows.append([{"text": bot_t(lang, "b_back"), "callback_data": "menu"}])
    return rows

def bot_status_text(cfg):
    lang = cfg.get("lang", "fa")
    last = cfg.get("last_backup")
    if last:
        mark = "✅" if last.get("ok") else "❌"
        last_txt = f"{last.get('time', '?')} {mark} ({human_size(last.get('size', 0))})"
    else:
        last_txt = bot_t(lang, "last_none")
    kept = bot_t(lang, "file_none")
    try:
        files = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".zip"))
        if files:
            kept = files[-1]
    except OSError:
        pass
    cron = bot_t(lang, "on") if os.path.exists(CRON_FILE) else bot_t(lang, "off")
    return bot_t(lang, "status", host=socket.gethostname(), times=", ".join(cfg.get("times") or []) or "-",
                 tz=server_timezone(), last=last_txt, file=kept, cron=cron)

def bot_set_times(cfg, times):
    lang = cfg.get("lang", "fa")
    ok, err = apply_schedule(times)
    if ok:
        tg_send(cfg, bot_t(lang, "times_ok", times=", ".join(times), tz=server_timezone()),
                [[{"text": bot_t(lang, "b_back"), "callback_data": "menu"}]])
    else:
        tg_send(cfg, bot_t(lang, "cron_fail", err=err))

def bot_run_backup_thread(cfg):
    lang = cfg.get("lang", "fa")
    if backup_is_running():
        tg_send(cfg, bot_t(lang, "backup_busy"))
        return
    tg_send(cfg, bot_t(lang, "backup_start"))
    threading.Thread(target=run_scheduled_backup, args=("telegram",), daemon=True).start()

def bot_action(cfg, action):
    lang = cfg.get("lang", "fa")
    if action == "backup":
        bot_run_backup_thread(cfg)
    elif action == "status":
        tg_send(cfg, bot_status_text(cfg), bot_menu_keyboard(lang))
    elif action == "sched":
        tg_send(cfg, bot_t(lang, "sched_title") + f"\n🕒 {server_timezone()}", bot_sched_keyboard(lang))
    elif action.startswith("preset:"):
        times = SCHEDULE_PRESETS.get(action.split(":", 1)[1])
        if times:
            bot_set_times(cfg, times)
    elif action == "custom":
        BOT_AWAITING[str(cfg["admin_chat_id"])] = "times"
        tg_send(cfg, bot_t(lang, "ask_times"))
    elif action == "lang":
        new_lang = "en" if lang == "fa" else "fa"
        cfg["lang"] = new_lang
        save_config(cfg)
        tg_send(cfg, bot_t(new_lang, "lang_set"))
        tg_send(cfg, bot_t(new_lang, "menu"), bot_menu_keyboard(new_lang))
    else:   # "menu" and anything unknown
        tg_send(cfg, bot_t(lang, "menu"), bot_menu_keyboard(lang))

def bot_handle_update(upd):
    cfg = load_config()
    if not is_configured(cfg):
        return
    token, admin = cfg["bot_token"], str(cfg["admin_chat_id"])
    lang = cfg.get("lang", "fa")

    if "callback_query" in upd:
        cq = upd["callback_query"]
        tg_api(token, "answerCallbackQuery", {"callback_query_id": cq.get("id")})
        chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
        if chat_id == admin:
            BOT_AWAITING.pop(admin, None)
            bot_action(cfg, cq.get("data", "menu"))
        return

    msg = upd.get("message")
    if not msg or str(msg.get("chat", {}).get("id", "")) != admin:
        return   # only the admin can talk to this bot; everyone else is ignored

    text = (msg.get("text") or "").strip()
    if not text:
        return
    cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""

    if cmd == "/cancel":
        BOT_AWAITING.pop(admin, None)
        tg_send(cfg, bot_t(lang, "cancelled"), bot_menu_keyboard(lang))
    elif cmd in ("/start", "/help", "/menu"):
        BOT_AWAITING.pop(admin, None)
        bot_action(cfg, "menu")
    elif cmd == "/backup":
        bot_action(cfg, "backup")
    elif cmd == "/status":
        bot_action(cfg, "status")
    elif cmd in ("/schedule", "/times"):
        bot_action(cfg, "sched")
    elif cmd == "/settimes" and len(text.split(None, 1)) == 2:
        times, err = parse_times(text.split(None, 1)[1])
        if times:
            bot_set_times(cfg, times)
        else:
            tg_send(cfg, bot_t(lang, "times_bad", err=err))
    elif BOT_AWAITING.get(admin) == "times" and not cmd:
        times, err = parse_times(text)
        if times:
            BOT_AWAITING.pop(admin, None)
            bot_set_times(cfg, times)
        else:
            tg_send(cfg, bot_t(lang, "times_bad", err=err))
    else:
        bot_action(cfg, "menu")

def run_bot():
    cfg = load_config()
    if not is_configured(cfg):
        print_error("Telegram bot is not configured. Run 'teperbk' and use the Telegram menu first.")
        sys.exit(1)
    token = cfg["bot_token"]
    print_info("teperbk Telegram bot started.")
    sys.stdout.flush()
    tg_api(token, "deleteWebhook")
    tg_api(token, "setMyCommands", {"commands": [
        {"command": "start", "description": "Menu"},
        {"command": "backup", "description": "Backup now"},
        {"command": "status", "description": "Status"},
        {"command": "schedule", "description": "Backup schedule"},
    ]})

    offset = None
    while True:
        params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        token = load_config().get("bot_token", token)
        res = tg_api(token, "getUpdates", params, timeout=70)
        if not res.get("ok"):
            print_warning(f"getUpdates failed: {res.get('description')}")
            time.sleep(10)
            continue
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            try:
                bot_handle_update(upd)
            except Exception as e:
                print_error(f"Error while handling an update: {e}")
        sys.stdout.flush()

# ----------------------------------------------- terminal menu (option 5) ----
def _tgm_ask_token():
    while True:
        token = input(f"{Colors.CYAN}🔑 Enter Telegram Bot Token (from @BotFather): {Colors.RESET}").strip()
        if not token:
            continue
        res = tg_api(token, "getMe")
        if res.get("ok"):
            print_success(f"Bot found: @{res['result'].get('username', '?')}")
            return token
        print_error(f"Telegram rejected this token: {res.get('description')}")

def _tgm_ask_chat_id():
    while True:
        chat_id = input(f"{Colors.CYAN}👤 Enter Admin numeric Chat ID (your own account, not a group): {Colors.RESET}").strip()
        if chat_id.lstrip("-").isdigit():
            return chat_id
        print_error("Chat ID must be a number.")

def _tgm_ask_times(default):
    print_info(f"Server time zone: {server_timezone()}")
    print_info("Enter the daily backup times (24h), separated by comma or space. Example: 03:00, 15:30")
    print_info("One time = once a day, three times = three backups per day.")
    while True:
        raw = input(f"{Colors.CYAN}⏰ Times [{', '.join(default)}]: {Colors.RESET}").strip()
        if not raw:
            return list(default)
        times, err = parse_times(raw)
        if times:
            return times
        print_error(f"Invalid input: {err}")

def tgm_setup():
    print_header("Connect Telegram Bot")
    print_info("Create a bot with @BotFather, press START in your new bot, and get your numeric ID from @userinfobot.")
    cfg = load_config()
    cfg["bot_token"] = _tgm_ask_token()
    cfg["admin_chat_id"] = _tgm_ask_chat_id()

    lang_choice = input(f"{Colors.CYAN}🌐 Bot language (1 = فارسی, 2 = English) [1]: {Colors.RESET}").strip()
    cfg["lang"] = "en" if lang_choice == "2" else "fa"
    cfg["times"] = _tgm_ask_times(cfg.get("times") or ["03:00"])

    res = tg_send(cfg, bot_t(cfg["lang"], "menu"), bot_menu_keyboard(cfg["lang"]))
    if not res.get("ok"):
        print_error(f"Could not message the admin: {res.get('description')}")
        print_warning("Open your bot in Telegram and press START first, then try again.")
        if not ask_yes_no("Save the settings anyway? (y/n): ", default=False):
            return
    else:
        print_success("Test message sent to the admin.")

    print_info("Installing the cron job and the bot service...")
    ok_cron, err, ok_service = activate_schedule(cfg)
    if ok_cron:
        print_success(f"Cron job created: {CRON_FILE}")
    else:
        print_error(f"Could not write the cron job: {err}")
    if ok_service:
        print_success(f"Bot service is running ({SERVICE_NAME}).")
    print_success(f"Daily backups at: {', '.join(cfg['times'])}  [{server_timezone()}]")
    print_info(f"Only the latest backup is kept in {BACKUP_DIR}. Logs: {LOG_FILE}")

def tgm_set_times():
    cfg = load_config()
    if not is_configured(cfg):
        print_warning("Connect the Telegram bot first.")
        return
    times = _tgm_ask_times(cfg.get("times") or ["03:00"])
    ensure_installed_copy()
    ok, err = apply_schedule(times)
    if ok:
        print_success(f"Schedule saved: {', '.join(times)}  [{server_timezone()}]")
        print_success("Cron job updated.")
    else:
        print_error(f"Could not write the cron job: {err}")

def tgm_status():
    cfg = load_config()
    token = cfg.get("bot_token", "")
    masked = (token[:6] + "..." + token[-4:]) if len(token) > 12 else ("(not set)" if not token else "***")
    print(f"  Bot token     : {masked}")
    print(f"  Admin chat ID : {cfg.get('admin_chat_id') or '(not set)'}")
    print(f"  Language      : {cfg.get('lang')}")
    print(f"  Daily times   : {', '.join(cfg.get('times') or []) or '-'}  [{server_timezone()}]")
    print(f"  Cron job      : {'present' if os.path.exists(CRON_FILE) else 'MISSING'}  ({CRON_FILE})")
    print(f"  Bot service   : {bot_service_state()}")
    last = cfg.get("last_backup")
    if last:
        print(f"  Last backup   : {last.get('time')}  {'OK' if last.get('ok') else 'FAILED'}  {human_size(last.get('size', 0))}")
    else:
        print("  Last backup   : none yet")
    try:
        files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".zip")]
        print(f"  Kept on server: {', '.join(sorted(files)) or 'none'}  ({BACKUP_DIR})")
    except OSError:
        print(f"  Kept on server: none  ({BACKUP_DIR})")

def tgm_disable():
    if not ask_yes_no("Remove the cron job and stop the Telegram bot service? (y/n): ", default=False):
        return
    write_cron([])
    if shutil.which("systemctl"):
        run_command(f"systemctl disable --now {SERVICE_NAME}")
    for path in (SERVICE_FILE, LOGROTATE_FILE):
        try:
            os.remove(path)
        except OSError:
            pass
    if shutil.which("systemctl"):
        run_command("systemctl daemon-reload")
    print_success("Cron job removed and bot service stopped.")
    if ask_yes_no("Also delete the saved bot token and settings? (y/n): ", default=False):
        try:
            os.remove(CONFIG_FILE)
            print_success("Settings deleted.")
        except OSError:
            pass

def workflow_telegram_manager():
    while True:
        print_header("Telegram Bot & Daily Backup Schedule")
        cfg = load_config()
        if is_configured(cfg):
            print_info(f"Daily times: {', '.join(cfg.get('times') or [])}  [{server_timezone()}]")
        else:
            print_warning("Not connected yet. Start with option 1.")
        print(f"\n{Colors.BLUE}1-{Colors.RESET} 🔗 Connect / change Telegram bot (+ auto create cron job)")
        print(f"{Colors.BLUE}2-{Colors.RESET} ⏰ Change daily backup times")
        print(f"{Colors.BLUE}3-{Colors.RESET} 📦 Run a backup now and send it to Telegram")
        print(f"{Colors.BLUE}4-{Colors.RESET} 📊 Show status")
        print(f"{Colors.BLUE}5-{Colors.RESET} 🗑️  Disable (remove cron job & stop bot)")
        print(f"{Colors.RED}6-{Colors.RESET} ⬅️  Back to main menu")
        choice = input(f"\n{Colors.CYAN}👉 Select an option (1-6): {Colors.RESET}").strip()

        if choice == "1":
            tgm_setup()
        elif choice == "2":
            tgm_set_times()
        elif choice == "3":
            if not is_configured(cfg):
                print_warning("Connect the Telegram bot first.")
            else:
                run_scheduled_backup("manual")
        elif choice == "4":
            tgm_status()
        elif choice == "5":
            tgm_disable()
        elif choice == "6":
            return
        else:
            print_error("Invalid option!")
        input(f"\n{Colors.YELLOW}Press [ENTER] to continue...{Colors.RESET}")


def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}=================================================={Colors.RESET}")
        print(f"{Colors.HEADER}{Colors.BOLD}          🛡️  PASARGUARD MANAGER UTILITY 🛡️           {Colors.RESET}")
        print(f"{Colors.HEADER}{Colors.BOLD}=================================================={Colors.RESET}")
        print(f"{Colors.CYAN}       Dev by: jyavaz{Colors.RESET}")
        print(f"{Colors.CYAN}       GitHub: https://github.com/jyavaz68/{Colors.RESET}")
        print(f"{Colors.HEADER}{Colors.BOLD}=================================================={Colors.RESET}\n")
        print(f"{Colors.BLUE}1-{Colors.RESET} 🚀 Auto Backup & Transfer to New Server")
        print(f"{Colors.BLUE}2-{Colors.RESET} 🤖 Auto Backup to Telegram Bot (Scheduled)")
        print(f"{Colors.BLUE}3-{Colors.RESET} 💾 Manual Backup (Save locally)")
        print(f"{Colors.BLUE}4-{Colors.RESET} 🔄 Manual Restore (From local zip)")
        print(f"{Colors.BLUE}5-{Colors.RESET} ⏰ Telegram Bot & Daily Schedule (cron job, recommended)")
        print(f"{Colors.RED}6-{Colors.RESET} 🚪 Exit")
        print(f"{Colors.HEADER}--------------------------------------------------{Colors.RESET}")
        
        choice = input(f"{Colors.CYAN}👉 Please select an option (1-6): {Colors.RESET}").strip()
        
        db_type = None
        if choice in ['1', '2', '3']:
            print("")
            db_type = detect_db_type_local()
            if not db_type:
                pause_and_return()
                continue

        if choice == '1':
            workflow_auto_backup_restore(db_type)
            pause_and_return()
        elif choice == '2':
            workflow_backup_bot(db_type)
            pause_and_return()
        elif choice == '3':
            workflow_manual_backup(db_type)
            pause_and_return()
        elif choice == '4':
            workflow_manual_restore()
            pause_and_return()
        elif choice == '5':
            workflow_telegram_manager()
        elif choice == '6':
            print(f"{Colors.YELLOW}🚪 Exiting... Have a great day!{Colors.RESET}")
            sys.exit(0)
        else:
            print_error("Invalid option! Please try again.")
            time.sleep(2)

if __name__ == "__main__":
    if "--cron-backup" in sys.argv:
        sys.exit(0 if run_scheduled_backup("cron") else 1)
    elif "--bot" in sys.argv:
        run_bot()
    else:
        main()
