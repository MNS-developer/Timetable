import os
import asyncio
import aiohttp

# Output folder for HTML files
OUTPUT_DIR = "course_htmls"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Endpoint base
BASE_URL = "https://my.kfueit.edu.pk/users/testtable"

# Static headers & cookies from your curl
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en-PK;q=0.9,en;q=0.8,ur-PK;q=0.7,ur;q=0.6",
    "Connection": "keep-alive",
    "Referer": "https://my.kfueit.edu.pk/users/testtable",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
}

COOKIES = {
    "_ga": "GA1.3.1269834786.1758520982",
    "ZDEDebuggerPresent": "php,phtml,php3",
    "_gid": "qeg8hk96476hi8vg875ujf3e3m8r9gsk",
    "ci_session": "l03dr54112et7fvub3aodrcf2euqp0dn"
}


async def fetch_course(session, course):
    filename = os.path.join(OUTPUT_DIR, f"{course}.html")

    # Skip if file already exists
    if os.path.exists(filename):
        print(f"[SKIP] {course}.html already exists")
        return

    params = {
        "filter": "class",
        "room": "",
        "teacher": "",
        "subject": "",
        "timetablename": "KFUEIT Fall 2025 Time Table",
        "sets": course
    }
    try:
        async with session.get(BASE_URL, headers=HEADERS, cookies=COOKIES, params=params) as resp:
            if resp.status == 200:
                html = await resp.text()
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[OK] Saved {course}.html")
            else:
                print(f"[ERROR] {course}: HTTP {resp.status}")
    except Exception as e:
        print(f"[FAILED] {course}: {e}")


async def main():
    # Read course list
    with open("courses.txt", "r") as f:
        courses = [line.strip() for line in f if line.strip()]

    print(f"Found {len(courses)} courses. Starting downloads...")

    # Limit concurrency (avoid flooding server)
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_course(session, course) for course in courses]
        await asyncio.gather(*tasks)

    print("All downloads complete.")


if __name__ == "__main__":
    asyncio.run(main())
