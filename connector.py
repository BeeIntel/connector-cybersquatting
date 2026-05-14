import os
import re
import gzip
import shutil
import time
import tempfile
import schedule
from datetime import datetime

import requests
from pycti import OpenCTIApiClient

# --- Конфигурация из переменных окружения ---
OPENCTI_URL = os.getenv("OPENCTI_URL", "http://opencti:8080")
OPENCTI_TOKEN = os.getenv("OPENCTI_TOKEN")
TARGET_SUBSTRINGS = os.getenv("TARGET_SUBSTRINGS", "").split(",")
EXCLUDE_SUBSTRINGS = os.getenv("EXCLUDE_SUBSTRINGS", "").split(",")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "03:00")  # время суток
SCHEDULE_INTERVAL = os.getenv("SCHEDULE_INTERVAL")   # интервал в секундах (приоритетнее)

# Прокси
PROXIES = {}
if os.getenv("HTTP_PROXY"):
    PROXIES["http"] = os.getenv("HTTP_PROXY")
if os.getenv("HTTPS_PROXY"):
    PROXIES["https"] = os.getenv("HTTPS_PROXY")

# Список архивов для скачивания
URLS = [
    "https://partner.r01.ru/zones/ru_domains.gz",
    "https://partner.r01.ru/zones/su_domains.gz"
]

DOMAIN_REGEX = re.compile(
    r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b',
    re.IGNORECASE
)

# --- Класс для работы с OpenCTI API ---
class OpenCTIHandler:
    def __init__(self):
        self.client = OpenCTIApiClient(OPENCTI_URL, OPENCTI_TOKEN)

    def find_observable_by_value(self, domain):
        query = """
            query FindObservable($filters: FilterGroup) {
                stixCyberObservables(filters: $filters) {
                    edges {
                        node {
                            id
                            observable_value
                        }
                    }
                }
            }
        """
        variables = {
            "filters": {
                "mode": "and",
                "filters": [
                    {"key": "value", "values": [domain]},
                    {"key": "entity_type", "values": ["Domain-Name"]}
                ],
                "filterGroups": []
            }
        }
        try:
            result = self.client.query(query, variables)
            if result and 'data' in result:
                edges = result['data'].get('stixCyberObservables', {}).get('edges', [])
                if edges:
                    obs_id = edges[0]['node']['id']
                    print(f"[+] Observable already exists: {domain} (ID: {obs_id})")
                    return obs_id
        except Exception as e:
            print(f"[!] Error searching observable: {e}")
        return None

    def create_observable(self, domain):
        mutation = """
            mutation CreateObservable($type: String!, $value: String!) {
                stixCyberObservableAdd(
                    type: $type,
                    DomainName: { value: $value }
                ) {
                    id
                    entity_type
                    observable_value
                }
            }
        """
        variables = {
            "type": "Domain-Name",
            "value": domain
        }
        try:
            result = self.client.query(mutation, variables)
            if result and 'data' in result and 'stixCyberObservableAdd' in result['data']:
                obs_data = result['data']['stixCyberObservableAdd']
                obs_id = obs_data['id']
                print(f"[+] Observable created: {domain} (ID: {obs_id})")
                return obs_id
            else:
                print(f"[-] Failed to create observable for {domain}: {result}")
                return None
        except Exception as e:
            print(f"[!] Exception creating observable: {e}")
            return None

    def get_or_create_observable(self, domain):
        obs_id = self.find_observable_by_value(domain)
        if obs_id:
            return obs_id
        return self.create_observable(domain)

# --- Функция фильтрации доменов ---
def is_target_domain(domain):
    """
    Домен должен содержать хотя бы одну целевую подстроку
    и не содержать ни одной подстроки из исключений.
    """
    if not TARGET_SUBSTRINGS or not TARGET_SUBSTRINGS[0]:  # если список пуст
        return False

    domain_lower = domain.lower()

    # Исключения
    for excl in EXCLUDE_SUBSTRINGS:
        if excl and excl in domain_lower:
            return False

    # Целевые подстроки
    for target in TARGET_SUBSTRINGS:
        if target and target in domain_lower:
            return True

    return False

# --- Функции для скачивания и обработки ---
def download_file(url, dest_dir):
    local_filename = os.path.join(dest_dir, url.split('/')[-1])
    try:
        print(f"Downloading {url}")
        response = requests.get(
            url,
            stream=True,
            timeout=60,
            verify=False,
            proxies=PROXIES
        )
        response.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded {local_filename}")
        return local_filename
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

def extract_gz(gz_path, extract_dir):
    base_name = os.path.basename(gz_path).replace('.gz', '')
    extracted_path = os.path.join(extract_dir, base_name)
    try:
        print(f"Extracting {gz_path} -> {extracted_path}")
        with gzip.open(gz_path, 'rb') as f_in:
            with open(extracted_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"Extracted {extracted_path}")
        return extracted_path
    except Exception as e:
        print(f"Error extracting {gz_path}: {e}")
        return None

def process_file(file_path, ct_handler):
    print(f"Processing file {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        domains = DOMAIN_REGEX.findall(content)
        target_domains = set()
        for d in domains:
            if is_target_domain(d):
                target_domains.add(d.lower())

        if target_domains:
            for domain in target_domains:
                ct_handler.get_or_create_observable(domain)
        else:
            print(f"No target domains found in {file_path}")
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

def job():
    """Основная задача: скачивание, распаковка, обработка."""
    print(f"\n--- Job started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # Создаём временную директорию (автоматически удалится после завершения)
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Working directory: {tmpdir}")

        ct_handler = OpenCTIHandler()

        for url in URLS:
            gz_file = download_file(url, tmpdir)
            if gz_file:
                extracted = extract_gz(gz_file, tmpdir)
                if extracted:
                    process_file(extracted, ct_handler)
            else:
                print(f"Skipping extraction for {url}")

    print(f"--- Job finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

# --- Запуск ---
if __name__ == "__main__":
    print("Cybersquatting connector started.")
    print(f"Target substrings: {TARGET_SUBSTRINGS}")
    print(f"Exclude substrings: {EXCLUDE_SUBSTRINGS}")
    print(f"Schedule: {SCHEDULE_INTERVAL if SCHEDULE_INTERVAL else SCHEDULE_TIME}")

    # Выполнить задачу один раз сразу при запуске (опционально)
    job()

    # Настройка расписания
    if SCHEDULE_INTERVAL:
        schedule.every(int(SCHEDULE_INTERVAL)).seconds.do(job)
        print(f"Job scheduled every {SCHEDULE_INTERVAL} seconds")
    else:
        schedule.every().day.at(SCHEDULE_TIME).do(job)
        print(f"Job scheduled daily at {SCHEDULE_TIME}")

    # Бесконечный цикл
    while True:
        schedule.run_pending()
        time.sleep(60)
