import re
from bs4 import BeautifulSoup

with open('parasakthi-index.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'lxml')

# Find all theater listings
theater_elements = soup.find_all('li', class_=re.compile(r'MovieSessionsListing_movieSessions'))
print(f'Total theaters: {len(theater_elements)}')

# Find Vettri specifically
for elem in theater_elements:
    text = elem.get_text().lower()
    if 'vettri' in text:
        print('Found Vettri theater element!')
        # Find links
        links = elem.find_all('a')
        for link in links:
            t = link.get_text(strip=True)
            if t and 'vettri' in t.lower():
                print(f'Theater name: {t}')
        # Find timeblocks
        timeblocks = elem.find_all('li', class_=re.compile(r'MovieSessionsListing_timeblock'))
        print(f'Timeblocks: {len(timeblocks)}')
        for tb in timeblocks[:3]:
            time_div = tb.find('div', class_=re.compile(r'MovieSessionsListing_time'))
            if time_div:
                classes = time_div.get('class')
                print(f'  Time div text: {time_div.get_text(strip=True)[:30]}')
                print(f'  Classes: {classes}')
